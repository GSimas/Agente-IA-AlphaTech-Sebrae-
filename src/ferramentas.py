import os
from langchain_core.tools import tool
from supabase.client import create_client
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

# Carrega a chave da API do arquivo .env para a memória
load_dotenv()


# 1. Tool de Consulta SQL (Dados Quantitativos - AGORA NA NUVEM)
@tool
def consultar_banco_sql(query: str) -> str:
    """
    Executa uma query SQL no banco de dados PostgreSQL (Supabase) da AlphaTech.

    MAPA DO BANCO DE DADOS (Escolha a tabela correta para a pergunta):
    1. 'receitas': Use para perguntas sobre CLIENTES específicos, PRODUTOS, status de clientes e faturamento bruto/líquido detalhado.
    2. 'custos_despesas': Use para perguntas sobre GASTOS detalhados, CATEGORIAS (ex: Pessoas, Marketing) e SUBCATEGORIAS.
    3. 'metas': Use para ver apenas os objetivos projetados isoladamente.
    4. 'resumo_financeiro_enriquecido': Use para visões GERENCIAIS, fechamento do mês, EBITDA, Margem % e nível de risco.

    REGRAS OBRIGATÓRIAS PARA O SQL:
    - Tipagem: As colunas "mes" e "ano" são TEXTO (VARCHAR). Sempre use aspas simples. Exemplo: mes = '02' AND ano = '2025'.
    - JOINs: Se a pergunta cruzar informações operacionais (ex: "Compare o gasto de Pessoas com a receita do Produto X na Consultoria"), faça um JOIN entre 'custos_despesas' e 'receitas' utilizando as chaves: "mes", "ano" e "unidade_negocio".
    - Sempre limite os resultados (LIMIT) se a busca for muito genérica.
    - Buscas de Texto: O PostgreSQL é case-sensitive. Ao buscar por status, nomes de clientes, produtos ou categorias, NUNCA use o operador '='. Use SEMPRE o operador 'ILIKE' com coringas (ex: status_cliente ILIKE '%inativo%').
    - Filtros de Data: Se o usuário NÃO especificar um mês ou ano na pergunta, NÃO coloque filtros de data no WHERE. Assuma que ele quer ver o histórico todo.
    - Evite Joins Desnecessários: Se a pergunta puder ser respondida consultando uma única tabela (ex: "Qual o EBITDA?" → use 'resumo_financeiro_enriquecido'), NÃO faça JOIN. Joins lentos confundem o modelo e podem gerar erros de sintaxe na concatenação.
    """
    string_conexao = os.environ.get("SUPABASE_DB_URL")

    if not string_conexao:
        return "Erro interno: A variável SUPABASE_DB_URL não foi encontrada no .env."

    try:
        # A MÁGICA ESTÁ AQUI: Liberando acesso a múltiplas tabelas e puxando 3 exemplos reais
        db = SQLDatabase.from_uri(
            string_conexao,
            include_tables=[
                "receitas",
                "custos_despesas",
                "metas",
                "resumo_financeiro_enriquecido",
            ],
            sample_rows_in_table_info=3,  # O LangChain injeta 3 linhas de exemplo de cada tabela no LLM para ele aprender o formato sozinho
        )

        resultados = db.run(query)

        if not resultados or resultados == "[]":
            return "A consulta SQL foi executada, mas não retornou nenhum dado. Verifique os filtros de mês/ano/unidade."

        return f"Resultados da consulta PostgreSQL:\n{resultados}"

    except Exception as e:
        return f"Erro ao executar a query SQL. Ajuste sua sintaxe (PostgreSQL) e tente novamente. Erro: {e}"


# 2. Tool de Consulta RAG (Dados Qualitativos e Regras - JÁ NA NUVEM)
@tool
def consultar_regras_negocio(pergunta: str) -> str:
    """
    Pesquisa no banco de dados vetorial Supabase as políticas internas,
    regras de negócio e orientações executivas da AlphaTech.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)

    # Embeddings atualizados e configurados para o limite de 768 do ivfflat
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        output_dimensionality=768,
    )

    # Conecta à mesma tabela que criamos via SQL
    vectorstore = SupabaseVectorStore(
        embedding=embeddings,
        client=supabase,
        table_name="documents",
        query_name="match_documents",
    )

    # Busca os 3 trechos mais similares à pergunta do usuário
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    documentos = retriever.invoke(pergunta)

    if not documentos:
        return "Nenhuma diretriz encontrada sobre este tema."

    resposta_formatada = "Contexto recuperado das diretrizes internas da AlphaTech:\n\n"
    for i, doc in enumerate(documentos):
        resposta_formatada += f"--- Trecho {i + 1} ---\n{doc.page_content}\n"

    return resposta_formatada


# Bloco de teste local
if __name__ == "__main__":
    print("Testando Tool SQL na Nuvem...")
    teste_sql = consultar_banco_sql.invoke(
        "SELECT unidade_negocio, margem_realizada_perc FROM resumo_financeiro_enriquecido LIMIT 3"
    )
    print(teste_sql)

    print("\n------------------\n")

    print("Testando Tool RAG na Nuvem...")
    teste_rag = consultar_regras_negocio.invoke(
        "O que fazer se a unidade de software tiver queda de margem?"
    )
    print(teste_rag)
