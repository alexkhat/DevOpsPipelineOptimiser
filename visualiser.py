import networkx as nx
import matplotlib.pyplot as plt
import logging
from typing import List

# visualiser.py
# Generates a static PNG image of the pipeline DAG.
# Critical path nodes are highlighted in red; all other nodes are blue.
#
# Kept as a separate module to maintain the four-component architecture:
# Parser → Analyser → Suggestion Engine → Visualiser.
# This means the graph can be produced from the CLI without any Streamlit dependency.
#
# Layout: Kamada-Kawai algorithm minimises edge crossings for sparse pipeline
# graphs. Falls back to spring layout if Kamada-Kawai fails.

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def save_pipeline_graph(
    G: nx.DiGraph,
    critical_path: List[str],
    output_path: str = "pipeline_graph.png"
) -> bool:
    """
    Renders the pipeline DAG and saves it as a PNG.

    Critical path nodes are drawn in red with a thicker border.
    All other nodes are drawn in blue.

    Returns True if saved successfully, False if the graph was empty
    or the file could not be written.
    """
    if G.number_of_nodes() == 0:
        logger.warning("Empty graph — nothing to visualise.")
        return False

    logger.info("Generating pipeline graph image...")
    plt.figure(figsize=(16, 10))

    try:
        pos = nx.kamada_kawai_layout(G)
    except Exception:
        # Fall back to spring layout for disconnected or edge-case graphs
        pos = nx.spring_layout(G, k=0.9, seed=42)

    critical_set = set(critical_path)
    non_critical = [n for n in G.nodes() if n not in critical_set]

    # Non-critical nodes — light blue
    nx.draw_networkx_nodes(
        G, pos, nodelist=non_critical,
        node_color='#BBDEFB', node_size=800,
        alpha=0.9, edgecolors='#1976D2'
    )

    # Critical path nodes — red with thicker border
    nx.draw_networkx_nodes(
        G, pos, nodelist=list(critical_set),
        node_color='#FFCDD2', node_size=1000,
        alpha=1.0, edgecolors='#D32F2F', linewidths=2
    )

    nx.draw_networkx_edges(
        G, pos, edge_color='#9E9E9E',
        arrows=True, arrowsize=15, width=1.5
    )

    # White background on labels keeps them readable over any node colour
    nx.draw_networkx_labels(
        G, pos, font_size=9, font_weight="bold",
        bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.5)
    )

    plt.title("Pipeline DAG — Critical Path Highlighted", fontsize=16, fontweight='bold', pad=20)
    plt.axis('off')

    try:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Graph saved to '{output_path}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to save graph image: {e}")
        return False
    finally:
        plt.close()  # Always close to prevent memory leaks
