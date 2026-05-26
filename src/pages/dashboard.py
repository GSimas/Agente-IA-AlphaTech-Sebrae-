"""
Dashboard.py — AlphaTech | Painel Executivo de Inteligência Financeira
Arquivo: src/pages/Dashboard.py
"""

import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================

st.set_page_config(
    page_title="AlphaTech | Dashboard Executivo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# PALETA DE CORES SEMÂNTICAS (Apenas para gráficos)
# ==============================================================================
# Usamos cores que funcionam bem tanto no Light quanto no Dark mode

COR_SEMANTICA = {
    "verde": "#27AE60",
    "amarelo": "#F1C40F",
    "vermelho": "#E74C3C",
    "azul_claro": "#3498DB",
    "azul_escuro": "#2980B9",
    "roxo": "#9B59B6",
    "cinza": "#95A5A6",
}

COR_RISCO = {
    "Alto": COR_SEMANTICA["vermelho"],
    "Médio": COR_SEMANTICA["amarelo"],
    "Baixo": COR_SEMANTICA["verde"],
}

COR_UNIDADE = {
    "Consultoria": COR_SEMANTICA["azul_escuro"],
    "Software": COR_SEMANTICA["roxo"],
    "Treinamentos": COR_SEMANTICA["azul_claro"],
}

# ==============================================================================
# CSS CUSTOMIZADO (Adaptável ao Tema do Streamlit)
# ==============================================================================

st.markdown(
    """
    <style>
    /* Usa as variáveis nativas do Streamlit para suportar Light/Dark Mode automaticamente */
    .kpi-card {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--border-color); /* Borda sutil nativa */
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        height: 138px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }
    .kpi-icon  { font-size: 1.4rem; margin-bottom: 4px; }
    .kpi-label {
        font-size: 0.70rem; font-weight: 700;
        letter-spacing: 0.09em; text-transform: uppercase;
        color: var(--text-color); opacity: 0.7; margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.65rem; font-weight: 800;
        line-height: 1; color: var(--text-color);
    }
    .kpi-delta { font-size: 0.73rem; margin-top: 5px; opacity: 0.8; }
    .kpi-delta.pos  { color: #27AE60; font-weight: bold; } /* Verde universal */
    .kpi-delta.neg  { color: #E74C3C; font-weight: bold; } /* Vermelho universal */
    .kpi-delta.warn { color: #F39C12; font-weight: bold; } /* Laranja universal */

    .section-title {
        font-size: 0.75rem; font-weight: 700;
        letter-spacing: 0.13em; text-transform: uppercase;
        color: var(--text-color); opacity: 0.8;
        padding: 4px 0 10px 0;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 14px;
    }
    .empty-state {
        background-color: var(--secondary-background-color);
        border: 1px dashed var(--border-color);
        border-radius: 10px;
        padding: 40px; text-align: center;
        color: var(--text-color); opacity: 0.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# CAMINHO DO BANCO DE DADOS
# ==============================================================================

_DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))  # src/pages/
_RAIZ = os.path.abspath(os.path.join(_DIR_ATUAL, "..", ".."))  # raiz do projeto
DB_PATH = os.path.join(_RAIZ, "data", "banco_financeiro.db")


# ==============================================================================
# CARREGAMENTO DE DADOS
# ==============================================================================


@st.cache_data(ttl=300, show_spinner=False)
def carregar_dados() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT * FROM resumo_financeiro_enriquecido ORDER BY mes, unidade_negocio",
            conn,
        )
        conn.close()

        if df.empty:
            return df

        df["mes_dt"] = pd.to_datetime(df["mes"], format="%Y-%m")
        df["mes_label"] = df["mes_dt"].dt.strftime("%b/%Y")
        ordem_meses = df.sort_values("mes_dt")["mes_label"].unique().tolist()
        df["mes_label"] = pd.Categorical(
            df["mes_label"], categories=ordem_meses, ordered=True
        )

        df["meta_atingida"] = df["status_meta_receita"].str.strip() == "Atingida"
        df["margem_perc"] = (df["margem_realizada_perc"] * 100).round(2)
        df["meta_margem_perc"] = (df["meta_margem"] * 100).round(2)

        df["nivel_de_risco"] = pd.Categorical(
            df["nivel_de_risco"],
            categories=["Alto", "Médio", "Baixo"],
            ordered=True,
        )
        return df

    except Exception as exc:
        st.error(f"❌ Falha ao carregar dados: `{exc}`")
        return pd.DataFrame()


# ==============================================================================
# HELPERS
# ==============================================================================


def fmt_reais(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_perc(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}%"


def vazio(msg: str = "Sem dados para os filtros selecionados.") -> None:
    st.markdown(f'<div class="empty-state">📭 {msg}</div>', unsafe_allow_html=True)


def card_kpi(icone, label, valor, delta="", delta_tipo="pos") -> None:
    delta_html = f'<div class="kpi-delta {delta_tipo}">{delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon">{icone}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{valor}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# GRÁFICOS (Sem template fixo, o Streamlit aplicará o tema nativo)
# ==============================================================================


def fig_linha_receita_vs_meta(df: pd.DataFrame) -> go.Figure:
    agg = (
        df.groupby("mes_label", observed=True)
        .agg(
            receita=("receita_total_realizada", "sum"),
            meta=("meta_receita_liquida", "sum"),
        )
        .reset_index()
    )

    fig = go.Figure()

    # Área entre as curvas (transparente)
    fig.add_trace(
        go.Scatter(
            x=list(agg["mes_label"]) + list(reversed(list(agg["mes_label"]))),
            y=list(agg["receita"]) + list(reversed(list(agg["meta"]))),
            fill="toself",
            fillcolor="rgba(52, 152, 219, 0.1)",  # Azul com 10% de opacidade
            line=dict(color="rgba(255,255,255,0)"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=agg["mes_label"],
            y=agg["meta"],
            name="Meta de Receita",
            mode="lines+markers",
            line=dict(color=COR_SEMANTICA["cinza"], width=2, dash="dash"),
            marker=dict(symbol="diamond", size=8, color=COR_SEMANTICA["cinza"]),
            hovertemplate="<b>Meta</b><br>%{x}: R$ %{y:,.0f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=agg["mes_label"],
            y=agg["receita"],
            name="Receita Realizada",
            mode="lines+markers",
            line=dict(color=COR_SEMANTICA["azul_claro"], width=3),
            marker=dict(size=9, color=COR_SEMANTICA["azul_claro"]),
            hovertemplate="<b>Realizado</b><br>%{x}: R$ %{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Evolução da Receita: Realizado vs Meta",
        xaxis_title="Período",
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=340,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def fig_barras_unidade(df: pd.DataFrame) -> go.Figure:
    agg = (
        df.groupby(["mes_label", "unidade_negocio"], observed=True)
        .agg(
            receita=("receita_total_realizada", "sum"),
            meta=("meta_receita_liquida", "sum"),
        )
        .reset_index()
    )

    fig = go.Figure()
    for unidade in agg["unidade_negocio"].unique():
        d = agg[agg["unidade_negocio"] == unidade]
        cor = COR_UNIDADE.get(unidade, COR_SEMANTICA["cinza"])

        fig.add_trace(
            go.Bar(
                name=f"{unidade} — Real",
                x=d["mes_label"],
                y=d["receita"],
                marker_color=cor,
                opacity=0.9,
                hovertemplate=f"<b>{unidade}</b><br>Realizado: R$ %{{y:,.0f}}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                name=f"{unidade} — Meta",
                x=d["mes_label"],
                y=d["meta"],
                marker_color=cor,
                opacity=0.3,
                marker_pattern_shape="/",
                hovertemplate=f"<b>{unidade}</b><br>Meta: R$ %{{y:,.0f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Receita por Unidade de Negócio: Real vs Meta",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.05,
        xaxis_title="Período",
        yaxis_title="Receita (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=340,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def fig_donut_risco(df: pd.DataFrame) -> go.Figure:
    contagem = df["nivel_de_risco"].value_counts().reset_index()
    contagem.columns = ["nivel", "qtd"]
    contagem["nivel"] = pd.Categorical(
        contagem["nivel"], categories=["Alto", "Médio", "Baixo"], ordered=True
    )
    contagem = contagem.sort_values("nivel")
    cores = [COR_RISCO.get(str(n), COR_SEMANTICA["cinza"]) for n in contagem["nivel"]]

    fig = go.Figure(
        go.Pie(
            labels=contagem["nivel"],
            values=contagem["qtd"],
            hole=0.60,
            marker=dict(colors=cores),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Qtd: %{value}<br>%{percent}<extra></extra>",
            direction="clockwise",
            sort=False,
        )
    )

    fig.update_layout(
        title="Distribuição do Nível de Risco",
        annotations=[
            dict(
                text=f"<b>{len(df)}</b><br><span style='font-size:10px'>registros</span>",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
        ],
        legend=dict(orientation="v", x=0.98, y=0.5, xanchor="right"),
        height=340,
        margin=dict(l=20, r=20, t=50, b=40),
    )
    return fig


def fig_heatmap_margem(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot_table(
        index="unidade_negocio",
        columns="mes_label",
        values="margem_perc",
        aggfunc="mean",
        observed=True,
    )
    colunas = sorted(pivot.columns, key=lambda x: pd.to_datetime(x, format="%b/%Y"))
    pivot = pivot[colunas]

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="RdYlGn",  # Escala nativa Red-Yellow-Green
            zmin=0,
            zmax=100,
            text=pivot.values,
            texttemplate="%{text:.1f}%",
            hoverongaps=False,
            hovertemplate="<b>%{y}</b> — %{x}<br>Margem: %{z:.1f}%<extra></extra>",
            colorbar=dict(ticksuffix="%", len=0.85),
            xgap=2,
            ygap=2,
        )
    )

    fig.update_layout(
        title="Heatmap de Margem Realizada (%) — Unidade × Período",
        height=270,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


# ==============================================================================
# CABEÇALHO
# ==============================================================================

col_logo, col_tit = st.columns([1, 11])
with col_logo:
    st.markdown(
        "<div style='font-size:2.8rem;padding-top:6px'>📊</div>", unsafe_allow_html=True
    )
with col_tit:
    st.markdown(
        """
        <div>
            <h1 style='margin:0;font-size:1.7rem;font-weight:800;'>AlphaTech — Painel Executivo Financeiro</h1>
            <p style='margin:2px 0 0; opacity:0.7; font-size:0.80rem;'>
                Business Intelligence em tempo real &nbsp;·&nbsp; Fonte: <code>banco_financeiro.db</code>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)

# ==============================================================================
# CARREGAMENTO
# ==============================================================================

with st.spinner("Conectando ao banco de dados..."):
    df_raw = carregar_dados()

if df_raw.empty:
    st.error("❌ **Banco de dados não encontrado ou vazio.**")
    st.stop()

# ==============================================================================
# SIDEBAR — FILTROS
# ==============================================================================

with st.sidebar:
    st.markdown("<h2>🔧 Filtros</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.8rem; opacity:0.7'>Todos os gráficos reagem aos filtros.</p>",
        unsafe_allow_html=True,
    )

    meses_labels = sorted(
        df_raw["mes_label"].cat.categories.tolist(),
        key=lambda x: pd.to_datetime(x, format="%b/%Y"),
    )
    sel_meses = st.multiselect(
        "📅 Período (Mês)", options=meses_labels, default=meses_labels
    )

    unidades = sorted(df_raw["unidade_negocio"].unique().tolist())
    sel_unidades = st.multiselect(
        "🏢 Unidade de Negócio", options=unidades, default=unidades
    )

    riscos = [
        r
        for r in ["Alto", "Médio", "Baixo"]
        if r in df_raw["nivel_de_risco"].cat.categories.tolist()
    ]
    sel_riscos = st.multiselect("⚠️ Nível de Risco", options=riscos, default=riscos)

    st.markdown("---")
    if st.button("🔄 Recarregar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ==============================================================================
# FILTRAGEM
# ==============================================================================

df = df_raw[
    df_raw["mes_label"].isin(sel_meses)
    & df_raw["unidade_negocio"].isin(sel_unidades)
    & df_raw["nivel_de_risco"].isin(sel_riscos)
].copy()

if df.empty:
    vazio("Nenhum dado para os filtros selecionados. Ajuste na barra lateral.")
    st.stop()

# ==============================================================================
# KPI CARDS
# ==============================================================================

st.markdown(
    '<div class="section-title">Indicadores Estratégicos</div>', unsafe_allow_html=True
)

receita_total = df["receita_total_realizada"].sum()
margem_media = df["margem_perc"].mean()
ebitda_total = df["ebitda_realizado"].sum()
n_reg = len(df)
n_metas = int(df["meta_atingida"].sum())
pct_metas = (n_metas / n_reg * 100) if n_reg else 0
desvio_receita = receita_total - df["meta_receita_liquida"].sum()
pct_ebitda_rec = (ebitda_total / receita_total * 100) if receita_total else 0

k1, k2, k3, k4 = st.columns(4)

with k1:
    card_kpi(
        "💰",
        "Receita Total Acumulada",
        fmt_reais(receita_total),
        delta=f"{'▲' if desvio_receita >= 0 else '▼'} {fmt_reais(abs(desvio_receita))} vs meta",
        delta_tipo="pos" if desvio_receita >= 0 else "neg",
    )
with k2:
    tipo_margem = (
        "pos" if margem_media >= 40 else ("warn" if margem_media >= 25 else "neg")
    )
    card_kpi(
        "📈",
        "Margem Média Realizada",
        fmt_perc(margem_media),
        delta="Média de todas as unidades",
        delta_tipo=tipo_margem,
    )
with k3:
    tipo_meta = "pos" if pct_metas >= 60 else ("warn" if pct_metas >= 40 else "neg")
    card_kpi(
        "🎯",
        "Metas de Receita Batidas",
        fmt_perc(pct_metas),
        delta=f"{n_metas} de {n_reg} registros",
        delta_tipo=tipo_meta,
    )
with k4:
    card_kpi(
        "⚡",
        "EBITDA Total",
        fmt_reais(ebitda_total),
        delta=f"{fmt_perc(pct_ebitda_rec)} sobre a receita",
        delta_tipo="pos" if ebitda_total > 0 else "neg",
    )

st.markdown("<div style='margin-bottom:22px'></div>", unsafe_allow_html=True)

# ==============================================================================
# GRÁFICOS E TABELA
# ==============================================================================

st.markdown(
    '<div class="section-title">Desempenho Temporal & Perfil de Risco</div>',
    unsafe_allow_html=True,
)
col_linha, col_donut = st.columns([3, 1.5], gap="medium")

with col_linha:
    st.plotly_chart(
        fig_linha_receita_vs_meta(df), use_container_width=True, theme="streamlit"
    )
with col_donut:
    st.plotly_chart(fig_donut_risco(df), use_container_width=True, theme="streamlit")

st.markdown(
    '<div class="section-title">Análise por Unidade de Negócio</div>',
    unsafe_allow_html=True,
)
col_barras, col_heat = st.columns([1.65, 1], gap="medium")

with col_barras:
    st.plotly_chart(fig_barras_unidade(df), use_container_width=True, theme="streamlit")
with col_heat:
    st.plotly_chart(fig_heatmap_margem(df), use_container_width=True, theme="streamlit")

st.markdown(
    '<div class="section-title">Detalhamento dos Registros</div>',
    unsafe_allow_html=True,
)

with st.expander("🔍 Expandir tabela de dados filtrados", expanded=False):
    df_exib = df[
        [
            "mes_label",
            "unidade_negocio",
            "receita_total_realizada",
            "meta_receita_liquida",
            "custo_total_realizado",
            "margem_perc",
            "meta_margem_perc",
            "ebitda_realizado",
            "variacao_receita_mom",
            "desvio_receita",
            "status_meta_receita",
            "nivel_de_risco",
        ]
    ].copy()

    df_exib.columns = [
        "Período",
        "Unidade",
        "Receita Real (R$)",
        "Meta Receita (R$)",
        "Custo Total (R$)",
        "Margem Real (%)",
        "Meta Margem (%)",
        "EBITDA (R$)",
        "Var. MoM",
        "Desvio Meta (R$)",
        "Status Meta",
        "Nível de Risco",
    ]

    for col in [
        "Receita Real (R$)",
        "Meta Receita (R$)",
        "Custo Total (R$)",
        "EBITDA (R$)",
        "Desvio Meta (R$)",
    ]:
        df_exib[col] = df_exib[col].apply(
            lambda v: fmt_reais(v) if pd.notna(v) else "—"
        )
    df_exib["Margem Real (%)"] = df_exib["Margem Real (%)"].apply(
        lambda v: fmt_perc(v) if pd.notna(v) else "—"
    )
    df_exib["Meta Margem (%)"] = df_exib["Meta Margem (%)"].apply(
        lambda v: fmt_perc(v) if pd.notna(v) else "—"
    )
    df_exib["Var. MoM"] = df_exib["Var. MoM"].apply(
        lambda v: f"{v:+.1%}" if pd.notna(v) else "—"
    )

    # Correção do pandas > 2.1 usando .map() em vez de .applymap()
    def cor_status(v):
        return "color: #27AE60" if v == "Atingida" else "color: #F39C12"

    def cor_risco(v):
        return f"color: {COR_RISCO.get(str(v), '#95A5A6')}; font-weight: 700"

    styled = (
        df_exib.style.map(cor_status, subset=["Status Meta"])
        .map(cor_risco, subset=["Nível de Risco"])
        .hide(axis="index")
    )
    st.dataframe(styled, use_container_width=True, height=300)

    col_dl, _ = st.columns([1.2, 6])
    with col_dl:
        st.download_button(
            label="⬇️ Exportar CSV",
            data=df_exib.to_csv(index=False).encode("utf-8-sig"),
            file_name="alphatech_dashboard.csv",
            mime="text/csv",
            use_container_width=True,
        )
