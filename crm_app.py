import streamlit as st
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, db
import json
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="CRM Inteligente para WhatsApp")
st.title("🤖 CRM Inteligente para WhatsApp 🤖")
st.write("A memória viva do seu suporte ao cliente via WhatsApp.")

# --- INICIALIZAÇÃO SEGURA E CORRETA DO FIREBASE ---
@st.cache_resource
def init_firebase():
    """Inicializa a conexão com o Firebase usando a secção [firebase] dos segredos."""
    try:
        # Pega o dicionário inteiro da secção [firebase] nos segredos
        firebase_creds_dict = st.secrets["firebase"]
        
        # Pega a URL do banco de dados do segredo principal
        db_url = st.secrets["databaseURL"]
        
        cred = credentials.Certificate(firebase_creds_dict)

        # Evita reinicializar o app se ele já estiver rodando
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred, {'databaseURL': db_url})
        return True
    except Exception as e:
        st.error(f"Erro CRÍTICO ao inicializar o Firebase: {e}. Verifique a formatação da secção [firebase] e do 'databaseURL' nos seus 'Secrets'.")
        return False

# --- INICIALIZAÇÃO SEGURA DA API DO GEMINI ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"Erro ao configurar a API do Google: {e}. Verifique a sua chave GOOGLE_API_KEY nos 'Secrets'.")
    st.stop()

# Só continua se o Firebase inicializar corretamente
if not init_firebase():
    st.stop()

# --- FUNÇÕES DE AJUDA PARA LER/SALVAR NO FIREBASE ---
def carregar_dados():
    ref = db.reference('/')
    data = ref.get()
    return data if data else {}

def salvar_dados(dados):
    ref = db.reference('/')
    ref.set(dados)

# --- RESTO DO CÓDIGO (sem alterações) ---
dados_clientes = carregar_dados()

st.sidebar.header("Clientes Cadastrados")
with st.sidebar.form("novo_cliente_form", clear_on_submit=True):
    novo_cliente_numero = st.text_input("Número do Novo Cliente (ex: +5511...)", key="novo_numero")
    novo_cliente_nome = st.text_input("Nome do Novo Cliente", key="novo_nome")
    submitted = st.form_submit_button("Adicionar Novo Cliente")
    if submitted:
        if novo_cliente_numero and novo_cliente_nome:
            numero_formatado = ''.join(filter(str.isdigit, novo_cliente_numero))
            if not numero_formatado.startswith('+'):
                 numero_formatado = '+' + numero_formatado
            if numero_formatado not in dados_clientes:
                dados_clientes[numero_formatado] = {
                    "nome_cliente": novo_cliente_nome,
                    "resumo_inteligente": "Cliente recém-cadastrado. Nenhum histórico.",
                    "problemas_abertos": {},
                    "problemas_resolvidos": {}
                }
                salvar_dados(dados_clientes)
                st.sidebar.success(f"Cliente {novo_cliente_nome} adicionado!")
            else:
                st.sidebar.error("Cliente já existe!")
        else:
            st.sidebar.error("Por favor, preencha o número e o nome.")

lista_nomes = [data['nome_cliente'] for data in dados_clientes.values()]
if not lista_nomes:
    st.info("Nenhum cliente cadastrado. Adicione um cliente na barra lateral para começar.")
    st.stop()

nome_cliente_selecionado = st.sidebar.selectbox("Selecione um Cliente", options=sorted(lista_nomes))

numero_cliente_selecionado = next((num for num, data in dados_clientes.items() if data['nome_cliente'] == nome_cliente_selecionado), None)
cliente_atual = dados_clientes.get(numero_cliente_selecionado, {})

col1, col2 = st.columns(2)
with col1:
    st.header(f"Atualizar Dossiê de {cliente_atual.get('nome_cliente', 'N/A')}")
    nova_conversa = st.text_area("Cole aqui a nova conversa para análise", height=300, key=f"conversa_{numero_cliente_selecionado}")
    if st.button("Analisar e Atualizar Dossiê", use_container_width=True):
        if not nova_conversa:
            st.warning("Por favor, cole a conversa para análise.")
        else:
            with st.spinner("A IA está a analisar a conversa..."):
                try:
                    prompt = f"""
                    Você é um sistema de CRM inteligente. Sua tarefa é atualizar o dossiê de um cliente... (o resto do prompt é igual)
                    """
                    model = genai.GenerativeModel('gemini-1.0-pro')
                    response = model.generate_content(prompt)
                    resposta_limpa = response.text.strip().replace("```json", "").replace("```", "")
                    dossie_atualizado = json.loads(resposta_limpa)
                    dados_clientes[numero_cliente_selecionado] = dossie_atualizado
                    salvar_dados(dados_clientes)
                    st.success("Dossiê atualizado com sucesso no Firebase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ocorreu um erro na análise da IA: {e}")
                    try: st.error(f"Resposta da IA: {response.text}")
                    except: pass
with col2:
    st.header(f"Dossiê de: {cliente_atual.get('nome_cliente', 'N/A')}")
    st.caption(f"Contato: {numero_cliente_selecionado}")
    st.subheader("📄 Resumo Inteligente")
    st.info(cliente_atual.get('resumo_inteligente', 'N/A'))
    st.subheader("🔥 Problemas em Aberto")
    problemas_abertos = cliente_atual.get('problemas_abertos', {})
    if not problemas_abertos:
        st.success("Nenhuma pendência! ✅")
    else:
        for id_problema, detalhes in problemas_abertos.items():
            st.expander(f"**{id_problema.replace('_', ' ').capitalize()}:** {detalhes.get('descricao', 'Sem descrição')}").write(detalhes)
    st.subheader("✅ Histórico de Problemas Resolvidos")
    problemas_resolvidos = cliente_atual.get('problemas_resolvidos', {})
    if not problemas_resolvidos:
        st.write("Nenhum problema resolvido registrado.")
    else:
        for id_problema, detalhes in problemas_resolvidos.items():
            st.expander(f"**{id_problema.replace('_', ' ').capitalize()}:** {detalhes.get('descricao', 'Sem descrição')}").write(detalhes)

