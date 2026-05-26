import pandas as pd
import sqlite3
import os
import unicodedata


def limpar_nomes_colunas(df):
    """Limpa acentos, espaços e padroniza nomes de colunas"""
    colunas_limpas = []
    for i, col in enumerate(df.columns):
        # Trata colunas vazias
        if pd.isna(col) or str(col).strip() == "":
            col_str = f"col_vazia_{i}"
        else:
            col_str = str(col).strip().lower()

        # Remove acentos
        col_sem_acento = "".join(
            c
            for c in unicodedata.normalize("NFD", col_str)
            if unicodedata.category(c) != "Mn"
        )
        # Substitui espaços por underline
        col_sem_acento = (
            col_sem_acento.replace(" ", "_").replace("\n", "_").replace("-", "_")
        )
        colunas_limpas.append(col_sem_acento)

    df.columns = colunas_limpas
    return df


def encontrar_cabecalho_real(df):
    """Procura a linha que contém os verdadeiros cabeçalhos da tabela e remove as linhas de título acima dela"""
    # Verifica se as colunas já estão corretas (se não tem colunas 'unnamed')
    if not any("unnamed" in str(c).lower() for c in df.columns):
        return df

    # Percorre as primeiras 10 linhas procurando pelo cabeçalho real
    for idx, row in df.head(10).iterrows():
        valores_linha = [str(v).strip().lower() for v in row.values if pd.notna(v)]

        # Palavras-chave que indicam que achamos a linha de cabeçalhos
        if (
            "mes" in valores_linha
            or "unidade_negocio" in valores_linha
            or "unidade de negocio" in valores_linha
            or "campo" in valores_linha
        ):
            # Define essa linha como o novo cabeçalho
            df.columns = row.values
            # Corta o DataFrame para começar da linha seguinte e remove linhas 100% vazias
            df = df.iloc[idx + 1 :].dropna(how="all").reset_index(drop=True)
            return df

    # Fallback: Se não achar as palavras, tenta apenas pular a primeira linha
    df.columns = df.iloc[0].values
    return df.iloc[1:].dropna(how="all").reset_index(drop=True)


def processar_dados_financeiros():
    caminho_excel = os.path.join("data", "base-financeira-alphatech-QElu8nIR.xlsx")
    caminho_db = os.path.join("data", "banco_financeiro.db")

    if not os.path.exists(caminho_excel):
        print(f"Erro: O arquivo {caminho_excel} não foi encontrado.")
        return

    print("Iniciando a extração dos dados...")
    abas_excel = pd.read_excel(caminho_excel, sheet_name=None)
    conn = sqlite3.connect(caminho_db)

    print("Iniciando o tratamento e carregamento...")

    for nome_aba, df in abas_excel.items():
        print(f"\n-> Processando a aba: {nome_aba}")

        # 1. Ajusta cabeçalhos e limpa nomes
        df = encontrar_cabecalho_real(df)
        df = limpar_nomes_colunas(df)

        # 2. Tratamento Dinâmico de Moedas e Percentuais
        for col in df.columns:
            if df[col].dtype == "object":
                # Se contém R$, limpa e converte para float
                if df[col].astype(str).str.contains("R\$", na=False, regex=True).any():
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace("R$", "", regex=False)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                # Se contém %, limpa e divide por 100
                elif df[col].astype(str).str.contains("%", na=False).any():
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace("%", "", regex=False)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(df[col], errors="coerce") / 100

        # 3. Tratamento de Datas
        if "mes" in df.columns:
            df["mes"] = pd.to_datetime(df["mes"], errors="coerce").dt.strftime("%Y-%m")

        # 4. Tratamento de Nulos
        for col in df.columns:
            if df[col].dtype in ["float64", "int64"]:
                df[col] = df[col].fillna(0)
            elif df[col].dtype == "object":
                # Mantém vazio o que for lacuna para o agente IA preencher depois
                if nome_aba == "lacunas_para_enriquecimento" and col in [
                    "causa_provavel",
                    "recomendacao",
                    "fonte_referencia",
                ]:
                    df[col] = df[col].fillna("")
                else:
                    df[col] = df[col].fillna("Não Informado")

        # 5. Salva no SQLite
        df.to_sql(nome_aba, conn, if_exists="replace", index=False)
        print(
            f"   Tabela '{nome_aba}' corrigida e salva com as colunas: {df.columns.tolist()}"
        )

    conn.close()
    print(f"\nSucesso! Banco de dados estruturado em: {caminho_db}")


if __name__ == "__main__":
    processar_dados_financeiros()
