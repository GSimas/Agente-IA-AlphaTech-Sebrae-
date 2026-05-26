import sqlite3
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

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
    Busca informações qualitativas, regras de negócio, metas e diretrizes da AlphaTech.
    Use esta ferramenta para responder perguntas sobre o que fazer, recomendações,
    políticas de redução de custos ou classificações de risco.
    """
    caminho_chroma = os.path.join("data", "chroma_db")

    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

    try:
        # Carrega o banco vetorial existente
        vector_store = Chroma(
            persist_directory=caminho_chroma, embedding_function=embeddings
        )

        # Realiza a busca por similaridade semântica (traz os 3 trechos mais relevantes)
        docs = vector_store.similarity_search(pergunta, k=3)

        if not docs:
            return "Nenhuma diretriz ou regra de negócio encontrada para esta pergunta."

        # Concatena o conteúdo dos documentos encontrados para o LLM ler
        contexto = "Contexto recuperado das diretrizes internas da empresa:\n\n"
        for i, doc in enumerate(docs, 1):
            contexto += f"--- Trecho {i} ---\n{doc.page_content}\n\n"

        return contexto
    except Exception as e:
        return f"Erro ao consultar o banco de conhecimento (RAG): {e}"


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
