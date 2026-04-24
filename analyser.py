import networkx as nx
import logging
from typing import Dict, List, Tuple, Any

# analyser.py
# Converts parsed pipeline data into a Directed Acyclic Graph (DAG) and
# computes the Critical Path — the longest chain of dependent stages that
# determines the minimum possible pipeline duration (makespan).
#
# Algorithm: topological sort + forward-pass edge relaxation — O(V+E).
# This is deterministic: the same input always produces the same output.
#
# References: Agarwal (2025) — CPA as the standard for pipeline measurement.
#             Düllmann et al. (2021) — model-driven pipeline analysis (StalkCD).

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def build_dag(pipeline_data: Dict[str, Dict[str, Any]]) -> nx.DiGraph:
    """
    Builds a weighted directed graph from the parser's output.

    Each pipeline job becomes a node weighted by its duration.
    Each dependency relationship becomes a directed edge (parent → child).
    """
    G = nx.DiGraph()
    logger.info("Building DAG from pipeline data.")

    for job, attributes in pipeline_data.items():
        duration = attributes.get('duration', 0.0)
        G.add_node(job, duration=duration)

        for parent in attributes.get('dependencies', []):
            if parent in pipeline_data:
                G.add_edge(parent, job)

    logger.info(f"DAG built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    return G


def calculate_critical_path(G: nx.DiGraph) -> Tuple[List[str], float]:
    """
    Finds the critical path (longest weighted path) through the pipeline DAG.

    Steps:
      1. Initialise every node's distance to its own duration.
      2. Walk nodes in topological order.
      3. For each node, propagate its accumulated distance to successors —
         updating if the new route is longer (relaxation).
      4. The node with the highest final distance is the pipeline's end.
      5. Backtrack through the predecessor map to reconstruct the full path.

    Returns ([], 0.0) if the graph is empty or contains a cycle.
    """
    if G.number_of_nodes() == 0:
        logger.warning("Empty graph — cannot compute critical path.")
        return [], 0.0

    if not nx.is_directed_acyclic_graph(G):
        logger.error("Cycle detected in graph. Critical path requires a DAG.")
        return [], 0.0

    # Each node starts with a distance equal to its own duration
    dist: Dict[str, float] = {
        node: G.nodes[node].get('duration', 0.0) for node in G.nodes()
    }

    # Records which predecessor gave each node its longest route
    pred_map: Dict[str, str] = {node: None for node in G.nodes()}

    # Forward pass — process in topological order so every parent is
    # settled before we look at its children
    for u in nx.topological_sort(G):
        for v in G.successors(u):
            candidate = dist[u] + G.nodes[v].get('duration', 0.0)
            if candidate > dist[v]:
                dist[v]     = candidate
                pred_map[v] = u

    # The node with the maximum accumulated distance is the path's end
    target_node  = max(dist, key=dist.get)
    max_duration = dist[target_node]

    # Walk backwards through predecessors, then reverse to get correct order
    critical_path: List[str] = []
    current = target_node
    while current is not None:
        critical_path.append(current)
        current = pred_map[current]
    critical_path.reverse()

    logger.info(f"Critical path found. Makespan: {max_duration:.2f}s")
    return critical_path, max_duration
