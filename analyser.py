import networkx as nx
import logging
from typing import Dict, List, Tuple, Any

# ==============================================================================
# MODULE: analyser.py
# PURPOSE: Transforms parsed pipeline data into a Directed Acyclic Graph (DAG)
#          and identifies the Critical Path using topological sort with
#          dynamic programming relaxation.
#
# DESIGN JUSTIFICATION:
#   - DAG modelling follows the StalkCD framework (Dullmann et al., 2021)
#     which advocates treating pipelines as graph structures rather than
#     sequential scripts.
#   - Critical Path Analysis follows Agarwal (2025), who identifies CPA as
#     the standard for measuring pipeline makespan.
#   - Algorithm complexity: O(V+E) via topological sort, replacing brute-force
#     O(2^V) path enumeration.
#
# IPO MAPPING: This module implements the "Analyzer" component.
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def build_dag(pipeline_data: Dict[str, Dict[str, Any]]) -> nx.DiGraph:
    """
    Constructs a Directed Acyclic Graph from parsed pipeline data.

    Each job becomes a node weighted by its duration. Each dependency
    relationship becomes a directed edge (parent -> child).

    Args:
        pipeline_data: Dictionary from the parser with job names as keys
                       and {duration, dependencies, start} as values.

    Returns:
        A NetworkX DiGraph representing the pipeline topology.
    """
    G = nx.DiGraph()
    logger.info("Building Directed Acyclic Graph from pipeline data.")

    for job, attributes in pipeline_data.items():
        duration = attributes.get('duration', 0.0)
        G.add_node(job, duration=duration)

        for parent in attributes.get('dependencies', []):
            if parent in pipeline_data:
                G.add_edge(parent, job)

    logger.info(
        f"DAG constructed: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges."
    )
    return G


def calculate_critical_path(G: nx.DiGraph) -> Tuple[List[str], float]:
    """
    Identifies the Critical Path (longest path) in the pipeline DAG.

    Uses topological sort followed by edge relaxation (dynamic programming)
    to find the path with the maximum accumulated duration. This path
    determines the minimum possible makespan of the pipeline.

    The algorithm:
      1. Initialise each node's distance to its own duration.
      2. Process nodes in topological order.
      3. For each node, check if routing through it gives successors a
         longer accumulated path. If so, update the successor's distance.
      4. The node with the maximum distance is the end of the critical path.
      5. Backtrack through predecessors to reconstruct the full path.

    Args:
        G: A NetworkX DiGraph representing the pipeline.

    Returns:
        A tuple of (critical_path_nodes, total_makespan_seconds).
        Returns ([], 0.0) if the graph is empty or contains cycles.
    """
    if G.number_of_nodes() == 0:
        logger.warning("Graph is empty. Cannot compute critical path.")
        return [], 0.0

    if not nx.is_directed_acyclic_graph(G):
        logger.error("Graph contains a cycle. Critical path analysis requires a DAG.")
        return [], 0.0

    # Initialise: each node's earliest finish = its own duration
    dist: Dict[str, float] = {
        node: G.nodes[node].get('duration', 0.0) for node in G.nodes()
    }

    # Track which predecessor leads to the longest path for each node
    pred_map: Dict[str, str] = {node: None for node in G.nodes()}

    # Forward pass: topological relaxation in O(V+E)
    for u in nx.topological_sort(G):
        for v in G.successors(u):
            weight_v = G.nodes[v].get('duration', 0.0)
            candidate_dist = dist[u] + weight_v

            if candidate_dist > dist[v]:
                dist[v] = candidate_dist
                pred_map[v] = u

    # Find the terminal node with the longest accumulated duration
    target_node = max(dist, key=dist.get)
    max_duration = dist[target_node]

    # Backtrack to reconstruct the critical path
    critical_path: List[str] = []
    current_node = target_node
    while current_node is not None:
        critical_path.append(current_node)
        current_node = pred_map[current_node]

    critical_path.reverse()

    logger.info(f"Critical path identified. Makespan: {max_duration:.2f}s")
    return critical_path, max_duration
