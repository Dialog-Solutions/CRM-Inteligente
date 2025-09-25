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

# --- INICIALIZAÇÃO SEGURA DO FIREBASE (SÓ RODA UMA VEZ) ---
@st.cache_resource
def init_firebase():
    """Inicializa a conexão com o Firebase usando os segredos do Streamlit."""
    try:
        firebase_creds_dict = st.secrets["firebase"]
        cred = credentials.Certificate(firebase_creds_dict)
        
        # Evita reinicializar o app se ele já estiver rodando
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred, {
                'databaseURL': firebase_creds_dict["databaseURL"]
            })
        return True
    except Exception as e:
        st.error(f"Erro ao inicializar o Firebase: {e}. Verifique a configuração dos seus 'Secrets'.")
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

# --- NOVAS FUNÇÕES DE AJUDA PARA LER/SALVAR NO FIREBASE ---
def carregar_dados():
    """Carrega os dados dos clientes do Firebase."""
    ref = db.reference('/')
    data = ref.get()
    return data if data else {}

def salvar_dados(dados):
    """Salva os dados dos clientes no Firebase."""
    ref = db.reference('/')
    ref.set(dados)

# --- Carregar Dados dos Clientes ---
dados_clientes = carregar_dados()

# --- Barra Lateral (Sidebar) para Gerenciar Clientes ---
st.sidebar.header("Clientes Cadastrados")

with st.sidebar.form("novo_cliente_form", clear_on_submit=True):
    novo_cliente_numero = st.text_input("Número do Novo Cliente (ex: +5511...)", key="novo_numero")
    novo_cliente_nome = st.text_input("Nome do Novo Cliente", key="novo_nome")
    submitted = st.form_submit_button("Adicionar Novo Cliente")
    if submitted:
        if novo_cliente_numero and novo_cliente_nome:
            # Garante que o número não contenha caracteres indesejados e comece com '+'
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

# --- Seleção de Cliente na Sidebar ---
lista_nomes = [data['nome_cliente'] for data in dados_clientes.values()]
if not lista_nomes:
    st.info("Nenhum cliente cadastrado. Adicione um cliente na barra lateral para começar.")
    st.stop()

nome_cliente_selecionado = st.sidebar.selectbox(
    "Selecione um Cliente",
    options=sorted(lista_nomes)
)

# Encontra os dados do cliente selecionado
numero_cliente_selecionado = None
for numero, data in dados_clientes.items():
    if data['nome_cliente'] == nome_cliente_selecionado:
        numero_cliente_selecionado = numero
        break

cliente_atual = dados_clientes[numero_cliente_selecionado]

# --- Layout Principal com Duas Colunas ---
col1, col2 = st.columns(2)

# Coluna 1: Área de Atualização
with col1:
    st.header(f"Atualizar Dossiê de {cliente_atual['nome_cliente']}")
    nova_conversa = st.text_area("Cole aqui a nova conversa para análise", height=300, key=f"conversa_{numero_cliente_selecionado}")
    
    if st.button("Analisar e Atualizar Dossiê", use_container_width=True):
        if not nova_conversa:
            st.warning("Por favor, cole a conversa para análise.")
        else:
            with st.spinner("A IA está a conectar-se ao Firebase, a ler o histórico e a analisar a nova conversa..."):
                try:
                    prompt = f"""
                    Você é um sistema de CRM inteligente. Sua tarefa é atualizar o dossiê de um cliente.

                    **Dossiê Atual do Cliente (em formato JSON):**
                    {json.dumps(cliente_atual, ensure_ascii=False, indent=2)}

                    **Nova Transcrição da Conversa do WhatsApp:**
                    ---
                    {nova_conversa}
                    ---

                    **Sua Tarefa:**
                    Analise a "Nova Transcrição" levando em conta o "Dossiê Atual".
                    Retorne um NOVO dossiê completo em formato JSON, aplicando as seguintes regras:
                    1.  **Identifique Novos Problemas:** Se a conversa menciona um problema que não está em "problemas_abertos", crie um novo problema com um ID único (ex: "problema_X", onde X é o próximo número disponível), uma descrição clara e o status "aberto".
                    2.  **Identifique Resoluções:** Se a conversa indica que um problema que estava em "problemas_abertos" foi resolvido, mova-o para "problemas_resolvidos".
                    3.  **Atualize o Resumo:** Reescreva o campo "resumo_inteligente" para refletir o estado atual do cliente e os últimos acontecimentos.
                    4.  **Mantenha o Histórico:** Nunca apague problemas antigos de "problemas_resolvidos". Apenas adicione novos.
                    5.  **Formato de Saída:** Sua resposta deve ser APENAS o código JSON do dossiê atualizado. Não inclua texto explicativo antes ou depois.
                    """
                    # NOME DO MODELO CORRETO E COMPATÍVEL
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
                    try:
                        st.error(f"Resposta recebida da IA: {response.text}")
                    except NameError:
                        st.error("Não foi possível obter uma resposta da IA. Verifique as configurações e a chave de API.")

# Coluna 2: Visualização do Dossiê
with col2:
    st.header(f"Dossiê de: {cliente_atual['nome_cliente']}")
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

