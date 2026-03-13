import logging
from typing import Optional
from dataclasses import dataclass, field
from typing import List

import networkx as nx

import data_parser
import analyser
import suggestion_engine
from suggestion_engine import Recommendation

# ==============================================================================
# MODULE: orchestrator.py
# PURPOSE: Provides a single entry point for the complete analysis pipeline:
#          Parse -> Build DAG -> Critical Path -> Suggestions.
#
# DESIGN JUSTIFICATION:
#   Both the CLI (app.py) and the web dashboard (dashboard.py) execute the
#   same analysis workflow. Extracting this shared logic into a dedicated
#   module eliminates code duplication and ensures both interfaces produce
#   identical results. This follows the separation of concerns principle:
#   the orchestrator handles business logic, while app.py and dashboard.py
#   handle their respective presentation layers.
#
# IPO MAPPING: This module coordinates the four IPO components.
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """
    Contains all outputs from a complete pipeline analysis run.

    Attributes:
        pipeline_data: Raw parsed data from the log file.
        graph: The NetworkX DAG representation.
        critical_path: Ordered list of job names on the critical path.
        makespan: Total critical path duration in seconds.
        recommendations: List of structured Recommendation objects.
    """
    pipeline_data: dict
    graph: nx.DiGraph
    critical_path: List[str]
    makespan: float
    recommendations: List[Recommendation] = field(default_factory=list)


def run_analysis(
    log_file_path: str,
    threshold: float = 0.20
) -> Optional[AnalysisResult]:
    """
    Executes the full analysis pipeline on a log file.

    Steps:
      1. Parse the log file into structured data.
      2. Build a DAG from the parsed data.
      3. Compute the critical path and makespan.
      4. Generate optimisation recommendations.

    Args:
        log_file_path: Path to the CI/CD log file.
        threshold: Bottleneck sensitivity threshold (0.0-1.0).

    Returns:
        An AnalysisResult containing all outputs, or None if parsing fails.
    """
    # Step 1: Parse
    pipeline_data = data_parser.parse_log_file(log_file_path)
    if not pipeline_data:
        logger.error("Parsing produced no valid results.")
        return None

    # Step 2: Build DAG
    graph = analyser.build_dag(pipeline_data)

    # Step 3: Critical Path
    critical_path, makespan = analyser.calculate_critical_path(graph)
    if not critical_path:
        logger.error("Critical path analysis failed (empty graph or cycle detected).")
        return None

    # Step 4: Suggestions
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
