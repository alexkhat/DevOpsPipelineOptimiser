import streamlit as st
import pandas as pd
import os
# Import core custom modules to connect the analytical pipeline
from data_parser import parse_ci_log
from analyzer import PipelineAnalyzer
from suggestion_engine import generate_recommendations
from typing import List

# Set the Streamlit page configuration for a professional, wide display
st.set_page_config(layout="wide", page_title="DevOps Pipeline Optimizer")

# --- HUMANIZED EXPLANATION OF THE APP ---
st.title("🚀 DevOps Pipeline Optimizer (MVP)")
st.markdown(
    "This tool provides **prescriptive, quantifiable analysis** by modeling your CI/CD pipeline as a flowchart (DAG) to find the exact sequence of tasks that cause the biggest delay (the **Critical Path**).")
st.markdown("---")


def run_pipeline_analysis(log_path: str):
    """
    Orchestrates the entire analytical workflow (Parsing -> Analysis -> Prediction -> Visualization)
    and presents the results in the interactive Streamlit interface.
    """

    # 1. PARSING (The Input Bridge)
    st.subheader("1. Data Ingestion & Parsing")
    structured_df = parse_ci_log(log_path)
    if structured_df.empty:
        st.error("Analysis stopped. Could not process log data.")
        return

    # 2. ANALYSIS (The Brain - DAG Construction and CPM Execution)
    st.subheader("2. Analytical Model & Critical Path Calculation")
    analyzer = PipelineAnalyzer(structured_df)

    # Find the Critical Path and total time (Makespan)
    path, makespan = analyzer.find_critical_path()

    # --- ERROR CHECKING (Ensuring robustness against bad data) ---
    if isinstance(path, list) and path[0].startswith("ERROR_"):
        st.error(f"❌ Analysis Failed: {path[0].replace('ERROR_', '').replace('_', ' ')}.")
        st.info("Action: Review log data for cycles or ensure start/end nodes are defined.")
        return

    # If successful, proceed to calculate metrics
    critical_path_duration = 0
    bottleneck_task = ""
    max_duration = -1

    # Loop over the calculated path to find the single largest bottleneck task
    for task in path:
        duration = analyzer.graph.nodes[task].get('duration', 0)
        critical_path_duration += duration

        if duration > max_duration:
            max_duration = duration
            bottleneck_task = task

    # --- DISPLAY METRICS ---
    st.subheader("3. Core Performance Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pipeline Runtime (Makespan)", f"{makespan:.0f} seconds")
    col2.metric("Critical Path Tasks", f"{len(path)} tasks")
    col3.metric("Primary Time Sink", f"'{bottleneck_task}' ({max_duration:.0f}s)")

    # --- VISUALIZATION ---
    # Draw the graph and save it to a file, then display the file in the app.
    analyzer.draw_pipeline_graph(path)
    st.subheader("4. Critical Path Visualization")
    st.markdown("The flowchart below visually confirms the critical sequence (tasks colored **RED**).")
    st.image("pipeline_dag_output.png", caption="Pipeline Dependency Flowchart (Critical Path Highlighted)",
             use_column_width=True)

    # --- PRESCRIPTIVE ADVICE & SIMULATION ---
    st.subheader("5. Actionable Recommendations (Prescriptive Action)")

    # Generate recommendations using the quantifiable result
    recommendations = generate_recommendations(path, makespan, bottleneck_task, max_duration)

    # Print the specific bottleneck finding first
    st.markdown(
        f"**📌 Finding:** The largest time-sink on the Critical Path is **'{bottleneck_task}'** ({max_duration:.0f}s).")

    for rec in recommendations:
        st.markdown(f"- **{rec}**")

    st.markdown("---")
    st.success("Analysis and prediction complete. You are now equipped with the data to optimize your pipeline!")

    # --- DEBUG/DATA OUTPUT ---
    st.markdown("### 6. Debug Data (Full Task List)")
    st.dataframe(structured_df, use_container_width=True)


# --- Streamlit Execution Flow ---
if __name__ == "__main__":

    # Define the log file path used for the MVP demonstration
    log_file = "real_world_simulated_log.json"

    # Check for file existence before running
    if not os.path.exists(log_file):
        st.error(f"FATAL ERROR: Required data file '{log_file}' not found.")
        st.stop()

    # Run the orchestrator function
    run_pipeline_analysis(log_file)