import os
import argparse
import sys

import orchestrator
import visualiser

# app.py
# Command-line interface for headless pipeline analysis.
# Useful for engineers who prefer terminal workflows or need to integrate
# the tool into scripts without launching a browser.
#
# All analysis logic is handled by orchestrator.py — this file only deals
# with argument parsing, input validation, and printing results to stdout.
#
# Usage:
#   python app.py -f path/to/logfile.txt
#   python app.py -f path/to/logfile.txt -t 0.15


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

    # Validate the file exists before passing it to the analyser
    if not os.path.exists(args.file):
        print(f"\n[ERROR] File not found: '{args.file}'")
        sys.exit(1)

    print(f"\n[*] Analysing: {args.file}")
    result = orchestrator.run_analysis(args.file, threshold=args.threshold)

    if result is None:
        print("[ERROR] Analysis failed. Check that the file is a valid pipeline log.")
        sys.exit(1)

    # Print summary metrics
    print(f"[+] Stages extracted : {result.graph.number_of_nodes()}")
    print(f"[+] Makespan         : {result.makespan:.2f}s")
    print(f"[+] Critical path    : {' -> '.join(result.critical_path)}")

    # Save the DAG image
    graph_path = "pipeline_graph.png"
    saved = visualiser.save_pipeline_graph(result.graph, result.critical_path, graph_path)
    if saved:
        print(f"[+] Graph saved to   : '{graph_path}'")
    else:
        print("[!] Could not save graph image.")

    # Print recommendations
    print(f"\n[*] Recommendations (threshold: {args.threshold * 100:.0f}%):")
    print("=" * 60)

    for i, rec in enumerate(result.recommendations, 1):
        if rec.category == 'info':
            print(f"  {rec.message}")
        else:
            label = {'compute': 'COMPUTE', 'io': 'I/O', 'general': 'GENERAL'}.get(
                rec.category, 'GENERAL'
            )
            print(f"  {i}. [{label}] {rec.message}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
