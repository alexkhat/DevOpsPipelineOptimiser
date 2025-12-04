from typing import List, Tuple


def generate_recommendations(critical_path: List[str], makespan: float, bottleneck_task: str, max_duration: float,
                             makespan_reduction_target: float = 0.30) -> List[str]:
    """
    PURPOSE: Translates raw Critical Path analysis into actionable, rule-based
    optimization advice (Heuristics). This module acts as the automated DevOps
    Consultant, prescribing fixes for detected bottlenecks.

    Args:
        critical_path (List[str]): The exact sequence of tasks causing the max delay.
        makespan (float): The current total pipeline runtime (Makespan).
        bottleneck_task (str): The single longest task on the critical path.
        max_duration (float): The duration of the bottleneck task.
        makespan_reduction_target (float): The target percentage reduction (e.g., 0.30 for 30%).

    Returns:
        List[str]: A list of prioritized recommendations for the developer.
    """

    recommendations = []
    # Calculate the minimum time we need to save to meet the project's goal.
    target_reduction_seconds = makespan * makespan_reduction_target

    # ----------------------------------------------------
    # RULE 1: HIGH PRIORITY - STRUCTURAL BOTTLENECKS (Testing/Build)
    # Heuristic: Slow, dominant tasks (e.g., E2E tests) should be split via parallelism.
    # ----------------------------------------------------
    if 'e2e' in bottleneck_task.lower() and max_duration > target_reduction_seconds:
        recommendations.append(
            f"1.  HIGH PRIORITY (Structural Optimization): The task '{bottleneck_task}' consumes {max_duration:.0f}s. "
            f"**ACTION: Implement Parallel Test Matrix.** Use multiple runners (e.g., 4x parallelism) to distribute this load, drastically cutting the critical path time."
        )

    # ----------------------------------------------------
    # RULE 2: MEDIUM PRIORITY - RESOURCE BOTTLENECKS (Installation/Caching)
    # Heuristic: Repetitive tasks (installs) should be fixed via caching.
    # ----------------------------------------------------
    elif 'install' in bottleneck_task.lower():
        recommendations.append(
            f"2. MEDIUM PRIORITY (Resource Optimization): The task '{bottleneck_task}' involves package management. "
            f"**ACTION: Implement Dependency Caching.** Configure your CI system to cache dependencies, eliminating this repeated time sink on subsequent runs."
        )

    # ----------------------------------------------------
    # RULE 3: LOW PRIORITY - GENERAL TIME SINKS
    # Heuristic: When the cause is not obvious, suggest general script and resource review.
    # ----------------------------------------------------
    else:
        recommendations.append(
            f"3. GENERAL OPTIMIZATION: Task '{bottleneck_task}' is a significant, non-obvious time sink. "
            f"**ACTION: Review Script Efficiency.** Verify resource limits (CPU/Memory) on the runner and analyze the underlying script logic for inefficiencies."
        )

    # Final summary of the project's quantifiable goal (ROI).
    recommendations.append(
        f"\nTotal Pipeline Savings Goal: Target a minimum reduction of {target_reduction_seconds:.0f}s ({int(makespan_reduction_target * 100)}%) from the current Makespan ({makespan:.0f}s). **Focusing on the recommended action is essential to achieve this ROI.**"
    )

    return recommendations