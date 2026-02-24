import networkx as nx
import matplotlib.pyplot as plt
import logging
from typing import Dict, List, Tuple, Any

from networkx.algorithms.shortest_paths.unweighted import predecessor

# ==============================================================================
# MODULE: Graph Analyser (analyser.py)
# DESCRIPTION: Transforms sequential data into a Directed Acyclic Graph (DAG)
#               and executes O(V+E) Critical Path Analysis via Topological Sorting.
# ==============================================================================

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def build_dag(pipeline_data: Dict[str, Dict[str, Any]]) -> nx.DiGraph:
    """
    Constructs a mathematical Directed Acyclic Graph (DAG) from parsed log data.

    Mapping Logic:
    - Nodes (V) = Individual Jobs
    - Edges (E) = Dependency Constraints
    - Weights (W) = Job Durations

    Args:
        pipeline_data (Dict): The structured dictionary from the data parser.

    Returns:
        nx.DiGraph: A NetworkX Directed Graph topological model.
    """
    G = nx.DiGraph()
    logger.info("Constructing Directed Acyclic Graph (DAG) topology.")

    for job, attributes in pipeline_data.items():
        # Add Node with Duration as a metadata attribute
        # Node (V) and Weight (W) assignment
        duration = attributes.get('duration', 0.0)
        G.add_node(job, duration=duration)

        # Add Directed Edges for Dependencies (Parent -> Child)
        # Edge (E) assignment mapping temporal dependencies
        for parent in attributes.get('dependencies', []):
            if parent in pipeline_data:
                G.add_edge(parent, job)
    logger.info(f"DAG Module Built: |V|={G.number_of_nodes()} Nodes, |E|={G.number_of_edges()} Edges.")
    return G


def calculate_critical_path(G: nx.DiGraph) -> Tuple[List[str], float]:
    """
    Identifies the Critical Path (Longest Path) in the DAG.

    ALGORITHM: Topological Sort + Dynamic Programming
    COMPLEXITY: Linear Time O(|V| + |E|), replacing O(2^V) path iteration

    Args:
        G (nx.DiGraph): The weighted pipeline graph.

    Returns:
        Tuple[List[str], float]: The sequence of job on the critical path, Total Duration in seconds
    """
    if G.number_of_nodes() == 0:
        logger.warning("Graph is empty. Cannot compute Critical Path")
        return [], 0.0
    if not nx.is_directed_acyclic_graph(G):
        logger.error("Mathematical Violation: Graph contains a cyclic deadlock.")
        return [], 0.0

    # Initialize Distance (dist) and Path History (predecessor) trackers
    dist: Dict[str, float] = {node: G.nodes[node].get('duration', 0.0) for node in G.nodes()}
    predecessor: Dict[str, str] = {node: None for node in G.nodes()}

    # O(V+E) Topological Relaxation
    # This evaluates the graph logically from start to finish without redundant iteration
    for u in nx.topological_sort(G):
        for v in G.successors(u):
            weight_v = G.nodes[v].get('duration', 0.0)
            # Relaxation Step: if the path through 'u' to 'v' is longer than the known path to 'v'
            if dist[u] + weight_v > dist[v]:
                dist[v] = dist[u] + weight_v
                predecessor[v] = u

    # identify the terminal node with the absolute longest accumulated duration (Makespan)
    target_node = max(dist, key=dist.get)
    max_duration = dist[target_node]

    # Backtrack through the predecessors to reconstruct the exact path
    critical_path: List[str] = []
    current_node = target_node
    while current_node is not None:
        critical_path.append(current_node)
        current_node = predecessor[current_node]

    critical_path.reverse() # Reverse to display from Start -> End

    logger.info(f"Critical path mathematically verified. Makespan: {max_duration:.2f}s")
    return critical_path, max_duration


def visualize_graph(G: nx.DiGraph, critical_path: List[str]) -> None:
    """
    Generates a high-resolution topological artifact for the thesis document.
    Red nodes indicate elements on the Critical Path.
    """
    if G.number_of_nodes() == 0:
        return

    logger.info("Generating high-resolution topological visualisation...")
    plt.figure(figsize=(16, 10))

    try:
        # Kamada-Kawai distributes complex DAGs evenly
        pos = nx.kamada_kawai_layout(G)
    except Exception:
        pos = nx.spring_layout(G, k=0.9, seed=42)

    critical_set = set(critical_path)
    non_critical = [n for n in G.nodes() if n not in critical_set]

    # Draw Standard Nodes (Blue)
    nx.draw_networkx_nodes(G, pos, nodelist=non_critical, node_color='#BBDEFB',
                           node_size=800, alpha=0.9, edgecolors='#1976D2')
    # Draw Critical Nodes (Red)
    nx.draw_networkx_nodes(G, pos, nodelist=critical_path, node_color='#FFCDD2',
                           node_size=1000, alpha=1.0, edgecolors='#D32F2F', linewidths=2)

    nx.draw_networkx_edges(G, pos, edge_color='#9E9E9E', arrows=True, arrowsize=15, width=1.5)

    nx.draw_networkx_labels(G, pos, font_size=9, font_weight="bold",
                            bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.5))

    plt.title("DAG Topology & Deterministic Critical Path Identification", fontsize=16, fontweight='bold', pad=20)
    plt.axis('off')

    try:
        plt.savefig("pipeline_graph.png", dpi=300, bbox_inches='tight')
        logger.info("Artifact successfully saved as 'pipeline_graph.png'")
    except Exception as e:
        logger.error(f"Failed to save visualisation artifact: {e}")
    finally:
        plt.close()  # Prevent memory leaks in Streamlit
