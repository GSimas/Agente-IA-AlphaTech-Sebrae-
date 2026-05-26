import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# Carrega a chave da API do arquivo .env
load_dotenv()


def criar_documentos_ficticios():
    """Cria os arquivos Markdown com o contexto da AlphaTech."""
    caminho_docs = os.path.join("docs", "contexto_alphatech")
    os.makedirs(caminho_docs, exist_ok=True)

    regras = {
        "regras_negocio.md": """# Regras de Negócio e Políticas Financeiras - AlphaTech
        
1. Classificação de Risco:
- Risco Alto: Margem abaixo da meta E desvio negativo de receita. Requer plano de ação imediato.
- Risco Médio: Margem abaixo da meta OU desvio negativo de receita. Requer monitoramento mensal.
- Risco Baixo: Margem e receita dentro ou acima da meta.

2. Políticas de Redução de Custos:
- Se a unidade de 'Software' apresentar queda de margem, a recomendação é renegociar contratos de infraestrutura em nuvem e pausar novas contratações.
- Se a unidade de 'Consultoria' apresentar queda de margem, a recomendação é focar na venda de projetos de alto valor agregado (ticket médio maior) e otimizar a alocação de horas da equipe.
- Se a unidade de 'Treinamentos' apresentar queda de margem, a recomendação é migrar para turmas 100% online para cortar custos logísticos e de espaço físico.

3. Alocação de Capital:
- Unidades com melhor margem e crescimento consecutivo ganham prioridade no orçamento de marketing no trimestre seguinte.
""",
        "metas_empresa.md": """# Metas e Objetivos Estratégicos 2025/2026 - AlphaTech

1. Diretriz Principal: 
A AlphaTech busca um crescimento sustentável. A prioridade do ano não é apenas aumentar a receita bruta, mas garantir que a "Margem Realizada" fique sempre acima de 30% no consolidado da empresa.

2. Foco por Unidade de Negócio:
- Consultoria: Foco em expandir clientes Enterprise.
- Software: Foco em reduzir o Churn (cancelamentos) e aumentar o LTV.
- Treinamentos: Transformação digital e escalabilidade.
""",
        "dicionario_dados.md": """# Dicionário de Dados e Métricas
        
- Receita Líquida: Receita após dedução de impostos, devoluções e descontos comerciais. Base para calcular a margem.
- Custo Realizado: Todos os custos diretos e despesas operacionais daquela unidade de negócio.
- Margem: (Receita Líquida - Custos) / Receita Líquida. Indica a rentabilidade da operação.
- EBITDA Estimado: Receita Líquida - Custo Realizado. Reflete o potencial de geração de caixa antes de juros e impostos.
- Variação MoM (Month over Month): Compara o desempenho de um mês em relação ao mês imediatamente anterior. Importante para ver tendência de queda ou alta.
""",
    }

    caminhos_arquivos = []
    for nome_arquivo, conteudo in regras.items():
        caminho_completo = os.path.join(caminho_docs, nome_arquivo)
        with open(caminho_completo, "w", encoding="utf-8") as f:
            f.write(conteudo)
        caminhos_arquivos.append(caminho_completo)

    print(f"[{len(caminhos_arquivos)}] Documentos Markdown gerados em {caminho_docs}")
    return caminhos_arquivos


def construir_banco_vetorial():
    print("Iniciando a construção do RAG...")

    # 1. Gera e recupera os caminhos dos documentos
    arquivos = criar_documentos_ficticios()

    # 2. Carrega os documentos usando o LangChain
    documentos = []
    for arquivo in arquivos:
        loader = TextLoader(arquivo, encoding="utf-8")
        documentos.extend(loader.load())

    print(f"Total de documentos carregados: {len(documentos)}")

    # 3. Quebra os textos em pedaços menores (Chunks)
    # Isso ajuda o LLM a encontrar partes específicas da regra sem ler textos gigantes
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=50, length_function=len
    )
    chunks = text_splitter.split_documents(documentos)
    print(f"Documentos divididos em {len(chunks)} chunks de texto.")

    # 4. Configura o modelo de Embeddings do Google Gemini
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

    # 5. Cria e salva o banco de dados vetorial local (ChromaDB)
    caminho_chroma = os.path.join("data", "chroma_db")

    print("Gerando embeddings e salvando no ChromaDB...")
    vector_store = Chroma.from_documents(
        documents=chunks, embedding=embeddings, persist_directory=caminho_chroma
    )

    print(f"Sucesso! Banco vetorial salvo em: {caminho_chroma}")


if __name__ == "__main__":
    construir_banco_vetorial()
