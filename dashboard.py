import os
import streamlit as st
import pandas as pd
import plotly.express as px
import networkx as nx

import data_parser
import analyser
import suggestion_engine

# ==============================================================================
# Dashboard Interface - GitHub Dark Theme Edition (UK English)
# ==============================================================================

st.set_page_config(
    page_title="Pipeline Optimiser",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# Custom CSS for GitHub Dark Theme & Welcome Cards
st.markdown("""
    <style>
    /* 1. GitHub Dark Backgrounds */
    .stApp { background-color: #0d1117; } /* GitHub Canvas Black */
    section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }

    /* Global Text Colors */
    h1, h2, h3, h4, p, span, div, li { color: #c9d1d9 !important; }

    /* 2. Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #161b22 !important; 
        border: 1px solid #30363d !important;
        padding: 20px; border-radius: 6px;
    }
    div[data-testid="stMetricLabel"] > div { color: #8b949e !important; font-size: 1rem !important; font-weight: 600 !important; }
    div[data-testid="stMetricValue"] > div { color: #58a6ff !important; font-size: 2.2rem !important; font-weight: 700 !important; }

    /* 3. Tabs */
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22; color: #8b949e !important; 
        border: 1px solid #30363d; border-bottom: none; border-radius: 6px 6px 0 0;
    }
    .stTabs [aria-selected="true"] { background-color: #1f6feb !important; color: #ffffff !important; border-color: #1f6feb; }

    /* 4. Alert Boxes */
    .alert-compute { background-color: #2a0a12; border-left: 5px solid #f85149; padding: 15px; border-radius: 6px; margin-bottom: 12px; border: 1px solid #4a131b; border-left-width: 5px; }
    .alert-compute h4 { color: #ff7b72 !important; font-weight: 700; margin-top: 0; margin-bottom: 8px;}
    .alert-compute p { color: #ffdce0 !important; font-weight: 500; font-size: 1.05rem; line-height: 1.5; margin: 0;}

    .alert-io { background-color: #0d223f; border-left: 5px solid #58a6ff; padding: 15px; border-radius: 6px; margin-bottom: 12px; border: 1px solid #163a6a; border-left-width: 5px; }
    .alert-io h4 { color: #79c0ff !important; font-weight: 700; margin-top: 0; margin-bottom: 8px;}
    .alert-io p { color: #cdd9e5 !important; font-weight: 500; font-size: 1.05rem; line-height: 1.5; margin: 0;}

    .alert-general { background-color: #2b1d07; border-left: 5px solid #d29922; padding: 15px; border-radius: 6px; margin-bottom: 12px; border: 1px solid #4d350b; border-left-width: 5px; }
    .alert-general h4 { color: #e3b341 !important; font-weight: 700; margin-top: 0; margin-bottom: 8px;}
    .alert-general p { color: #f0e2b6 !important; font-weight: 500; font-size: 1.05rem; line-height: 1.5; margin: 0;}

    /* 5. Critical Path Cards */
    .path-card {
        background: #161b22; border-left: 4px solid #238636;
        padding: 12px 16px; margin-bottom: 12px; border-radius: 6px;
        border: 1px solid #30363d; border-left-width: 4px; display: flex; align-items: center;
    }
    .path-step {
        background: #238636; color: #ffffff !important; font-weight: bold;
        border-radius: 50%; width: 30px; height: 30px; display: flex;
        justify-content: center; align-items: center; margin-right: 15px;
    }
    .path-name { color: #c9d1d9 !important; font-weight: 600; font-size: 1.05rem; }

    /* 6. Welcome Landing Page Cards */
    .welcome-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 24px;
        height: 100%;
        transition: border-color 0.2s;
    }
    .welcome-card:hover { border-color: #8b949e; }
    .welcome-icon { font-size: 2.5rem; margin-bottom: 15px; display: block; }
    .welcome-title { font-size: 1.25rem; font-weight: 700; color: #58a6ff !important; margin-bottom: 10px; }

    .logo-container { display: flex; gap: 20px; align-items: center; margin-top: 20px; }
    /* The CSS invert filter makes the black GitHub logo turn bright white */
    .logo-container img { height: 45px; opacity: 0.8; transition: filter 0.3s, opacity 0.3s; }
    .logo-container img:hover { opacity: 1; transform: scale(1.05); }
    </style>
    """, unsafe_allow_html=True)


# ==============================================================================
# Helper Functions
# ==============================================================================
def create_gantt_chart(pipeline_data):
    df_list = []
    for job, attrs in pipeline_data.items():
        if 'start' in attrs and 'duration' in attrs:
            end_time = attrs['start'] + pd.Timedelta(seconds=attrs['duration'])
            df_list.append(dict(Job=job, Start=attrs['start'], Finish=end_time, Duration=attrs['duration']))

    if not df_list: return None

    df = pd.DataFrame(df_list)
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Job", color="Duration",
        color_continuous_scale="Tealgrn", title="Timeline View"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=450, margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9")
    )
    return fig


