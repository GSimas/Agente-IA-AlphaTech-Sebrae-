"""
agente.py — AlphaTech Financial Agent
Arquitetura: LangGraph StateGraph customizado com síntese forçada.

FLUXO GARANTIDO:
  agent_node ──→ (sem tool_calls) ──→ END          [resposta direta]
       └──────→ (com tool_calls) ──→ tools_node
                                         └──[aresta FIXA]──→ synthesize_node ──→ END

A aresta tools → synthesize é determinística (add_edge, não conditional_edge).
Isso torna matematicamente impossível que uma ToolMessage seja a resposta final.
"""

import os
from typing import Annotated, Sequence

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.ferramentas import consultar_banco_sql, consultar_regras_negocio

load_dotenv()


# ==============================================================================
# 1. ESTADO DO GRAFO
# ==============================================================================


class AgentState(TypedDict):
    """
    Estado compartilhado entre todos os nós do grafo.
    'messages' usa o reducer add_messages do LangGraph para acumular o histórico.
    'ferramentas_usadas' é uma flag de auditoria — não controla o fluxo
    (o fluxo é determinístico pela aresta fixa tools → synthesize).
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    ferramentas_usadas: bool


# ==============================================================================
# 2. SYSTEM PROMPTS — SEPARAÇÃO DE RESPONSABILIDADES
# ==============================================================================

# Prompt do Agente Coletor: foco exclusivo em chamar as ferramentas certas.
# Ele NÃO sintetiza — isso é responsabilidade do nó de síntese.
_PROMPT_COLETOR = """Você é o Agente Coletor de Dados da AlphaTech.
Sua ÚNICA responsabilidade é identificar quais dados são necessários e chamar as
ferramentas corretas para buscá-los. Não tente formatar ou sintetizar a resposta.

FERRAMENTAS DISPONÍVEIS:
1. consultar_banco_sql(query: str)
   → Executa SQL no SQLite. Tabela principal: 'resumo_financeiro_enriquecido'.
   Colunas: mes, unidade_negocio, receita_total_realizada, custo_total_realizado,
   meta_receita_liquida, meta_margem, meta_ebitda, margem_realizada_perc,
   ebitda_realizado, variacao_receita_mom, desvio_receita,
   status_meta_receita, nivel_de_risco.

2. consultar_regras_negocio(pergunta: str)
   → Busca diretrizes, políticas e definições de risco no ChromaDB.

REGRA: Chame as ferramentas adequadas. Se nenhuma ferramenta for necessária
(pergunta puramente conceitual), responda diretamente de forma profissional.
"""

# Prompt do Sintetizador: recebe dados brutos, gera relatório formatado.
# Este nó é acionado APENAS quando ferramentas foram chamadas.
_PROMPT_SINTETIZADOR = """Você é o Analista Financeiro Sênior da AlphaTech.
Você recebeu dados brutos coletados pelas ferramentas de busca.
Sua missão exclusiva é transformá-los em um relatório executivo profissional em Markdown.

