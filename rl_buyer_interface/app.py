import os
import sys
import tempfile
import io
import zipfile
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# Adicionar o diretório atual ao path para garantir importações
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from training_runner import (
        train_single_core_generator,
        train_multi_core_generator,
        run_testing_simulation
    )
except ImportError:
    from rl_buyer_interface.training_runner import (
        train_single_core_generator,
        train_multi_core_generator,
        run_testing_simulation
    )

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="RL Buyer Agent - Eureka Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS: PREMIUM DARK & GLASSMORPHISM ---
st.markdown("""
<style>
    /* Importar Fonte Outfit */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* Configuração Geral de Fontes */
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Tema Escuro customizado */
    .stApp {
        background-color: #0b0d12;
        color: #e5e9f0;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #121620;
        border-right: 1px solid #1f283d;
    }
    
    /* Custom Card container */
    .custom-card {
        background: rgba(30, 37, 53, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    
    /* Header Gradient styling */
    .main-title {
        background: linear-gradient(135deg, #00d2ff 0%, #0066ff 50%, #9b51e0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2.8rem;
        margin-bottom: 5px;
    }
    .subtitle {
        color: #8c9cb3;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }
    
    /* Terminal Console style */
    .console-header {
        background-color: #1a1e29;
        border-radius: 8px 8px 0 0;
        border: 1px solid #2e384e;
        border-bottom: none;
        padding: 8px 15px;
        font-size: 0.85rem;
        color: #00d2ff;
        font-family: monospace;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .console-box {
        background-color: #080a0f;
        border: 1px solid #2e384e;
        border-radius: 0 0 8px 8px;
        padding: 15px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9rem;
        color: #a3be8c;
        height: 350px;
        overflow-y: auto;
        white-space: pre-wrap;
        box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.5);
    }
    
    /* Custom tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-size: 1.1rem;
        font-weight: 600;
        color: #8c9cb3;
        border-bottom-width: 2px;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #00d2ff;
    }
    .stTabs [aria-selected="true"] {
        color: #00d2ff !important;
        border-bottom-color: #00d2ff !important;
    }
    
    /* Metric Card Custom styling */
    .metric-card {
        background: linear-gradient(145deg, #181d2a, #11141e);
        border: 1px solid #222b3d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #00ffaa;
        margin: 5px 0;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #8c9cb3;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# --- UTILS FOR FILE ZIP & DOWNLOADS ---
def create_model_zip_bytes(model_base_path):
    """ Lê os arquivos gerados do modelo e empacota-os num buffer ZIP em memória """
    zip_buffer = io.BytesIO()
    suffixes = ['_actor.pth', '_critic.pth', '_scaler.pth', '_econ_stat.pth']
    found_any = False
    
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for suffix in suffixes:
            file_path = model_base_path + suffix
            if os.path.exists(file_path):
                zip_file.write(file_path, os.path.basename(file_path))
                found_any = True
                
    if not found_any:
        return None
    return zip_buffer.getvalue()

# --- APP LAYOUT ---

# Top Banner Header
col_logo, col_desc = st.columns([1, 12])
with col_desc:
    st.markdown('<h1 class="main-title">RL Buyer Agent - Eureka</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Interface Interativa de Inteligência Artificial para Gestão Automática de Inventário Fruta & Logística</p>', unsafe_allow_html=True)

# ----------------- SIDEBAR: DATA UPLOAD & GLOBAL CONFIG -----------------
with st.sidebar:
    st.markdown("### 📥 Carregar Dataset de Demanda")
    uploaded_file = st.file_uploader(
        "Selecione o arquivo Excel ou CSV com dados de vendas históricas e meteorologia:",
        type=["xlsx", "csv"],
        help="O arquivo deve conter as colunas: real_value, prediction, price, temperature, humidity, ethylene."
    )
    
    st.markdown("---")
    st.markdown("### ⚙️ Configuração Global")
    device_opt = st.selectbox("Hardware de Execução (PyTorch):", ["CPU", "GPU"], index=0)
    device = "cuda" if device_opt == "GPU" and torch.cuda.is_available() else "cpu"
    if device_opt == "GPU" and not torch.cuda.is_available():
        st.warning("Aceleração GPU (CUDA) indisponível. Usando CPU.")
        
    st.markdown("---")
    st.markdown("#### ℹ️ Estrutura do Dataset Esperada")
    st.info(
        "**Variáveis Necessárias:**\n"
        "- `real_value`: Vendas Reais\n"
        "- `prediction`: Procura Prevista\n"
        "- `price`: Preço Unitário\n"
        "- `temperature`: Temperatura do dia\n"
        "- `humidity`: Humidade Relativa\n"
        "- `ethylene`: Concentração Etileno"
    )

# ----------------- SESSION STATE INITS -----------------
if 'train_log' not in st.session_state:
    st.session_state.train_log = ""
if 'test_log' not in st.session_state:
    st.session_state.test_log = ""
if 'trained_model_dir' not in st.session_state:
    st.session_state.trained_model_dir = None
if 'test_completed' not in st.session_state:
    st.session_state.test_completed = False
if 'test_results' not in st.session_state:
    st.session_state.test_results = None

# Verificação inicial se há dataset carregado
if uploaded_file is None:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.warning("👋 Por favor, faça upload de um ficheiro de dataset na barra lateral para começar a interagir com o agente de compras RL.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Carregar o arquivo na memória
@st.cache_data
def load_uploaded_df(file_obj):
    if file_obj.name.endswith('.xlsx'):
        return pd.read_excel(file_obj)
    else:
        return pd.read_csv(file_obj)

df_data = load_uploaded_df(uploaded_file)
st.sidebar.success(f"Dataset carregado com {len(df_data)} dias de registos!")

# Criar arquivo temporário local para a leitura das rotinas do modelo
temp_dataset_path = os.path.join(tempfile.gettempdir(), "uploaded_dataset.xlsx")
df_data.to_excel(temp_dataset_path, index=False)

# ----------------- TABS PRINCIPAIS -----------------
tab_train, tab_test = st.tabs(["🏋️ Treinar Modelo", "🧪 Testar & Fine-Tuning"])

# =====================================================================
# TAB 1: TREINO DO MODELO
# =====================================================================
with tab_train:
    st.markdown("### Treino Offline do Modelo PPO")
    st.markdown("Configure as variáveis de ambiente e os hiperparâmetros mais importantes do algoritmo Proximal Policy Optimization (PPO) abaixo.")
    
    col_split, col_cap = st.columns(2)
    with col_split:
        train_split = st.slider("Percentagem (%) de Dados para Treino:", min_value=30, max_value=90, value=60, step=5,
                                help="Apenas esta fração inicial do dataset será usada para treinar o agente. O restante é reservado para teste.")
    with col_cap:
        max_capacity = st.number_input("Capacidade Máxima do Armazém (unidades):", min_value=100, max_value=5000, value=500, step=100)
        
    st.markdown("#### Hiperparâmetros de RL")
    col_hp1, col_hp2, col_hp3, col_hp4 = st.columns(4)
    with col_hp1:
        lr_act = st.number_input("Learning Rate (Actor):", min_value=1e-5, max_value=1e-2, value=0.0003, format="%.5f")
        lr_crit = st.number_input("Learning Rate (Critic):", min_value=1e-5, max_value=1e-2, value=0.001, format="%.5f")
    with col_hp2:
        gamma = st.number_input("Discount Factor (Gamma):", min_value=0.5, max_value=0.99, value=0.8, format="%.2f")
        eps_clip = st.number_input("PPO Clip Epsilon:", min_value=0.05, max_value=0.4, value=0.2, format="%.2f")
    with col_hp3:
        k_epochs = st.number_input("K-Epochs por update:", min_value=5, max_value=100, value=30, step=5)
        batch_size = st.selectbox("Tamanho do Batch:", [32, 64, 128, 256, 512, 1024, 2048], index=6)
    with col_hp4:
        max_episodes = st.number_input("Total de Episódios (Máximo):", min_value=100, max_value=50000, value=1000, step=500)
        seed = st.number_input("Random Seed:", min_value=1, max_value=99999, value=1337)
        
    st.markdown("#### Configuração de Hardware & Paralelização")
    col_hw1, col_hw2 = st.columns(2)
    with col_hw1:
        num_envs = st.slider("Número de Ambientes Paralelos:", min_value=4, max_value=128, value=64, step=4,
                             help="Quantidade de simulações concorrentes para recolha de trajetórias.")
    with col_hw2:
        core_mode = st.radio("Modo de Processamento:", ["Single-Core (Estável em Cloud)", "Multi-Core (Mais Rápido Localmente)"], index=0)
        
    workers = 4
    if "Multi-Core" in core_mode:
        workers = st.slider("Número de Cores Físicos (Workers):", min_value=2, max_value=16, value=4, step=2)

    # Iniciar Treino
    btn_train = st.button("🚀 Iniciar Treino do Agente", use_container_width=True)
    
    # Contentor de logs
    st.markdown('<div class="console-header">📁 Terminal do PPO Agent - Logs de Treino</div>', unsafe_allow_html=True)
    console_placeholder = st.empty()
    console_placeholder.markdown('<div class="console-box">Agente à espera de comando...</div>', unsafe_allow_html=True)
    
    if btn_train:
        st.session_state.train_log = ""
        temp_model_dir = tempfile.mkdtemp()
        st.session_state.trained_model_dir = temp_model_dir
        
        # Seleciona o gerador de acordo com o modo de cores
        if "Single-Core" in core_mode:
            gen = train_single_core_generator(
                seed=seed,
                excel_path=temp_dataset_path,
                train_split=(train_split / 100.0),
                max_capacity=max_capacity,
                lr_actor=lr_act,
                lr_critic=lr_crit,
                gamma=gamma,
                k_epochs=k_epochs,
                eps_clip=eps_clip,
                batch_size=batch_size,
                max_episodes_total=max_episodes,
                num_envs=num_envs,
                save_dir=temp_model_dir
            )
        else:
            gen = train_multi_core_generator(
                seed=seed,
                excel_path=temp_dataset_path,
                train_split=(train_split / 100.0),
                max_capacity=max_capacity,
                lr_actor=lr_act,
                lr_critic=lr_crit,
                gamma=gamma,
                k_epochs=k_epochs,
                eps_clip=eps_clip,
                batch_size=batch_size,
                max_episodes_total=max_episodes,
                num_envs=num_envs,
                num_workers=workers,
                save_dir=temp_model_dir
            )
            
        progress_bar = st.progress(0.0)
        
        # Consome as linhas do gerador em tempo real
        for log_line in gen:
            st.session_state.train_log += log_line + "\n"
            # Formatar e injetar na caixa de terminal
            console_placeholder.markdown(
                f'<div class="console-box">{st.session_state.train_log}</div>',
                unsafe_allow_html=True
            )
            
            # Atualizar barra de progresso simples
            if "Episodes:" in log_line:
                try:
                    parts = log_line.split("Episodes:")[1].split("/")[0].strip()
                    current_ep = int(parts)
                    pct = min(1.0, current_ep / max_episodes)
                    progress_bar.progress(pct)
                except:
                    pass
        
        progress_bar.progress(1.0)
        st.success("🎉 Treino concluído com sucesso!")
        
    # Exibir o botão de download caso os arquivos já existam
    if st.session_state.trained_model_dir is not None:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("#### 💾 Guardar Ficheiros Finais do Modelo")
        st.write("Transfira o modelo treinado com os pesos do Actor, Critic, Scaler e estatísticas Z-Score compilados num ficheiro ZIP:")
        
        # Gerar o arquivo ZIP em memória
        base_path = os.path.join(st.session_state.trained_model_dir, "ppo_constrained_final")
        zip_bytes = create_model_zip_bytes(base_path)
        
        if zip_bytes is not None:
            st.download_button(
                label="📥 Descarregar Ficheiros de Treino (.ZIP)",
                data=zip_bytes,
                file_name="modelo_ppo_buyer_agente.zip",
                mime="application/zip",
                use_container_width=True
            )
            
            # Exibir gráfico de losses se existir
            plot_path = os.path.join(st.session_state.trained_model_dir, "losses_plot.png")
            if os.path.exists(plot_path):
                st.markdown("---")
                st.markdown("##### Curva de Aprendizagem (Loss Evolution)")
                st.image(plot_path, caption="Gráficos de Losses de Treino (Actor, Critic e Total)", use_container_width=True)
        else:
            st.error("Não foram encontrados ficheiros de pesos do modelo no diretório temporário.")
        st.markdown('</div>', unsafe_allow_html=True)

# =====================================================================
# TAB 2: TESTE E FINE-TUNING DO MODELO
# =====================================================================
with tab_test:
    st.markdown("### Simulação em Produção & Fine-Tuning Contínuo")
    st.markdown("Execute a simulação no período de teste do dataset e avalie o desempenho do RL Agent em tempo real face a estratégias Baseline.")
    
    col_ds, col_model = st.columns(2)
    with col_ds:
        st.markdown('<div class="custom-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("##### 1. Configurar Dados de Teste")
        test_split_option = st.radio(
            "Origem dos dias de teste:",
            ["Usar os restantes (100 - X)% do dataset de treino carregado", "Carregar outro ficheiro com novos dias"]
        )
        
        test_split_val = 0.6
        if "Usar os restantes" in test_split_option:
            test_split_val = train_split / 100.0
            st.info(f"A simulação usará a fração restante dos dados ({100 - train_split}% de {len(df_data)} dias = {int(len(df_data) * (1 - test_split_val))} dias).")
            final_test_dataset_path = temp_dataset_path
        else:
            uploaded_test_file = st.file_uploader(
                "Carregar Dataset de Teste / Futuro:",
                type=["xlsx", "csv"],
                key="test_dataset_uploader"
            )
            if uploaded_test_file is not None:
                df_test = load_uploaded_df(uploaded_test_file)
                st.success(f"Novos dias de teste carregados ({len(df_test)} dias).")
                # Escrever ficheiro temporário para teste
                final_test_dataset_path = os.path.join(tempfile.gettempdir(), "test_dataset.xlsx")
                df_test.to_excel(final_test_dataset_path, index=False)
                test_split_val = 0.0 # Todo o ficheiro novo é usado para o teste
            else:
                st.warning("A aguardar carregamento do ficheiro de teste...")
                st.markdown('</div>', unsafe_allow_html=True)
                st.stop()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_model:
        st.markdown('<div class="custom-card" style="height: 100%;">', unsafe_allow_html=True)
        st.markdown("##### 2. Upload do Modelo Treinado")
        st.write("Faça upload do ficheiro ZIP ou dos ficheiros individuais (.pth) contendo os pesos treinados:")
        
        upload_mode = st.radio("Tipo de upload:", ["Ficheiro ZIP", "Ficheiros Individuais (.pth)"])
        
        temp_load_dir = tempfile.mkdtemp()
        model_loaded_ok = False
        
        if upload_mode == "Ficheiro ZIP":
            zip_model_file = st.file_uploader("Upload do Modelo ZIP:", type=["zip"])
            if zip_model_file is not None:
                try:
                    with zipfile.ZipFile(zip_model_file) as zf:
                        zf.extractall(temp_load_dir)
                    # Verificar se encontramos o ficheiro do ator
                    files_in_dir = os.listdir(temp_load_dir)
                    actor_file = [f for f in files_in_dir if f.endswith('_actor.pth')]
                    if len(actor_file) > 0:
                        base_model_name = actor_file[0].split('_actor.pth')[0]
                        initial_model_base_path = os.path.join(temp_load_dir, base_model_name)
                        model_loaded_ok = True
                        st.success(f"Modelo ZIP descompactado! Identificado: {base_model_name}")
                    else:
                        st.error("O ficheiro ZIP não contém arquivos no formato esperado (*_actor.pth).")
                except Exception as e:
                    st.error(f"Erro ao descompactar o ZIP: {e}")
        else:
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                uploaded_actor = st.file_uploader("Ficheiro Actor (*_actor.pth)", type=["pth"])
                uploaded_scaler = st.file_uploader("Ficheiro Scaler (*_scaler.pth) [Opcional]", type=["pth"])
            with col_a2:
                uploaded_critic = st.file_uploader("Ficheiro Critic (*_critic.pth) [Opcional]", type=["pth"])
                uploaded_econ = st.file_uploader("Ficheiro Econ Stat (*_econ_stat.pth)", type=["pth"])
                
            if uploaded_actor is not None and uploaded_econ is not None:
                # Gravar com sufixos corretos no diretório temporário
                with open(os.path.join(temp_load_dir, "my_model_actor.pth"), "wb") as f:
                    f.write(uploaded_actor.getbuffer())
                with open(os.path.join(temp_load_dir, "my_model_econ_stat.pth"), "wb") as f:
                    f.write(uploaded_econ.getbuffer())
                    
                if uploaded_critic is not None:
                    with open(os.path.join(temp_load_dir, "my_model_critic.pth"), "wb") as f:
                        f.write(uploaded_critic.getbuffer())
                if uploaded_scaler is not None:
                    with open(os.path.join(temp_load_dir, "my_model_scaler.pth"), "wb") as f:
                        f.write(uploaded_scaler.getbuffer())
                        
                initial_model_base_path = os.path.join(temp_load_dir, "my_model")
                model_loaded_ok = True
                st.success("Pesos do Actor e do Econ Stat carregados com sucesso!")
            else:
                st.info("Para correr o teste, faça upload do Actor (*_actor.pth) e do Econ Stat (*_econ_stat.pth).")
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("#### Parâmetros de Simulação e Fine-Tuning")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        s_min = st.number_input("Valor Mínimo Baseline (s):", min_value=1, max_value=500, value=24, help="Desencadeia encomenda no Baseline Min-Max se o stock estimado for inferior a este valor.")
        S_max = st.number_input("Valor Máximo Baseline (S):", min_value=50, max_value=2000, value=60, help="Nível de stock alvo após encomenda no Baseline Min-Max.")
    with col_t2:
        update_interval = st.number_input("Intervalo de Fine-Tuning (dias):", min_value=1, max_value=90, value=15, help="Frequência em dias com que o agente atualiza online os seus pesos com dados reais do mercado.")
        online_batch = st.selectbox("Tamanho do Batch Online:", [16, 32, 64, 128], index=1)
    with col_t3:
        online_lr_act = st.number_input("Online Actor Learning Rate:", min_value=1e-7, max_value=1e-3, value=1e-5, format="%.7f", help="Learning rate ultra baixo para evitar esquecimento catastrófico.")
        online_lr_crit = st.number_input("Online Critic Learning Rate:", min_value=1e-7, max_value=1e-3, value=5e-5, format="%.7f")

    # Botão para correr simulação
    st.markdown("---")
    btn_disabled = not model_loaded_ok
    btn_test = st.button("🏁 Iniciar Teste e Fine-Tuning Contínuo", use_container_width=True, disabled=btn_disabled)
    
    if btn_disabled:
        st.warning("⚠️ O botão de teste está desativado. Por favor, carregue os pesos do modelo (Actor e Econ Stat) primeiro.")

    # Contentores dinâmicos
    col_chart, col_side_logs = st.columns([8, 4])
    with col_chart:
        chart_placeholder = st.empty()
        
    with col_side_logs:
        st.markdown('<div class="console-header">🤖 Logs Diários da Simulação</div>', unsafe_allow_html=True)
        test_console_placeholder = st.empty()
        test_console_placeholder.markdown('<div class="console-box">Simulação parada...</div>', unsafe_allow_html=True)

    if btn_test and model_loaded_ok:
        st.session_state.test_log = ""
        st.session_state.test_completed = False
        
        # Instanciar o gerador da simulação
        sim_gen = run_testing_simulation(
            excel_path=final_test_dataset_path,
            train_split=test_split_val,
            max_capacity=max_capacity,
            initial_model_base_path=initial_model_base_path,
            s_min=s_min,
            S_max=S_max,
            update_interval_days=update_interval,
            online_lr_actor=online_lr_act,
            online_lr_critic=online_lr_crit,
            online_batch_size=online_batch,
            save_dir=temp_load_dir
        )
        
        # Preparar dataframes para a atualização gráfica em tempo real
        plot_data = {
            "Dia": [],
            "RL Agent": [],
            "Min-Max": [],
            "Oracle": [],
            "Real Demand": [],
            "Stock Level": []
        }
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[], y=[], mode='lines', name='RL Agent (Profit Acumulado)', line=dict(color='#00ffaa', width=2.5)))
        fig.add_trace(go.Scatter(x=[], y=[], mode='lines', name='Min-Max Baseline', line=dict(color='#8c9cb3', width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(x=[], y=[], mode='lines', name='Oráculo (God Mode)', line=dict(color='#ffaa00', width=2.0, dash='dash')))
        fig.update_layout(
            title="Evolução Comparativa do Lucro Acumulado em Tempo Real",
            xaxis_title="Dias",
            yaxis_title="Lucro Acumulado (€)",
            paper_bgcolor="#11141e",
            plot_bgcolor="#11141e",
            font=dict(color="#e5e9f0"),
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        chart_placeholder.plotly_chart(fig, use_container_width=True)
        
        for sim_step in sim_gen:
            status = sim_step.get("status")
            msg = sim_step.get("msg")
            
            if status in ["init", "start", "error", "warning"]:
                st.session_state.test_log += msg + "\n"
                test_console_placeholder.markdown(
                    f'<div class="console-box">{st.session_state.test_log}</div>',
                    unsafe_allow_html=True
                )
                if status == "error":
                    st.error("Erro crítico na inicialização.")
                    break
                    
            elif status == "running":
                # Print log to console
                st.session_state.test_log += msg + "\n"
                # Keep scroll down locally:
                # split and keep last 20 lines to avoid slow page updates
                lines = st.session_state.test_log.split("\n")
                visible_logs = "\n".join(lines[-25:])
                test_console_placeholder.markdown(
                    f'<div class="console-box">{visible_logs}</div>',
                    unsafe_allow_html=True
                )
                
                # Atualizar dados gráficos
                plot_data["Dia"].append(sim_step["day"])
                plot_data["RL Agent"].append(sim_step["agent_profit_cum"])
                plot_data["Min-Max"].append(sim_step["minmax_profit_cum"])
                plot_data["Oracle"].append(sim_step["oracle_profit_cum"])
                plot_data["Real Demand"].append(sim_step["real_demand"])
                plot_data["Stock Level"].append(sim_step["stock_level"])
                
                # Fazer o redesenho parcial a cada 3 dias para suavizar performance do Streamlit
                if sim_step["day"] % 3 == 0 or sim_step["update_triggered"]:
                    # Criar nova figure com os arrays acumulados
                    fig_real = go.Figure()
                    fig_real.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["RL Agent"], mode='lines', name=f'RL Agent ({plot_data["RL Agent"][-1]:.0f}€)', line=dict(color='#00ffaa', width=2.5)))
                    fig_real.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["Min-Max"], mode='lines', name=f'Min-Max ({plot_data["Min-Max"][-1]:.0f}€)', line=dict(color='#8c9cb3', width=1.5, dash='dot')))
                    fig_real.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["Oracle"], mode='lines', name=f'Oráculo ({plot_data["Oracle"][-1]:.0f}€)', line=dict(color='#ffaa00', width=2.0, dash='dash')))
                    
                    fig_real.update_layout(
                        title="Evolução Comparativa do Lucro Acumulado em Tempo Real",
                        xaxis_title="Dias",
                        yaxis_title="Lucro Acumulado (€)",
                        paper_bgcolor="#11141e",
                        plot_bgcolor="#11141e",
                        font=dict(color="#e5e9f0"),
                        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                        margin=dict(t=50, b=40, l=40, r=40)
                    )
                    chart_placeholder.plotly_chart(fig_real, use_container_width=True)
                    
            elif status == "complete":
                st.session_state.test_log += msg + "\n"
                test_console_placeholder.markdown(
                    f'<div class="console-box">{st.session_state.test_log}</div>',
                    unsafe_allow_html=True
                )
                
                # Guardar resultados no session state
                st.session_state.test_completed = True
                st.session_state.test_results = sim_step
                
                # Plot final
                fig_final = go.Figure()
                fig_final.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["RL Agent"], mode='lines', name=f'RL Agent ({sim_step["cum_profit_agent"]:.1f}€)', line=dict(color='#00ffaa', width=3.0)))
                fig_final.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["Min-Max"], mode='lines', name=f'Min-Max ({sim_step["cum_profit_minmax"]:.1f}€)', line=dict(color='#8c9cb3', width=1.5, dash='dot')))
                fig_final.add_trace(go.Scatter(x=plot_data["Dia"], y=plot_data["Oracle"], mode='lines', name=f'Oráculo ({sim_step["cum_profit_oracle"]:.1f}€)', line=dict(color='#ffaa00', width=2.0, dash='dash')))
                
                # Marcar linhas de fine-tuning
                for ud in sim_step["update_days"]:
                    fig_final.add_vline(x=ud, line_width=1, line_dash="dash", line_color="#ff4757", annotation_text="Fine-Tuning", annotation_position="top left")
                
                fig_final.update_layout(
                    title="Evolução Comparativa do Lucro Acumulado Final",
                    xaxis_title="Dias",
                    yaxis_title="Lucro Acumulado (€)",
                    paper_bgcolor="#11141e",
                    plot_bgcolor="#11141e",
                    font=dict(color="#e5e9f0"),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
                )
                chart_placeholder.plotly_chart(fig_final, use_container_width=True)

    # Exibir Scorecard e downloaders ao completar a simulação
    if st.session_state.test_completed and st.session_state.test_results is not None:
        res = st.session_state.test_results
        
        st.markdown("---")
        st.markdown("### 📊 Scorecard de Resultados")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Lucro Agente</div>'
                f'<div class="metric-val">{res["cum_profit_agent"]:,.2f}€</div>'
                f'</div>', unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Lucro Min-Max</div>'
                f'<div class="metric-val" style="color: #8c9cb3;">{res["cum_profit_minmax"]:,.2f}€</div>'
                f'</div>', unsafe_allow_html=True
            )
        with c3:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Apodrecimento</div>'
                f'<div class="metric-val" style="color: #ff4757;">{res["spoilage_total"]:.0f} un</div>'
                f'</div>', unsafe_allow_html=True
            )
        with c4:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Vendas Perdidas</div>'
                f'<div class="metric-val" style="color: #ffb300;">{res["lost_sales_total"]:.0f} un</div>'
                f'</div>', unsafe_allow_html=True
            )
        with c5:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">Dias Stock Zero</div>'
                f'<div class="metric-val" style="color: #ff4757;">{res["stockout_days"]} dias</div>'
                f'</div>', unsafe_allow_html=True
            )
            
        # Comparações diretas
        profit_diff = res["cum_profit_agent"] - res["cum_profit_minmax"]
        pct_improvement = (profit_diff / max(1.0, abs(res["cum_profit_minmax"]))) * 100.0
        
        st.markdown("#### Resumo Executivo")
        if profit_diff > 0:
            st.success(f"📈 O Agente PPO superou o baseline Min-Max tradicional em **{profit_diff:.2f}€** (+{pct_improvement:.2f}%).")
        else:
            st.warning(f"📉 O Agente PPO obteve um lucro inferior ao baseline Min-Max tradicional em **{abs(profit_diff):.2f}€** ({pct_improvement:.2f}%).")
            
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("#### 📥 Exportar Resultados e Modelo Otimizado")
        col_down1, col_down2 = st.columns(2)
        
        with col_down1:
            # Downloader do excel de simulação
            if os.path.exists(res["excel_report_path"]):
                with open(res["excel_report_path"], "rb") as f:
                    st.download_button(
                        label="📊 Descarregar Relatório Excel (.xlsx)",
                        data=f.read(),
                        file_name="relatorio_simulacao_buyer_agent.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
        with col_down2:
            # Downloader do modelo fine-tuned final
            zip_final_bytes = create_model_zip_bytes(res["final_model_path"])
            if zip_final_bytes is not None:
                st.download_button(
                    label="📥 Descarregar Modelo Otimizado / Fine-Tuned (.ZIP)",
                    data=zip_final_bytes,
                    file_name="modelo_ppo_buyer_agent_fine_tuned.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        st.markdown('</div>', unsafe_allow_html=True)
