import logging
from dataclasses import dataclass, field
from typing import List, Optional

import networkx as nx

import data_parser
import analyser
import suggestion_engine
from suggestion_engine import Recommendation

# orchestrator.py
# Single entry point for the complete analysis pipeline.
# Both the CLI (app.py) and the dashboard (dashboard.py) call run_analysis()
# here, so the analysis logic lives in exactly one place.
#
# Flow: Log file → Parse → Build DAG → Critical Path → Suggestions
#
# Keeping this separate from the two interfaces means:
#   - changing the analysis logic never touches the UI code
#   - CLI and dashboard are guaranteed to produce identical results
#   - the integration test can exercise the full pipeline in one call

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """
    Bundles all outputs from a single analysis run.
    Passed directly from the orchestrator to the CLI or dashboard for rendering.
    """
    pipeline_data:   dict                         # raw parsed job data
    graph:           nx.DiGraph                   # the DAG built from that data
    critical_path:   List[str]                    # ordered list of bottleneck stages
    makespan:        float                        # total critical path duration in seconds
    recommendations: List[Recommendation] = field(default_factory=list)


def run_analysis(
    log_file_path: str,
    threshold: float = 0.20
) -> Optional[AnalysisResult]:
    """
    Runs the full four-step analysis pipeline on a CI/CD log file.

    Steps:
      1. Parse  — extract structured job data from the raw log
      2. Build  — construct a weighted DAG from the parsed data
      3. CPA    — find the critical path and compute the makespan
      4. Suggest — generate optimisation recommendations

    Returns an AnalysisResult, or None if parsing fails or the graph is invalid.
    """
    # Step 1 — Parse
    pipeline_data = data_parser.parse_log_file(log_file_path)
    if not pipeline_data:
        logger.error("Parsing produced no valid results.")
        return None

    # Step 2 — Build DAG
    graph = analyser.build_dag(pipeline_data)

    # Step 3 — Critical Path Analysis
    critical_path, makespan = analyser.calculate_critical_path(graph)
    if not critical_path:
        logger.error("Critical path analysis failed (empty graph or cycle detected).")
        return None

    # Step 4 — Generate recommendations
    recommendations = suggestion_engine.generate_suggestions(
        critical_path, pipeline_data, makespan, threshold=threshold
    )

    return AnalysisResult(
        pipeline_data=pipeline_data,
        graph=graph,
        critical_path=critical_path,
        makespan=makespan,
        recommendations=recommendations
    )
