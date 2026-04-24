import logging
from typing import List, Dict, Any
from dataclasses import dataclass

# suggestion_engine.py
# Analyses critical path jobs and generates rule-based optimisation
# recommendations. Only jobs ON the critical path are evaluated — jobs
# off the path have scheduling slack and cannot affect makespan.
#
# Each job is classified as compute-bound, I/O-bound, or general using
# keyword matching. An absolute duration fallback (LONG_JOB_SECONDS)
# ensures significant jobs are never silently ignored in large pipelines.
#
# No machine learning is used — every recommendation is directly traceable
# to job name, duration, and percentage of makespan.
#
# References: Barredo Arrieta et al. (2020) — explainability requirements.
#             Zampetti et al. (2020) — CI bad smells and anti-pattern taxonomy.

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """
    A single structured optimisation recommendation.
    All five fields are populated for every non-info recommendation,
    allowing the CLI and dashboard to render them identically.
    """
    category:   str    # 'compute', 'io', 'general', or 'info'
    job_name:   str    # the pipeline stage this targets
    impact_pct: float  # percentage of total makespan this job consumes
    duration:   float  # job duration in seconds
    message:    str    # human-readable recommendation text


# Compute-bound keywords — CPU-intensive tasks: testing, scanning, building
COMPUTE_KEYWORDS = [
    'test', 'unit', 'integration', 'e2e', 'spec', 'jest', 'pytest',
    'mocha', 'jasmine', 'rspec', 'junit', 'coverage', 'fuzz',
    'lint', 'eslint', 'pylint', 'flake', 'rubocop', 'checkstyle',
    'analyze', 'analyse', 'sonar', 'codeclimate', 'verify', 'validate',
    'scan', 'sast', 'dast', 'security', 'snyk', 'checkmarx', 'trivy',
    'dependency-check', 'audit',
    'build', 'compile', 'webpack', 'gradle', 'maven', 'cmake', 'make',
    'bundle', 'transpile', 'minify', 'package',
]

# I/O-bound keywords — tasks that primarily wait on network or disk
IO_KEYWORDS = [
    'install', 'npm', 'yarn', 'pip', 'gem', 'composer', 'cargo',
    'restore', 'download', 'fetch',
    'checkout', 'clone', 'pull', 'push',
    'cache', 'cached',
    'upload', 'publish', 'deploy', 'release', 'docker', 'image',
    'registry', 'artifact', 's3', 'bucket',
    'setup', 'provision', 'runner', 'provisioner',
]

# Jobs running longer than this are always flagged regardless of percentage.
# Prevents significant bottlenecks being missed in large pipelines.
LONG_JOB_SECONDS = 60.0


def _classify_job(job_name: str, duration: float) -> str:
    # Compute takes priority over I/O if both match.
    # If no keyword matches but the job ran for a long time, default to
    # compute — prolonged unrecognised tasks are almost always processing steps.
    job_lower = job_name.lower()
    if any(kw in job_lower for kw in COMPUTE_KEYWORDS):
        return 'compute'
    if any(kw in job_lower for kw in IO_KEYWORDS):
        return 'io'
    if duration >= LONG_JOB_SECONDS:
        logger.info(f"Duration fallback: '{job_name}' ({duration:.1f}s) → compute-bound.")
        return 'compute'
    return 'general'


def _build_message(category: str, job_name: str, impact_pct: float, duration: float) -> str:
    # Each message includes job name, percentage, and duration so the engineer
    # can verify it without consulting any model or confidence score.
    base = f"'{job_name}' consumes {impact_pct:.1f}% of total time ({duration:.1f}s). "
    if category == 'compute':
        return base + (
            "This is a compute-bound task. Consider parallel sharding, matrix "
            "execution, or splitting into smaller independent suites."
        )
    elif category == 'io':
        return base + (
            "This is an I/O-bound task. Consider dependency caching, artifact "
            "proxying, pre-built base images, or shallow clones."
        )
    else:
        return base + (
            "Review this task's configuration. Consider splitting it, adding "
            "caching, or parallelising independent sub-steps."
        )


def generate_suggestions(
    critical_path:  List[str],
    pipeline_data:  Dict[str, Dict[str, Any]],
    total_duration: float,
    threshold:      float = 0.10
) -> List[Recommendation]:
    """
    Generates optimisation recommendations for critical path stages.

    A job is flagged if either condition is met:
      - Its share of the total makespan >= threshold (default 10%), OR
      - Its absolute duration >= LONG_JOB_SECONDS (60s)

    A noise floor filters out micro-tasks too short to be meaningful
    (< 5s normally, < 0.1s for pipelines under 10s total).

    Returns a list sorted by impact descending. If nothing is flagged,
    returns a single informational item explaining why.
    """
    recommendations: List[Recommendation] = []

    if total_duration <= 0:
        return [Recommendation(
            category='info', job_name='N/A', impact_pct=0.0, duration=0.0,
            message="Pipeline duration is zero or invalid. Check log file format."
        )]

    noise_limit = 0.1 if total_duration < 10 else 5.0

    for job in critical_path:
        duration = pipeline_data.get(job, {}).get('duration', 0.0)

        if duration < noise_limit:
            continue

        impact = duration / total_duration

        if impact < threshold and duration < LONG_JOB_SECONDS:
            continue

        category = _classify_job(job, duration)
        message  = _build_message(category, job, impact * 100, duration)

        recommendations.append(Recommendation(
            category=category,
            job_name=job,
            impact_pct=round(impact * 100, 1),
            duration=duration,
            message=message
        ))

    recommendations.sort(key=lambda r: r.impact_pct, reverse=True)

    if not recommendations:
        recommendations.append(Recommendation(
            category='info', job_name='N/A', impact_pct=0.0, duration=0.0,
            message=(
                f"No significant bottlenecks found. All critical path tasks are "
                f"below the {threshold * 100:.0f}% threshold and under {LONG_JOB_SECONDS:.0f}s."
            )
        ))

    return recommendations
