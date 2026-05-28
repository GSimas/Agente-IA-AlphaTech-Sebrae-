import os
import pandas as pd
import sqlite3
import numpy as np
import unicodedata
from dotenv import load_dotenv
from supabase import create_client, Client


# Nova função para limpar acentos das colunas de forma definitiva
def limpar_nomes_colunas(df):
    colunas_limpas = []
    for col in df.columns:
        # Remove acentos substituindo caracteres especiais pelos equivalentes ASCII
        col_sem_acento = "".join(
            c
            for c in unicodedata.normalize("NFD", col)
            if unicodedata.category(c) != "Mn"
        )
        colunas_limpas.append(col_sem_acento)
    df.columns = colunas_limpas
    return df


def enriquecer_dados():
    caminho_db = os.path.join("data", "banco_financeiro.db")
    caminho_excel_saida = os.path.join("data", "base_financeira_enriquecida.xlsx")

    print("Conectando ao banco de dados SQLite...")
    conn = sqlite3.connect(caminho_db)

    # 1. Leitura das Tabelas Individuais
    df_receitas = pd.read_sql_query("SELECT * FROM receitas", conn)
    df_custos = pd.read_sql_query("SELECT * FROM custos_despesas", conn)
    df_metas = pd.read_sql_query("SELECT * FROM metas", conn)

    print("Removendo possíveis acentos dos nomes das colunas...")
    df_receitas = limpar_nomes_colunas(df_receitas)
    df_custos = limpar_nomes_colunas(df_custos)
    df_metas = limpar_nomes_colunas(df_metas)

    print("Consolidando Receitas e Custos por Mês e Unidade...")

    # Agrupando receitas
    receitas_agg = (
        df_receitas.groupby(["mes", "unidade_negocio"])["receita_liquida"]
        .sum()
        .reset_index()
    )
    receitas_agg.rename(
        columns={"receita_liquida": "receita_total_realizada"}, inplace=True
    )

    # Agrupando custos
    custos_agg = (
        df_custos.groupby(["mes", "unidade_negocio"])["valor"].sum().reset_index()
    )
    custos_agg.rename(columns={"valor": "custo_total_realizado"}, inplace=True)

    # 2. Mesclando as bases
    df_consolidado = pd.merge(
        receitas_agg, custos_agg, on=["mes", "unidade_negocio"], how="outer"
    ).fillna(0)
    df_consolidado = pd.merge(
        df_consolidado, df_metas, on=["mes", "unidade_negocio"], how="left"
    )

    # Ordenar por unidade e mês
    df_consolidado = df_consolidado.sort_values(
        by=["unidade_negocio", "mes"]
    ).reset_index(drop=True)

    print("Calculando Métricas e Regras de Negócio...")

    # 3. Margem Realizada (%)
    df_consolidado["margem_realizada_perc"] = np.where(
        df_consolidado["receita_total_realizada"] > 0,
        (
            df_consolidado["receita_total_realizada"]
            - df_consolidado["custo_total_realizado"]
        )
        / df_consolidado["receita_total_realizada"],
        0,
    )

    # 4. EBITDA
    df_consolidado["ebitda_realizado"] = (
        df_consolidado["receita_total_realizada"]
        - df_consolidado["custo_total_realizado"]
    )

    # 5. Variação Mensal (MoM)
    df_consolidado["variacao_receita_mom"] = (
        df_consolidado.groupby("unidade_negocio")["receita_total_realizada"]
        .pct_change()
        .fillna(0)
    )

    # 6. Desvios
    if "meta_receita_liquida" in df_consolidado.columns:
        df_consolidado["desvio_receita"] = (
            df_consolidado["receita_total_realizada"]
            - df_consolidado["meta_receita_liquida"]
        )
        df_consolidado["status_meta_receita"] = np.where(
            df_consolidado["desvio_receita"] >= 0, "Atingida", "Não Atingida"
        )
    else:
        df_consolidado["desvio_receita"] = 0
        df_consolidado["status_meta_receita"] = "Sem Meta"

    # 7. Risco
    def classificar_risco(row):
        meta_margem = row.get("meta_margem", 0)
        desvio = row.get("desvio_receita", 0)
        if row["margem_realizada_perc"] < meta_margem and desvio < 0:
            return "Alto"
        elif row["margem_realizada_perc"] < meta_margem or desvio < 0:
            return "Médio"
        else:
            return "Baixo"

    df_consolidado["nivel_de_risco"] = df_consolidado.apply(classificar_risco, axis=1)

    # --- SALVANDO NO LOCAL (MANTIDO PARA SEU BACKUP) ---
    df_consolidado.to_sql(
        "resumo_financeiro_enriquecido", conn, if_exists="replace", index=False
    )
    conn.close()

    with pd.ExcelWriter(caminho_excel_saida, engine="openpyxl") as writer:
        df_consolidado.to_excel(writer, sheet_name="resumo_consolidado", index=False)
        df_receitas.to_excel(writer, sheet_name="receitas_originais", index=False)
        df_custos.to_excel(writer, sheet_name="custos_originais", index=False)

    print("✅ Dados locais processados e Excel gerado!")

    # --- NOVO: ENVIANDO PARA A NUVEM (SUPABASE) ---
    print("Conectando ao Supabase para atualizar a nuvem...")
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("⚠️ ERRO: Credenciais do Supabase não encontradas no .env!")
        return

    supabase: Client = create_client(url, key)

    # Substitui NaNs gerados pelo Pandas por None (Null) para o JSON do Supabase não quebrar
    df_nuvem = df_consolidado.replace({np.nan: None})

    # Converte para formato JSON (lista de dicionários)
    registros = df_nuvem.to_dict(orient="records")

    try:
        # Usa a constraint "unique_mes_unidade" que criamos no SQL para mesclar dados antigos
        resposta = (
            supabase.table("resumo_financeiro_enriquecido")
            .upsert(registros, on_conflict="mes,unidade_negocio")
            .execute()
        )

        print(
            f"✅ Sucesso absoluto! {len(registros)} linhas foram atualizadas/inseridas no banco vetorial da IA."
        )
    except Exception as e:
        print(f"⚠️ Erro ao enviar dados para a nuvem: {e}")


if __name__ == "__main__":
    enriquecer_dados()