# ==============================================================================
# Sidebar & Inputs
# ==============================================================================
with st.sidebar:
    st.title("⚙️ Settings")

    st.subheader("1. Upload File")
    uploaded_file = st.file_uploader("Upload your pipeline log (.txt or .log)", type=["txt", "log"])

    st.subheader("2. Sensitivity")
    threshold_slider = st.slider("Flag tasks taking more than X% of total time:", 0.05, 0.50, 0.20)

    st.divider()

    st.subheader("🔮 What-If Simulator")
    enable_sim = st.checkbox("Test a potential fix")
    sim_job = None
    sim_reduction = 0

    if enable_sim and uploaded_file:
        st.info("Select a slow task and see how much time you'd save by speeding it up.")
        sim_job = st.selectbox("Select a task to optimise:",
                               list(data_parser.parse_log_file("temp_log.txt").keys()) if os.path.exists(
                                   "temp_log.txt") else [])
        sim_reduction = st.slider("Speed up this task by (%)", 0, 90, 50, 10)

    st.divider()
    st.caption("Final Year Honours Project")

# ==============================================================================
# Main Page Logic
# ==============================================================================
if uploaded_file is None:
    # ---------------------------------------------------------
    # EMPTY STATE / LANDING PAGE
    # ---------------------------------------------------------
    st.markdown("<h1 style='text-align: center; font-size: 3rem; margin-top: 2rem;'>⚡ Pipeline Optimiser</h1>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 1.2rem; color: #8b949e !important; margin-bottom: 3rem;'>Stop guessing. Use Graph Theory to find the true bottlenecks in your pipelines.</p>",
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="welcome-card">
            <span class="welcome-icon">🕸️</span>
            <div class="welcome-title">What is a Bottleneck?</div>
            <p>Pipelines run tasks in parallel. A task that takes 5 minutes isn't a bottleneck if another task running at the exact same time takes 10 minutes.</p>
            <p>This tool models your logs as a <b>Directed Acyclic Graph (DAG)</b> to mathematically prove which sequence of tasks is actually slowing down your deployment.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="welcome-card">
            <span class="welcome-icon">🧠</span>
            <div class="welcome-title">The Expert System</div>
            <p>This is a deterministic Heuristic Engine based on established engineering literature.</p>
            <ul>
                <li>Filters out micro-task noise using Amdahl's Law.</li>
                <li>Identifies I/O vs Compute boundaries.</li>
                <li>Suggests actionable fixes like Parallel Sharding or Dependency Caching.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="welcome-card">
            <span class="welcome-icon">🚀</span>
            <div class="welcome-title">Supported Platforms</div>
            <p>Upload raw, unstructured build logs directly from your runners. The Regex State Machine automatically cleans formatting noise and extracts execution telemetry.</p>
            <div class="logo-container">
                <img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="GitHub Actions" style="filter: invert(100%) brightness(200%);">
                <img src="https://upload.wikimedia.org/wikipedia/commons/e/e9/Jenkins_logo.svg" alt="Jenkins">
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        "<br><p style='text-align: center; color: #58a6ff !important; font-size: 1.1rem; font-weight: 600;'>👈 Get started by uploading a .txt or .log file from the menu.</p>",
        unsafe_allow_html=True)

