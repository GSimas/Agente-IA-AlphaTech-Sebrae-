import streamlit as st
import markdown
from fpdf import FPDF
import re
from agente import (
    inicializar_agente,
    gerar_relatorio_executivo,
    gerar_relatorio_unidade,
    gerar_relatorio_riscos,
    executar_pergunta,
)


# --- FUNÇÃO DE EXPORTAÇÃO ---
def exportar_para_pdf(texto_markdown):
    """
    Converte o texto Markdown gerado pelo Agente (incluindo tabelas)
    para um arquivo PDF em formato de bytes, limpando emojis incompatíveis.
    """
    # 1. Filtro de Limpeza: Substitui emojis e caracteres especiais problemáticos
    substituicoes = {
        "⚠️": "[Atenção]",
        "⚠": "[Atenção]",
        "📈": "",
        "🏢": "",
        "📊": "",
        "🤖": "",
        "💡": "[Dica]",
        "•": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
    }
    texto_limpo = texto_markdown
    for velho, novo in substituicoes.items():
        texto_limpo = texto_limpo.replace(velho, novo)

    # Remove qualquer outro emoji que não mapeamos (mantém apenas caracteres suportados)
    texto_limpo = texto_limpo.encode("latin-1", "ignore").decode("latin-1")

    # 2. Converte o Markdown limpo para HTML
    html_convertido = markdown.markdown(texto_limpo, extensions=["tables"])

    # 3. Inicializa o PDF
    pdf = FPDF()
    pdf.add_page()

    # 4. Define a fonte padrão
    pdf.set_font("helvetica", size=11)

    # 5. Escreve o HTML interpretado no PDF
    pdf.write_html(html_convertido)

    # 6. Retorna o binário do PDF
    return bytes(pdf.output())


# Configuração da página (deve ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="AlphaTech | Agente Financeiro IA", page_icon="📊", layout="wide"
)

# Renderiza a logo na sidebar
st.sidebar.image("alphatech-logo.png", use_container_width=True)


# Inicializa o Agente apenas uma vez na sessão para otimizar performance
if "agente" not in st.session_state:
    with st.spinner("Inicializando o cérebro da IA e conectando aos dados..."):
        st.session_state.agente = inicializar_agente()

# Inicializa o histórico de mensagens do chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Olá! Sou o Agente de IA da AlphaTech. Como posso ajudar nas análises financeiras e executivas hoje?",
        }
    ]

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.title("📊 Painel Executivo")
    st.write("Geração rápida de relatórios padronizados:")

    # Botões para os 3 relatórios obrigatórios
    if st.button("📈 Relatório Executivo Mensal", use_container_width=True):
        st.session_state.messages.append(
            {"role": "user", "content": "Gere o Relatório Executivo Mensal."}
        )
        with st.spinner("Consultando dados e elaborando relatório..."):
            resposta = gerar_relatorio_executivo(st.session_state.agente)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.rerun()  # Força a atualização imediata da tela para renderizar o relatório e o PDF

    if st.button("🏢 Relatório por Unidade", use_container_width=True):
        st.session_state.messages.append(
            {"role": "user", "content": "Gere o Relatório por Unidade de Negócio."}
        )
        with st.spinner("Consolidando métricas das unidades..."):
            resposta = gerar_relatorio_unidade(st.session_state.agente)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.rerun()

    if st.button("⚠️ Relatório de Riscos", use_container_width=True):
        st.session_state.messages.append(
            {"role": "user", "content": "Gere o Relatório de Riscos Financeiros."}
        )
        with st.spinner("Cruzando desvios com políticas de risco..."):
            resposta = gerar_relatorio_riscos(st.session_state.agente)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.rerun()

    st.markdown("---")
    st.caption("Gustavo Simas © 2026")


# --- ÁREA PRINCIPAL (CHATBOT INTERATIVO) ---
st.title("🤖 Chatbot Financeiro - AlphaTech")
st.write(
    "Faça perguntas livres sobre receitas, custos, metas ou diretrizes da empresa."
)

# Renderiza o histórico de mensagens de forma dinâmica
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # SEGREDO DO SUCESSO: Se a mensagem for do assistente e não for a mensagem inicial de boas-vindas,
        # injeta o botão de exportação para PDF diretamente abaixo do texto no histórico.
        if message["role"] == "assistant" and idx > 0:
            try:
                pdf_bytes = exportar_para_pdf(message["content"])
                st.write("")
                st.download_button(
                    label="📥 Baixar Relatório em PDF",
                    data=pdf_bytes,
                    file_name=f"Relatorio_AlphaTech_{idx}.pdf",
                    mime="application/pdf",
                    key=f"btn_pdf_history_{idx}",  # Garante chaves únicas e imutáveis durante a iteração
                )
            except Exception as pdf_err:
                st.caption(f"⚠️ Erro ao preparar PDF para esta mensagem: {pdf_err}")


# Captura a entrada do usuário em linguagem natural (Chat input livre)
if prompt := st.chat_input(
    "Ex: Qual unidade teve a pior margem e qual a recomendação para ela?"
):
    # Exibe a pergunta do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Força atualização para imprimir na hora o prompt do usuário e chamar a resposta do agente
    st.rerun()

# Lógica de processamento em tempo real do chat input para capturar a última pergunta adicionada
if st.session_state.messages[-1]["role"] == "user":
    ultimo_prompt = st.session_state.messages[-1]["content"]

    # Evita reprocessar se o usuário acabou de usar um dos botões da sidebar que já inseriram o assistant no histórico
    # Só roda se a última mensagem for estritamente um prompt livre sem resposta associada
    with st.chat_message("assistant"):
        with st.spinner("Analisando bases de dados e diretrizes..."):
            try:
                # 1. Executa o Agente para perguntas livres
                resposta = executar_pergunta(st.session_state.agente, ultimo_prompt)

                # 2. Salva a resposta no histórico da sessão
                st.session_state.messages.append(
                    {"role": "assistant", "content": resposta}
                )

                # Força a atualização para que a nova mensagem caia na lógica do laço de renderização estruturado acima
                st.rerun()

            except Exception as e:
                erro_msg = f"Ocorreu um erro ao processar sua solicitação: {e}"
                st.error(erro_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": erro_msg}
                )
                st.rerun()
