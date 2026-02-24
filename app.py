import os
import argparse
import sys

# Import Custom Modules
import data_parser
import analyser
import suggestion_engine


# ==============================================================================
# MODULE: Command Line Interface (app.py) 
# DESCRIPTION: A lightweight CLI for executing deterministic DevSecOps heuristics
#              without requiring a graphical web interface.
# ==============================================================================

def main():
    # Setup Argument Parser for Enterprise CLI usage
    parser = argparse.ArgumentParser(description="⚡ DevOps Pipeline Optimiser (CLI Mode)")
    parser.add_argument("-f", "--file", type=str, required=True, help="Path to the unstructured pipeline log file.")
    parser.add_argument("-t", "--threshold", type=float, default=0.20,
                        help="Pareto bottleneck sensitivity (default: 0.20).")

    args = parser.parse_args()
    log_file = args.file
    threshold = args.threshold

    print("\n" + "=" * 60)
    print(" ⚡ DEVOPS PIPELINE OPTIMISER (Headless Execution)")
    print("=" * 60)

    # ---------------------------------------------------------
    # STEP 1: PARSING (Sanitisation)
    # ---------------------------------------------------------
    if not os.path.exists(log_file):
        print(f"\n[FATAL ERROR] Artefact '{log_file}' not found.")
        sys.exit(1)

    print(f"[*] INGESTING: {log_file}")
    pipeline_data = data_parser.parse_log_file(log_file)

    if not pipeline_data:
        print("[FATAL ERROR] State Machine failed to parse valid sequence.")
        sys.exit(1)

    print(f"[+] PARSING SUCCESS: Extracted {len(pipeline_data)} topological nodes.")

    # ---------------------------------------------------------
    # STEP 2: ANALYSIS (Computation)
    # ---------------------------------------------------------
    print("\n[*] EXECUTING: O(V+E) Topological Sort & Edge Relaxation...")
    G = analyser.build_dag(pipeline_data)
    critical_path, total_duration = analyser.calculate_critical_path(G)

    if not critical_path:
        print("[FATAL ERROR] Cyclic deadlock detected in DAG topology.")
        sys.exit(1)

    print(f"[+] MATH SUCCESS: Total Makespan calculated at {total_duration:.2f}s")
    print(f"[+] CRITICAL PATH: {' -> '.join(critical_path)}")

    # Generate Visualisation Artefact in the background
    analyser.visualize_graph(G, critical_path)
    print("[+] ARTEFACT: Topology saved to 'pipeline_graph.png'.")

    # ---------------------------------------------------------
    # STEP 3: RECOMMENDATION (Heuristics)
    # ---------------------------------------------------------
    print(f"\n[*] EVALUATING: Heuristic rules engine (Threshold: {threshold * 100}%)...")

    recommendations = suggestion_engine.generate_suggestions(
        critical_path,
        pipeline_data,
        total_duration,
        threshold=threshold
    )

    print("\n" + "=" * 60)
    print(" 📋 ACTIONABLE PRESCRIPTIONS")
    print("=" * 60)

    if len(recommendations) == 1 and "No significant bottlenecks" in recommendations[0]:
        print("[OK] Topology Optimal. No architectural changes required.")
    else:
        for i, rec in enumerate(recommendations, 1):
            # Clean up the UI tags for terminal display
            rec = rec.replace("[DEVSECOPS BOTTLENECK]", "[SECURITY/COMPUTE]").replace("[I/O BOTTLENECK]",
                                                                                      "[I/O/DEPENDENCY]")
            print(f"  {i}. {rec}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
