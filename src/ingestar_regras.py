import os
from dotenv import load_dotenv
from supabase.client import create_client, Client
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SupabaseVectorStore

load_dotenv()


def subir_regras_supabase():
    print("Conectando ao Supabase...")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")  # Use a sua chave anon ou service_role
    supabase: Client = create_client(url, key)

    caminho_pasta = "docs/contexto_alphatech"
    print(f"Lendo arquivos .md da pasta: {caminho_pasta}...")

    loader = DirectoryLoader(
        path=caminho_pasta,
        glob="*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()

    print("Fatiando os textos...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150, separators=["\n\n", "\n", " ", ""]
    )
    textos_fatiados = text_splitter.split_documents(docs)

    print("Gerando Embeddings e enviando para o Supabase Vector...")
    # ATENÇÃO: "text-embedding-004" foi removido na nova SDK (google-genai >= 1.x).
    # "gemini-embedding-001" reduzido para 768 dims por compatibilidade com pgvector ivfflat.
    # O Supabase ivfflat index tem limite de 2000 dims; output_dimensionality=768
    # garante que os embeddings caibam naquela tabela vector(768) existente.
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        output_dimensionality=768,  # Mantém compatibilidade com table vector(768)
    )

    # Ingestão em nuvem apontando para a tabela 'documents'
    SupabaseVectorStore.from_documents(
        textos_fatiados,
        embeddings,
        client=supabase,
        table_name="documents",
        query_name="match_documents",
    )

    print("✅ Regras de negócio inseridas com sucesso na nuvem do Supabase!")


if __name__ == "__main__":
    subir_regras_supabase()