REGRAS ABSOLUTAS DE FORMATAÇÃO:
1. NUNCA exiba tuplas Python, listas brutas, ou dumps de banco de dados.
2. Converta todos os valores monetários para o formato "R$ 1.234.567,89".
3. Converta percentuais para "12,34%".
4. Use cabeçalhos Markdown (## para seções principais, ### para sub-seções).
5. Use tabelas Markdown quando comparar múltiplas unidades ou períodos.
6. Sempre inclua comparação Realizado vs. Meta quando os dados permitirem.
7. Destaque alertas críticos com o emoji ⚠️ e risco alto com 🔴.
8. Finalize SEMPRE com a seção "## 💡 Recomendações Executivas" baseada
   nas políticas internas encontradas no RAG.
9. Tom: profissional, analítico, direto — como um relatório do Board.
"""


# ==============================================================================
# 3. CONSTRUÇÃO DO GRAFO
# ==============================================================================


def inicializar_agente():
    """
    Compila e retorna o StateGraph LangGraph com síntese forçada.

    Nós:
      - 'coletor'   : LLM com tools bound; decide e executa a coleta.
      - 'tools'     : ToolNode padrão do LangGraph; executa as tool_calls.
      - 'sintetizar': LLM sem tools; SEMPRE chamado após tools; gera o relatório.

    Arestas:
      - coletor → (conditional) → tools | END
      - tools   → (fixa)        → sintetizar       ← PONTO CRÍTICO
      - sintetizar → END
    """
    tools = [consultar_banco_sql, consultar_regras_negocio]

    # LLM do Coletor: tem as ferramentas disponíveis via .bind_tools()
    llm_coletor = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.1,
    ).bind_tools(tools)

    # LLM do Sintetizador: SEM ferramentas, focado apenas em escrita analítica
    llm_sintetizador = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.3,
    )

    # ToolNode executa todas as tool_calls presentes na última AIMessage
    tool_node = ToolNode(tools)

    # --------------------------------------------------------------------------
    # Definição dos Nós
    # --------------------------------------------------------------------------

    def no_coletor(state: AgentState) -> AgentState:
        """
        Nó 1 — Coletor: o LLM decide quais ferramentas chamar (ou responde diretamente).
        Registra se tools foram acionadas para auditoria.
        """
        mensagens_com_sistema = [
            SystemMessage(content=_PROMPT_COLETOR),
            *state["messages"],
        ]
        resposta: AIMessage = llm_coletor.invoke(mensagens_com_sistema)
        ferramentas_usadas = bool(getattr(resposta, "tool_calls", None))
        return {
            "messages": [resposta],
            "ferramentas_usadas": ferramentas_usadas,
        }

    def no_sintetizar(state: AgentState) -> AgentState:
        """
        Nó 3 — Sintetizador: SEMPRE executado após o ToolNode.
        Constrói um contexto limpo com a pergunta original + todos os resultados
        das ferramentas, e gera o relatório executivo formatado em Markdown.
        Garante que NUNCA dados brutos cheguem ao usuário.
        """
        contexto = _construir_contexto_sintese(state["messages"])
        mensagens_sintese = [
            SystemMessage(content=_PROMPT_SINTETIZADOR),
            HumanMessage(content=contexto),
        ]
        resposta: AIMessage = llm_sintetizador.invoke(mensagens_sintese)
        return {
            "messages": [resposta],
            "ferramentas_usadas": False,
        }

    # --------------------------------------------------------------------------
    # Roteador da Aresta Condicional (apenas após o nó coletor)
    # --------------------------------------------------------------------------

    def rotear_apos_coletor(state: AgentState) -> str:
        """
        Se a última AIMessage contém tool_calls → vai para 'tools'.
        Caso contrário → vai direto para END (resposta direta sem dados externos).
        """
        ultima = state["messages"][-1]
        if hasattr(ultima, "tool_calls") and ultima.tool_calls:
            return "tools"
        return "end"

    # --------------------------------------------------------------------------
    # Construção e Compilação do Grafo
    # --------------------------------------------------------------------------

    grafo = StateGraph(AgentState)

    grafo.add_node("coletor", no_coletor)
    grafo.add_node("tools", tool_node)
    grafo.add_node("sintetizar", no_sintetizar)

    grafo.set_entry_point("coletor")

    # Aresta condicional: coletor → tools | END
    grafo.add_conditional_edges(
        "coletor",
        rotear_apos_coletor,
        {"tools": "tools", "end": END},
    )

    # ★ ARESTA FIXA — O ponto que resolve o bug de premature stopping.
    # Não há escolha, não há LLM decidindo: após tools, SEMPRE sintetiza.
    grafo.add_edge("tools", "sintetizar")

    # Aresta fixa: após síntese → END
    grafo.add_edge("sintetizar", END)

    return grafo.compile()


# ==============================================================================
# 4. CONSTRUÇÃO DO CONTEXTO DE SÍNTESE
# ==============================================================================


def _construir_contexto_sintese(messages: Sequence[BaseMessage]) -> str:
    """
    Percorre o histórico de mensagens e extrai:
    - A pergunta original do usuário (HumanMessage)
    - Os resultados de cada ferramenta (ToolMessage)

    Retorna um texto estruturado para o LLM Sintetizador processar.
    """
    pergunta_original = "(não identificada)"
    resultados_ferramentas: list[str] = []

    for msg in messages:
        nome_classe = msg.__class__.__name__
        conteudo = getattr(msg, "content", "")

        # Normaliza conteúdo em lista (padrão Gemini multimodal)
        if isinstance(conteudo, list):
            conteudo = "\n".join(
                bloco.get("text", "")
                for bloco in conteudo
                if isinstance(bloco, dict)
            )

        if nome_classe == "HumanMessage":
            pergunta_original = str(conteudo).strip()

        elif nome_classe == "ToolMessage":
            nome_ferramenta = getattr(msg, "name", "ferramenta_desconhecida")
            resultados_ferramentas.append(
                f"#### Resultado de `{nome_ferramenta}`:\n"
                f"```\n{str(conteudo).strip()}\n```"
            )

    linhas = [
        "### Solicitação do Usuário:",
        pergunta_original,
        "",
        "### Dados Coletados pelas Ferramentas:",
        "",
    ]

    if resultados_ferramentas:
        linhas.extend(resultados_ferramentas)
    else:
        linhas.append("*Nenhum dado de ferramenta disponível.*")

    linhas += [
        "",
        "---",
        "**Instrução:** Com base nos dados acima, gere agora o relatório executivo "
        "completo, formatado em Markdown profissional, conforme suas diretrizes.",
    ]

    return "\n".join(linhas)


# ==============================================================================
# 5. INTERFACE PÚBLICA — EXECUÇÃO E EXTRAÇÃO ROBUSTA
# ==============================================================================


def executar_pergunta(agente, pergunta: str) -> str:
    """
    Invoca o agente e extrai a resposta final.

    Com a nova arquitetura, a última mensagem do estado será SEMPRE:
    - Uma AIMessage do Sintetizador (se ferramentas foram usadas), ou
    - Uma AIMessage do Coletor (se a resposta foi direta, sem ferramentas).

    Nunca será uma ToolMessage.
    """
    try:
        estado_final = agente.invoke(
            {
                "messages": [HumanMessage(content=pergunta)],
                "ferramentas_usadas": False,
            }
        )

        # Validação do formato do estado
        if not isinstance(estado_final, dict) or "messages" not in estado_final:
            return (
                "⚠️ **Erro de Formato:** O agente retornou um estado inesperado. "
                "Tente novamente ou reformule a pergunta."
            )

        mensagens = estado_final.get("messages", [])
        if not mensagens:
            return "⚠️ **Sem Resposta:** O agente não gerou nenhuma mensagem. Reformule a pergunta."

        ultima_msg = mensagens[-1]
        conteudo = getattr(ultima_msg, "content", "")

        # Normaliza conteúdo em lista (resposta multipart do Gemini)
        if isinstance(conteudo, list):
            partes = [
                bloco.get("text", "")
                for bloco in conteudo
                if isinstance(bloco, dict) and bloco.get("text")
            ]
            conteudo = "\n".join(partes)

        conteudo = str(conteudo).strip()

        # Guarda de segurança — nunca deveria acontecer com a nova arquitetura
        if isinstance(ultima_msg, ToolMessage):
            return (
                "⚠️ **Anomalia de Pipeline:** O nó de síntese não foi executado. "
                "Isso não deveria acontecer — verifique os logs do LangGraph.\n\n"
                f"*Preview dos dados brutos (debug):*\n```\n{conteudo[:800]}\n```"
            )

        if not conteudo:
            return (
                "⚠️ **Síntese Vazia:** O agente coletou os dados, mas a resposta final "
                "retornou vazia. Tente reformular a pergunta com mais detalhes."
            )

        return conteudo

    except Exception as e:
        return (
            f"⚠️ **Erro Interno:** `{type(e).__name__}`: {e}\n\n"
            "Verifique as credenciais da API, a conexão com o banco e tente novamente."
        )


# ==============================================================================
# 6. RELATÓRIOS PADRONIZADOS
# ==============================================================================
# Os prompts abaixo são otimizados para o nó Coletor:
# instruem QUAIS ferramentas chamar e com QUAIS queries/perguntas.
# A formatação do relatório é 100% responsabilidade do nó Sintetizador.


def gerar_relatorio_executivo(agente) -> str:
    """Relatório 1 — Relatório Executivo Mensal Consolidado."""
    pergunta = (
        "Gere o Relatório Executivo Mensal da AlphaTech. "
        "Para isso, execute as seguintes coletas:\n\n"
        "1. [SQL] Totais consolidados:\n"
        "   SELECT "
        "SUM(receita_total_realizada) AS receita_total, "
        "SUM(custo_total_realizado) AS custo_total, "
        "ROUND(AVG(margem_realizada_perc), 2) AS margem_media, "
        "SUM(ebitda_realizado) AS ebitda_total, "
        "SUM(meta_receita_liquida) AS meta_receita_total, "
        "ROUND(AVG(meta_margem), 2) AS meta_margem_media, "
        "SUM(meta_ebitda) AS meta_ebitda_total "
        "FROM resumo_financeiro_enriquecido\n\n"
        "2. [RAG] Busque: 'políticas de redução de custos e critérios de risco AlphaTech'."
    )
    return executar_pergunta(agente, pergunta)


def gerar_relatorio_unidade(agente) -> str:
    """Relatório 2 — Desempenho por Unidade de Negócio."""
    pergunta = (
        "Gere o Relatório de Desempenho por Unidade de Negócio da AlphaTech. "
        "Para isso, execute as seguintes coletas:\n\n"
        "1. [SQL] Métricas por unidade:\n"
        "   SELECT "
        "unidade_negocio, "
        "SUM(receita_total_realizada) AS receita_total, "
        "SUM(custo_total_realizado) AS custo_total, "
        "ROUND(AVG(margem_realizada_perc), 2) AS margem_media, "
        "SUM(ebitda_realizado) AS ebitda_total, "
        "nivel_de_risco "
        "FROM resumo_financeiro_enriquecido "
        "GROUP BY unidade_negocio, nivel_de_risco\n\n"
        "2. [RAG] Busque: 'diretrizes de alocação de capital e prioridade de marketing por unidade'."
    )
    return executar_pergunta(agente, pergunta)


def gerar_relatorio_riscos(agente) -> str:
    """Relatório 3 — Análise de Riscos Financeiros."""
    pergunta = (
        "Gere o Relatório de Riscos Financeiros da AlphaTech. "
        "Para isso, execute as seguintes coletas:\n\n"
        "1. [SQL] Indicadores de risco por unidade e mês:\n"
        "   SELECT "
        "mes, "
        "unidade_negocio, "
        "desvio_receita, "
        "variacao_receita_mom, "
        "nivel_de_risco, "
        "status_meta_receita "
        "FROM resumo_financeiro_enriquecido "
        "ORDER BY nivel_de_risco DESC, desvio_receita ASC\n\n"
        "2. [RAG] Busque: 'definição de risco alto médio baixo e políticas de mitigação AlphaTech'."
    )
    return executar_pergunta(agente, pergunta)


# ==============================================================================
# 7. TESTE LOCAL
# ==============================================================================

if __name__ == "__main__":
    print("Inicializando agente LangGraph...\n")
    agente = inicializar_agente()

    print("=" * 60)
    print("TESTE 1: Relatório por Unidade de Negócio")
    print("=" * 60)
    resultado = gerar_relatorio_unidade(agente)
    print(resultado)

    print("\n" + "=" * 60)
    print("TESTE 2: Pergunta em Linguagem Natural")
    print("=" * 60)
    pergunta_livre = (
        "Qual unidade de negócio tem o maior nível de risco "
        "e o que as diretrizes internas recomendam para mitigá-lo?"
    )
    print(f"Pergunta: {pergunta_livre}\n")
    resposta = executar_pergunta(agente, pergunta_livre)
    print(resposta)
