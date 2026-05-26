import sqlite3
import os
from langchain_core.tools import tool          # langchain.tools está depreciado desde v0.3
from supabase.client import create_client
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from dotenv import load_dotenv

# Carrega a chave da API do arquivo .env para a memória
load_dotenv()


# 1. Tool de Consulta SQL (Dados Quantitativos)
@tool
def consultar_banco_sql(query: str) -> str:
    """
    Executa uma query SQL no banco de dados financeiro da AlphaTech e retorna os resultados.
    Use esta ferramenta APENAS com queries SQL válidas para SQLite.
    Sempre busque na tabela 'resumo_financeiro_enriquecido' para relatórios consolidados.
    """
    caminho_db = os.path.join("data", "banco_financeiro.db")
    try:
        conn = sqlite3.connect(caminho_db)
        cursor = conn.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()

        # Pega os nomes das colunas para dar contexto ao LLM
        colunas = [description[0] for description in cursor.description]
        conn.close()

        if not resultados:
            return "A consulta SQL foi executada, mas não retornou nenhum dado."

        # Formata o resultado como uma string legível para o LLM interpretar
        resposta = f"Colunas: {', '.join(colunas)}\nResultados:\n"
        for linha in resultados:
            resposta += f"- {linha}\n"

        return resposta
    except Exception as e:
        return f"Erro ao executar a query SQL. Ajuste sua sintaxe e tente novamente. Erro: {e}"


# 2. Tool de Consulta RAG (Dados Qualitativos e Regras)
@tool
def consultar_regras_negocio(pergunta: str) -> str:
    """
    Pesquisa no banco de dados vetorial Supabase as políticas internas,
    regras de negócio e orientações executivas da AlphaTech.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)

    # "text-embedding-004" foi aposentado na migração SDK v1→google-genai.
    # "gemini-embedding-001" produz 3072 dims por padrão, mas o Supabase com ivfflat
    # só suporta até 2000 dims. Usamos output_dimensionality=768 para compatibilidade.
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        output_dimensionality=768,  # Reduz para 768 dims (compatível com ivfflat)
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
    print("Testando Tool SQL...")
    teste_sql = consultar_banco_sql.invoke(
        "SELECT unidade_negocio, margem_realizada_perc FROM resumo_financeiro_enriquecido LIMIT 3"
    )
    print(teste_sql)

    print("\n------------------\n")

    print("Testando Tool RAG...")
    teste_rag = consultar_regras_negocio.invoke(
        "O que fazer se a unidade de software tiver queda de margem?"
    )
    print(teste_rag)
