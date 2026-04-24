import os
import tempfile
import streamlit as st
import pandas as pd
import plotly.express as px

import orchestrator
import analyser
import visualiser

# dashboard.py
# Interactive web dashboard — the primary interface for the tool.
# Streamlit re-executes the entire script on every user interaction,
# which enforces determinism: every widget change triggers a full
# re-analysis from scratch with no hidden state carry-over.
#
# Layout:
#   Sidebar  — file upload, sensitivity slider, What-If simulator
#   Tab 1    — summary metrics and Gantt timeline
#   Tab 2    — DAG graph image and critical path list
#   Tab 3    — optimisation recommendations
#
# Theme: GitHub Dark — chosen because DevOps engineers work primarily
# in dark-mode terminal and IDE environments.
#
# Usage: streamlit run dashboard.py

st.set_page_config(
    page_title="Pipeline Optimiser",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# GitHub Dark colour scheme applied via injected CSS
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1, h2, h3, h4, p, span, div, li { color: #c9d1d9 !important; }

    div[data-testid="stMetric"] {
        background-color: #161b22 !important; border: 1px solid #30363d !important;
        padding: 20px; border-radius: 6px;
    }
    div[data-testid="stMetricLabel"] > div { color: #8b949e !important; font-size: 1rem !important; }
    div[data-testid="stMetricValue"] > div { color: #58a6ff !important; font-size: 2.2rem !important; }

    .stTabs [data-baseweb="tab-list"] { background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22; color: #8b949e !important;
        border: 1px solid #30363d; border-bottom: none; border-radius: 6px 6px 0 0;
    }
    .stTabs [aria-selected="true"] { background-color: #1f6feb !important; color: #ffffff !important; }

    .alert-compute { background-color: #2a0a12; border-left: 5px solid #f85149; padding: 15px; border-radius: 6px; margin-bottom: 12px; }
    .alert-compute h4 { color: #ff7b72 !important; margin: 0 0 8px 0; }
    .alert-compute p  { color: #ffdce0 !important; margin: 0; }

    .alert-io { background-color: #0d223f; border-left: 5px solid #58a6ff; padding: 15px; border-radius: 6px; margin-bottom: 12px; }
    .alert-io h4 { color: #79c0ff !important; margin: 0 0 8px 0; }
    .alert-io p  { color: #cdd9e5 !important; margin: 0; }

    .alert-general { background-color: #2b1d07; border-left: 5px solid #d29922; padding: 15px; border-radius: 6px; margin-bottom: 12px; }
    .alert-general h4 { color: #e3b341 !important; margin: 0 0 8px 0; }
    .alert-general p  { color: #f0e2b6 !important; margin: 0; }

    .path-card {
        background: #161b22; border-left: 4px solid #238636;
        padding: 12px 16px; margin-bottom: 12px; border-radius: 6px;
        border: 1px solid #30363d; display: flex; align-items: center;
    }
    .path-step {
        background: #238636; color: #ffffff !important; font-weight: bold;
        border-radius: 50%; width: 30px; height: 30px; display: flex;
        justify-content: center; align-items: center; margin-right: 15px;
    }
    .path-name { color: #c9d1d9 !important; font-weight: 600; font-size: 1.05rem; }

    .welcome-card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 24px; height: 100%;
    }
    .welcome-card:hover { border-color: #8b949e; }
    .welcome-icon  { font-size: 2.5rem; margin-bottom: 15px; display: block; }
    .welcome-title { font-size: 1.25rem; font-weight: 700; color: #58a6ff !important; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)


def create_gantt_chart(pipeline_data):
    """Builds a Plotly timeline chart. Returns None if no plottable jobs found."""
    df_list = []
    for job, attrs in pipeline_data.items():
        if attrs.get('start') is not None and 'duration' in attrs:
            end_time = attrs['start'] + pd.Timedelta(seconds=attrs['duration'])
            df_list.append(dict(
                Job=job, Start=attrs['start'],
                Finish=end_time, Duration=attrs['duration']
            ))
    if not df_list:
        return None
    df  = pd.DataFrame(df_list)
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Job",
        color="Duration", color_continuous_scale="Tealgrn",
        title="Pipeline Timeline"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=450, margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9")
    )
    return fig


def render_recommendation(rec):
    """Renders a Recommendation as a coloured HTML card."""
    if rec.category == 'compute':
        st.markdown(
            f'<div class="alert-compute"><h4>Compute-Bound Task</h4>'
            f'<p>{rec.message}</p></div>', unsafe_allow_html=True
        )
    elif rec.category == 'io':
        st.markdown(
            f'<div class="alert-io"><h4>I/O-Bound Task</h4>'
            f'<p>{rec.message}</p></div>', unsafe_allow_html=True
        )
    elif rec.category == 'general':
        st.markdown(
            f'<div class="alert-general"><h4>Slow Task Detected</h4>'
            f'<p>{rec.message}</p></div>', unsafe_allow_html=True
        )
    else:
        st.success(rec.message)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Settings")
    st.subheader("1. Upload Log File")
    uploaded_file = st.file_uploader(
        "Upload a pipeline log (.txt or .log)", type=["txt", "log"]
    )
    st.subheader("2. Sensitivity")
    threshold_slider = st.slider(
        "Flag tasks taking more than X% of total time:", 0.05, 0.50, 0.20
    )
    st.divider()
    st.caption("Honours Project — Edinburgh Napier University")


# ── Main page ─────────────────────────────────────────────────────────────────

if uploaded_file is None:
    st.markdown(
        "<h1 style='text-align:center;font-size:3rem;margin-top:2rem;'>"
        "Pipeline Optimiser</h1>", unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center;font-size:1.2rem;color:#8b949e !important;'>"
        "Upload a CI/CD log file to identify bottlenecks using Critical Path Analysis.</p>",
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div class="welcome-card">
            <span class="welcome-icon">🕸️</span>
            <div class="welcome-title">Critical Path Analysis</div>
            <p>Models your pipeline as a DAG and identifies the longest chain of
            dependent tasks — the critical path that sets your minimum deployment time.</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="welcome-card">
            <span class="welcome-icon">🧠</span>
            <div class="welcome-title">Rule-Based Recommendations</div>
            <p>Classifies bottlenecks as compute-bound or I/O-bound and provides
            specific strategies such as parallel sharding or dependency caching.</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="welcome-card">
            <span class="welcome-icon">🚀</span>
            <div class="welcome-title">Supported Platforms</div>
            <p>Accepts raw build logs from GitHub Actions or Jenkins.
            Handles section markers, group markers, and timestamp-based detection.</p>
        </div>""", unsafe_allow_html=True)
    st.markdown(
        "<br><p style='text-align:center;color:#58a6ff !important;font-size:1.1rem;'>"
        "Upload a log file from the sidebar to get started.</p>", unsafe_allow_html=True
    )

else:
    st.title("Pipeline Optimiser")

    # Write uploaded bytes to a temporary file — the parser needs a real file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    try:
        with st.spinner('Analysing pipeline...'):
            result = orchestrator.run_analysis(tmp_path, threshold=threshold_slider)

        if result is None:
            st.error("Could not analyse this file. Please check it is a valid pipeline log.")
            st.stop()

        baseline_makespan = result.makespan

        # What-If Simulator — placed after analysis so job names are available
        with st.sidebar:
            st.divider()
            st.subheader("What-If Simulator")
            enable_sim = st.checkbox("Test a potential optimisation")
            sim_savings = 0.0

            if enable_sim:
                job_names     = list(result.pipeline_data.keys())
                sim_job       = st.selectbox("Select a task to speed up:", job_names)
                sim_reduction = st.slider("Speed up by (%):", 0, 90, 50, 10)

                if sim_job and sim_reduction > 0:
                    # Copy the pipeline data so the original result is not modified
                    sim_data = {k: dict(v) for k, v in result.pipeline_data.items()}
                    original_dur = sim_data[sim_job].get('duration', 0)
                    sim_data[sim_job]['duration'] = original_dur * (1 - sim_reduction / 100.0)

                    sim_graph = analyser.build_dag(sim_data)
                    _, sim_makespan = analyser.calculate_critical_path(sim_graph)
                    sim_savings = baseline_makespan - sim_makespan

                    st.success(
                        f"Simulated: {sim_reduction}% faster '{sim_job}' "
                        f"saves {sim_savings:.1f}s"
                    )

        tab1, tab2, tab3 = st.tabs(["Overview", "Pipeline Graph", "Optimisation Plan"])

        with tab1:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Makespan",            f"{result.makespan:.2f}s")
            col2.metric("Critical Path Tasks", f"{len(result.critical_path)}")
            col3.metric("Total Stages",        f"{result.graph.number_of_nodes()}")
            if enable_sim and sim_savings > 0:
                col4.metric("Simulated Savings", f"{sim_savings:.1f}s")
            else:
                col4.metric("Status", "Baseline")
            st.divider()
            gantt_fig = create_gantt_chart(result.pipeline_data)
            if gantt_fig:
                st.plotly_chart(gantt_fig, use_container_width=True)
            else:
                st.info("Timeline unavailable — start times could not be determined for all stages.")

        with tab2:
            col_left, col_right = st.columns([2, 1])
            with col_left:
                graph_path = "pipeline_graph.png"
                saved = visualiser.save_pipeline_graph(
                    result.graph, result.critical_path, graph_path
                )
                if saved and os.path.exists(graph_path):
                    st.image(graph_path, use_container_width=True)
                else:
                    st.warning("Could not generate graph image.")
            with col_right:
                st.markdown("<h3 style='margin-bottom:20px;'>Critical Path</h3>", unsafe_allow_html=True)
                for i, node in enumerate(result.critical_path):
                    st.markdown(
                        f'<div class="path-card"><div class="path-step">{i + 1}</div>'
                        f'<div class="path-name">{node}</div></div>',
                        unsafe_allow_html=True
                    )

        with tab3:
            st.markdown("<h3 style='margin-bottom:20px;'>Recommendations</h3>", unsafe_allow_html=True)
            has_issues = any(r.category != 'info' for r in result.recommendations)
            if not has_issues:
                st.success("No major bottlenecks detected at the current sensitivity threshold.")
            for rec in result.recommendations:
                if rec.category != 'info':
                    render_recommendation(rec)

    finally:
        # Always remove the temp file — even if analysis raises an exception
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