else:
    # ---------------------------------------------------------
    # ANALYSIS STATE (When file is uploaded)
    # ---------------------------------------------------------
    st.title("⚡ Pipeline Optimiser")

    with open("temp_log.txt", "wb") as f:
        f.write(uploaded_file.getbuffer())

    with st.spinner('Reading log file...'):
        pipeline_data = data_parser.parse_log_file("temp_log.txt")

    if not pipeline_data:
        st.error("❌ Could not read this file. Please make sure it's a valid pipeline log.")
        st.stop()

    if enable_sim and sim_job:
        original_duration = pipeline_data[sim_job].get('duration', 0)
        pipeline_data[sim_job]['duration'] = original_duration * (1 - (sim_reduction / 100.0))
        st.sidebar.success(f"Testing a {sim_reduction}% speedup on '{sim_job}'.")

    with st.spinner('Analysing pipeline dependencies...'):
        G = analyser.build_dag(pipeline_data)
        critical_path, total_duration = analyser.calculate_critical_path(G)

    recommendations = suggestion_engine.generate_suggestions(critical_path, pipeline_data, total_duration,
                                                             threshold=threshold_slider)

    tab1, tab2, tab3 = st.tabs(["📊 Overview", "🕸️ Pipeline Graph", "💡 Optimisation Plan"])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Calculated Makespan", f"{total_duration:.2f}s")
        col2.metric("Blocking Tasks", f"{len(critical_path)}")
        col3.metric("Total Extracted Nodes", f"{G.number_of_nodes()}")

        if enable_sim:
            col4.metric("Simulated Savings", f"▼ {sim_reduction}%")
            st.info(
                f"🧪 **Simulation Active:** If you apply this fix, the new makespan will be **{total_duration:.2f}s**.")
        else:
            col4.metric("Baseline", "100%", "Unoptimised")

        st.divider()
        gantt_fig = create_gantt_chart(pipeline_data)
        if gantt_fig: st.plotly_chart(gantt_fig, use_container_width=True)

    with tab2:
        col_left, col_right = st.columns([2, 1])
        with col_left:
            analyser.visualize_graph(G, critical_path)
            if os.path.exists("pipeline_graph.png"):
                st.image("pipeline_graph.png", use_container_width=True)
        with col_right:
            st.markdown("<h3 style='margin-bottom: 20px;'>Critical Path</h3>", unsafe_allow_html=True)
            for i, node in enumerate(critical_path):
                st.markdown(
                    f'<div class="path-card"><div class="path-step">{i + 1}</div><div class="path-name">{node}</div></div>',
                    unsafe_allow_html=True)

    with tab3:
        st.markdown("<h3 style='margin-bottom: 20px;'>Recommended Actions</h3>", unsafe_allow_html=True)
        if len(recommendations) == 1 and "No significant bottlenecks" in recommendations[0]:
            st.success("✅ **Looking Good:** Your pipeline is highly optimised. No major bottlenecks detected.")
        else:
            for rec in recommendations:
                if "[DEVSECOPS BOTTLENECK]" in rec:
                    clean = rec.replace("[DEVSECOPS BOTTLENECK]", "").strip()
                    st.markdown(f'<div class="alert-compute"><h4>🚨 Security / Compute Task</h4><p>{clean}</p></div>',
                                unsafe_allow_html=True)
                elif "[I/O BOTTLENECK]" in rec:
                    clean = rec.replace("[I/O BOTTLENECK]", "").strip()
                    st.markdown(f'<div class="alert-io"><h4>💾 Download / Setup Task</h4><p>{clean}</p></div>',
                                unsafe_allow_html=True)
                elif "[GENERAL BOTTLENECK]" in rec:
                    clean = rec.replace("[GENERAL BOTTLENECK]", "").strip()
                    st.markdown(f'<div class="alert-general"><h4>⚠️ Slow Task Detected</h4><p>{clean}</p></div>',
                                unsafe_allow_html=True)
                else:
                    st.info(rec)
