import os
import argparse
import sys

import orchestrator
import visualiser

# ==============================================================================
# MODULE: app.py
# PURPOSE: Command Line Interface (CLI) for headless pipeline analysis.
#          Uses the shared orchestrator module for all analysis logic.
#
# DESIGN JUSTIFICATION:
#   Provides a terminal-based interface for DevOps engineers who prefer
#   CLI workflows or need to integrate the tool into scripts/automation.
#   All analysis logic is delegated to orchestrator.py to ensure the CLI
#   and dashboard produce identical results.
#
# USAGE: python app.py -f path/to/logfile.txt [-t 0.20]
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="DevOps Pipeline Optimiser — CLI Mode"
    )
    parser.add_argument(
        "-f", "--file", type=str, required=True,
        help="Path to the pipeline log file (.txt or .log)."
    )
    parser.add_argument(
        "-t", "--threshold", type=float, default=0.20,
        help="Bottleneck sensitivity threshold (default: 0.20 = 20%%)."
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(" DevOps Pipeline Optimiser (CLI)")
    print("=" * 60)

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"\n[ERROR] File not found: '{args.file}'")
        sys.exit(1)

    # Run the shared analysis pipeline
    print(f"\n[*] Analysing: {args.file}")
    result = orchestrator.run_analysis(args.file, threshold=args.threshold)

    if result is None:
        print("[ERROR] Analysis failed. Check that the file is a valid pipeline log.")
        sys.exit(1)

    # Display results
    print(f"[+] Stages extracted: {result.graph.number_of_nodes()}")
    print(f"[+] Makespan: {result.makespan:.2f}s")
    print(f"[+] Critical path: {' -> '.join(result.critical_path)}")

    # Generate graph image
    graph_path = "pipeline_graph.png"
    saved = visualiser.save_pipeline_graph(result.graph, result.critical_path, graph_path)
    if saved:
        print(f"[+] Graph saved to '{graph_path}'")
    else:
        print("[!] Could not save graph image.")

    # Display recommendations
    print(f"\n[*] Recommendations (threshold: {args.threshold * 100:.0f}%):")
    print("=" * 60)

    for i, rec in enumerate(result.recommendations, 1):
        if rec.category == 'info':
            print(f"  {rec.message}")
        else:
            label = {
                'compute': 'COMPUTE',
                'io': 'I/O',
                'general': 'GENERAL'
            }.get(rec.category, 'GENERAL')
            print(f"  {i}. [{label}] {rec.message}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
