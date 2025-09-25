import streamlit as st
import google.generativeai as genai
import json
import os
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="CRM Inteligente para WhatsApp")
st.title(" 🤖CRM Inteligente para WhatsApp 🤖")
st.write("A memória viva do seu suporte ao cliente via WhatsApp.")

# --- Funções de Ajuda para Ler/Salvar o BD ---
DB_FILE = "clientes.json"

def carregar_dados():
  """Carrega os dados dos clientes do arquivo JSON"""
  if not os.path.exists(DB_FILE):
    return {}
  with open(DB_FILE, "r", encoding="utf-8") as f:
    return json.load(f)
  
def salvar_dados(dados):
  """Salva os dados dos clientes no arquivo JSON"""
  with open(DB_FILE, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=4)

dados_clientes = carregar_dados()

st.sidebar.header("Clientes Cadastrados")

novo_cliente_numero = st.sidebar.text_input("Número do Novo Cliente (ex: +5511...)", key="novo_numero")
novo_cliente_nome = st.sidebar.text_input("Nome do Novo Cliente", key="novo_nome")
if st.sidebar.button("Adicionar Novo Cliente"):
  if novo_cliente_numero and novo_cliente_nome:
    if novo_cliente_numero not in dados_clientes:
      dados_clientes[novo_cliente_numero] = {
        "nome_cliente": novo_cliente_nome,
        "resumo_inteligente": "Cliente recém-cadastrado. Nenhum histórico.",
        "problemas_abertos": {},
        "problemas_resolvidos": {}
      }
      salvar_dados(dados_clientes)
      st.sidebar.success(f"Cliente {novo_cliente_nome} adicionado com sucesso!")
    else:
      st.sidebar.error("Cliente já existe!")
  else:
    st.sidebar.error("Por favor, preencha ambos os campos.")

lista_nomes = [data['nome_cliente'] for data in dados_clientes.values()]
if not lista_nomes:
  st.info("Nenhum cliente cadastrado. Adicione um cliente na barra lateral para começar.")
  st.stop()

nome_cliente_selecionado = st.sidebar.selectbox(
  "Selecione um Cliente para ver ou atualizar",
  options=lista_nomes,
  index=0
)

numero_cliente_selecionado = None
for numero, data in dados_clientes.items():
  if data['nome_cliente'] == nome_cliente_selecionado:
    numero_cliente_selecionado = numero
    break

cliente_atual = dados_clientes[numero_cliente_selecionado]

col1, col2 = st.columns(2)
with col1:
  st.header(f"Atualizar Dossiê de {cliente_atual['nome_cliente']}")
  try:
      genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
  except Exception as e:
      st.error("Chave de API não configurada. Peça ao administrador para configurar os 'Secrets' do Streamlit.")
      st.stop()

  nova_conversa = st.text_area(
    "Cole aqui a nova conversa do WhatsApp para análise",
    height=300
  )

  if st.button("Analisar e Atualizar Dossiê", use_container_width=True):
    if not api_key:
      st.error("Por favor, insira sua chave de API.")
    elif not nova_conversa:
      st.warning("Por favor, cole a conversa para análise.")
    else:
      with st.spinner("A IA está lendo o histórico, analisando a nova conversa e atualizando o dossiê..."):
        try:
          genai.configure(api_key=api_key)

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
          1.  **Identifique Novos Problemas:** Se a conversa menciona um problema que não está em "problemas_abertos", crie um novo problema com um ID único (ex: "problema_1", "problema_2", etc), uma descrição clara e o status "aberto".
          2.  **Identifique Resoluções:** Se a conversa indica que um problema que estava em "problemas_abertos" foi resolvido, mova-o para "problemas_resolvidos".
          3.  **Atualize o Resumo:** Reescreva o campo "resumo_inteligente" para refletir o estado atual do cliente e os últimos acontecimentos.
          4.  **Mantenha o Histórico:** Nunca apague problemas antigos de "problemas_resolvidos". Apenas adicione novos.
          5.  **Formato de Saída:** Sua resposta deve ser APENAS o código JSON do dossiê atualizado. Não inclua texto explicativo antes ou depois.
          """

          model = genai.GenerativeModel('gemini-pro')
          response = model.generate_content(prompt)

          resposta_limpa = response.text.strip().replace("```json", "").replace("```", "")
          dossie_atualizado = json.loads(resposta_limpa)
          dados_clientes[numero_cliente_selecionado] = dossie_atualizado
          salvar_dados(dados_clientes)

          st.success("Dossiê atualizado com sucesso!")
          st.rerun()
        except Exception as e:
          st.error(f"Ocorreu um erro na análise da IA: {e}")
          st.error(f"Resposta recebida da IA (pode ajudar a depurar): {response.text}")

with col2:
    st.header(f"Dossiê de: {cliente_atual['nome_cliente']}")
    st.caption(f"Contato: {numero_cliente_selecionado} | Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    st.subheader("📄 Resumo Inteligente")
    st.info(cliente_atual.get('resumo_inteligente', 'N/A'))
    
    st.subheader("🔥 Problemas em Aberto")
    problemas_abertos = cliente_atual.get('problemas_abertos', {})
    if not problemas_abertos:
        st.success("Nenhuma pendência! ✅")
    else:
        for id_problema, detalhes in problemas_abertos.items():
            with st.expander(f"**{id_problema.replace('_', ' ').capitalize()}:** {detalhes.get('descricao', 'Sem descrição')}"):
                st.write(detalhes)
    
    st.subheader("✅ Histórico de Problemas Resolvidos")
    problemas_resolvidos = cliente_atual.get('problemas_resolvidos', {})
    if not problemas_resolvidos:
        st.write("Nenhum problema resolvido registrado.")
    else:
        for id_problema, detalhes in problemas_resolvidos.items():
            with st.expander(f"**{id_problema.replace('_', ' ').capitalize()}:** {detalhes.get('descricao', 'Sem descrição')}"):

                st.write(detalhes)
