import networkx as nx  # Core library for graph modeling (DAGs)
import pandas as pd  # Used to structure and handle input data efficiently
from typing import List, Tuple
import matplotlib.pyplot as plt  # Visualization library for drawing the graph
import os  # Used for file operations (deleting old image file)
import copy  # Crucial for the simulation module (avoids modifying original data)


class PipelineAnalyzer:
    """
    CORE ANALYTICAL ENGINE: This class is the 'brain' of the optimizer.
    It is responsible for modeling the CI/CD pipeline using the Directed Acyclic Graph
    (DAG) theory and calculating the Critical Path (CPM).
    """

    def __init__(self, structured_data: pd.DataFrame):
        # Initializes a Directed Graph, which enforces one-way flow (like a flowchart).
        self.graph = nx.DiGraph()
        self.data = structured_data
        self._build_dag()  # Immediately start constructing the graph model

    def _build_dag(self):
        """
        Translates the structured data (DataFrame) into a network model.
        Tasks become nodes, and dependencies become zero-weight edges.
        """
        for _, row in self.data.iterrows():
            task_name = row['task_name']
            duration = row['duration_seconds']
            dependencies = row['dependencies']

            # 1. Add the Task (Node)
            # The 'duration' attribute is the 'weight' used in the Critical Path calculation.
            self.graph.add_node(task_name, duration=duration, name=task_name)

            # 2. Add Dependencies (Edges)
            if dependencies:
                for parent_task in dependencies:
                    # Edges show precedence; their weight is zero as the time is on the node.
                    self.graph.add_edge(parent_task, task_name, weight=0)

                    # Note: This print is primarily for console debugging during development.
        print("DAG successfully constructed.")

    def find_critical_path(self) -> Tuple[List[str], float]:
        """
        CRITICAL PATH METHOD (CPM): Calculates the longest path (Makespan) and
        the sequence of tasks on that path.
        """

        # Safety Check 1: A pipeline must be acyclic (no task can wait for itself indirectly).
        if not nx.is_directed_acyclic_graph(self.graph):
            return ["ERROR_CYCLE"], 0.0

        def path_length_by_duration(path: List[str]) -> float:
            """Helper function to calculate path length by summing node durations (CPM)."""
            total_duration = 0.0
            for node in path:
                total_duration += self.graph.nodes[node].get('duration', 0)
            return total_duration

        try:
            # 1. Find all possible start nodes (no incoming edges) and end nodes (no outgoing edges)
            start_nodes = list(n for n in self.graph if self.graph.in_degree(n) == 0)
            end_nodes = list(n for n in self.graph if self.graph.out_degree(n) == 0)

            if not start_nodes or not end_nodes:
                return ["ERROR_DISCONNECTED"], 0.0

            # 2. Find ALL simple paths between any start node and any end node
            all_paths = []
            for start in start_nodes:
                for end in end_nodes:
                    all_paths.extend(nx.all_simple_paths(self.graph, start, end))

            if not all_paths:
                return ["ERROR_NOPATH"], 0.0

            # 3. Identify the Critical Path
            # The critical path is simply the one with the maximum cumulative duration.
            critical_path_nodes = max(all_paths, key=path_length_by_duration)
            makespan = path_length_by_duration(critical_path_nodes)

            return critical_path_nodes, makespan

        except Exception as e:
            # Catch general errors during complex pathfinding
            print(f"DEBUG: Detailed Pathfinding Error: {e}")
            return ["ERROR_GENERIC"], 0.0

    def run_optimization_simulation(self, task_to_reduce: str, reduction_factor: float) -> Tuple[float, float]:
        """
        SIMULATION MODULE: Predicts the quantifiable ROI of an optimization.
        It modifies the bottleneck task's duration and recalculates the Makespan.
        """
        if task_to_reduce not in self.graph.nodes:
            return self.find_critical_path()[1], 0.0  # Return current Makespan if task not found

        # 1. Create a Deep Copy: CRUCIAL to avoid modifying the original data.
        simulated_graph = copy.deepcopy(self.graph)

        # 2. Apply the Simulated Reduction (e.g., 75% reduction via parallelism)
        original_duration = simulated_graph.nodes[task_to_reduce]['duration']
        new_duration = original_duration * (1.0 - reduction_factor)

        # Update the node duration in the simulated graph
        simulated_graph.nodes[task_to_reduce]['duration'] = new_duration

        # 3. Recalculate Critical Path on the Simulated Graph
        # Use a temporary analyzer instance for the new calculation
        temp_analyzer = PipelineAnalyzer(pd.DataFrame())
        temp_analyzer.graph = simulated_graph

        # The new Makespan is the predicted performance after optimization
        _, new_makespan = temp_analyzer.find_critical_path()

        # 4. Calculate Savings
        original_makespan = self.find_critical_path()[1]
        time_saved = original_makespan - new_makespan

        return new_makespan, time_saved

    def draw_pipeline_graph(self, critical_path: List[str]):
        """
        VISUALIZER MODULE: Renders the DAG and highlights the Critical Path.
        This turns complex math into an easily understandable picture.
        """
        output_filename = "pipeline_dag_output.png"

        # Ensure the old image file is deleted so Streamlit displays the newest version
        if os.path.exists(output_filename):
            os.remove(output_filename)

        plt.figure(figsize=(16, 12))

        # 1. Define Visual Properties
        # Nodes on the critical path are RED; others are blue/grey.
        node_colors = ['#A0CBE2' if node not in critical_path else '#FF6347' for node in self.graph.nodes()]

        # Labels display the Name and Duration (the time sink)
        node_labels = {node: f"{self.graph.nodes[node]['name']}\n({self.graph.nodes[node]['duration']}s)"
                       for node in self.graph.nodes()}

        # Edges on the critical path are also RED.
        critical_edges = []
        for i in range(len(critical_path) - 1):
            critical_edges.append((critical_path[i], critical_path[i + 1]))
        edge_colors = ['gray' if (u, v) not in critical_edges else '#FF6347'
                       for u, v in self.graph.edges()]

        # Use a spring layout for complex graphs (pushes nodes apart nicely)
        pos = nx.spring_layout(self.graph, k=0.8, iterations=50)

        # 2. Draw Components
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, node_size=3800, alpha=0.9, linewidths=1.5,
                               edgecolors='black')
        nx.draw_networkx_labels(self.graph, pos, labels=node_labels, font_size=9, font_weight="bold",
                                font_color='black')
        nx.draw_networkx_edges(self.graph, pos, edge_color=edge_colors, width=3, arrowsize=25, alpha=0.7)

        # 3. Finalize and Save
        plt.title("CI/CD Pipeline Critical Path Analysis (Bottleneck Visualization)", fontsize=18)
        plt.axis('off')
        plt.savefig(output_filename, bbox_inches='tight')
        plt.close()