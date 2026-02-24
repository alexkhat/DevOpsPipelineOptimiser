import logging
from typing import List, Dict, Any

# ==============================================================================
# MODULE: Suggestion Engine
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def generate_suggestions(
        critical_path: List[str],
        pipeline_data: Dict[str, Dict[str, Any]],
        total_duration: float,
        threshold: float = 0.20
) -> List[str]:
    recommendations: List[str] = []

    if total_duration <= 0:
        return ["[SYSTEM] Pipeline duration is zero or invalid."]

    noise_limit: float = 0.1 if total_duration < 10 else 5.0

    for job in critical_path:
        duration: float = pipeline_data.get(job, {}).get('duration', 0.0)

        if duration < noise_limit:
            continue

        impact: float = duration / total_duration
        rule_applied = False

        job_lower = job.lower()
        is_compute_heavy = any(keyword in job_lower for keyword in ['test', 'fuzz', 'scan', 'security', 'sast', 'dast'])
        is_io_heavy = any(
            keyword in job_lower for keyword in ['install', 'setup', 'download', 'checkout', 'npm', 'yarn'])

        # THIS IS THE FIXED INDENTATION BLOCK
        if impact > threshold:
            if is_compute_heavy:
                recommendations.append(
                    f"[DEVSECOPS BOTTLENECK] Job '{job}' consumes {impact * 100:.1f}% of total time ({duration:.1f}s). "
                    f"Action: Compute-bound task. Implement parallel sharding or matrix execution strategy."
                )
                rule_applied = True

            elif is_io_heavy:
                recommendations.append(
                    f"[I/O BOTTLENECK] '{job}' consumes {impact * 100:.1f}% of total time ({duration:.1f}s). "
                    f"Action: Network/Disk bound task. Implement aggressive dependency caching or vendor artifact proxying."
                )
                rule_applied = True

            if not rule_applied:
                recommendations.append(
                    f"[GENERAL BOTTLENECK] '{job}' consumes {impact * 100:.1f}% of total time ({duration:.1f}s). "
                    f"Action: Review source code or infrastructure allocation for execution inefficiencies."
                )

    if not recommendations:
        recommendations.append(
            f"No significant bottlenecks found. All the tasks are below the {threshold * 100}% impact threshold or smaller than {noise_limit}s.")

    return recommendations
