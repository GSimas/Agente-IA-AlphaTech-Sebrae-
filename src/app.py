import streamlit as st
from agente import (
    inicializar_agente,
    gerar_relatorio_executivo,
    gerar_relatorio_unidade,
    gerar_relatorio_riscos,
    executar_pergunta,
)

# Configuração da página (deve ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="AlphaTech | Agente Financeiro IA", page_icon="📊", layout="wide"
)

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

    if st.button("🏢 Relatório por Unidade", use_container_width=True):
        st.session_state.messages.append(
            {"role": "user", "content": "Gere o Relatório por Unidade de Negócio."}
        )
        with st.spinner("Consolidando métricas das unidades..."):
            resposta = gerar_relatorio_unidade(st.session_state.agente)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

    if st.button("⚠️ Relatório de Riscos", use_container_width=True):
        st.session_state.messages.append(
            {"role": "user", "content": "Gere o Relatório de Riscos Financeiros."}
        )
        with st.spinner("Cruzando desvios com políticas de risco..."):
            resposta = gerar_relatorio_riscos(st.session_state.agente)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

    st.markdown("---")
    st.caption("AlphaTech IA © 2026")

# --- ÁREA PRINCIPAL (CHATBOT INTERATIVO) ---
st.title("🤖 Chatbot Financeiro - AlphaTech")
st.write(
    "Faça perguntas livres sobre receitas, custos, metas ou diretrizes da empresa."
)

# Renderiza o histórico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Captura a entrada do usuário em linguagem natural
if prompt := st.chat_input(
    "Ex: Qual unidade teve a pior margem e qual a recomendação para ela?"
):
    # Exibe a pergunta do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Gera e exibe a resposta do Agente
    with st.chat_message("assistant"):
        with st.spinner("Analisando bases de dados e diretrizes..."):
            try:
                resposta = executar_pergunta(st.session_state.agente, prompt)
                st.markdown(resposta)
                # Salva a resposta no histórico
                st.session_state.messages.append(
                    {"role": "assistant", "content": resposta}
                )
            except Exception as e:
                erro_msg = f"Ocorreu um erro ao processar sua solicitação: {e}"
                st.error(erro_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": erro_msg}
                )
