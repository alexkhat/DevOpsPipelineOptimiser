import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# data_parser.py
# Parses raw CI/CD pipeline log files (GitHub Actions and Jenkins) into
# structured job data that the analyser can use to build a DAG.
#
# Supports three log formats:
#   - GitHub Actions section-based  (##[section]Starting / Finishing)
#   - GitHub Actions group-based    (##[group] / ##[endgroup])
#   - Jenkins Declarative Pipeline  ([Pipeline] { (StageName) })
#
# For Jenkins logs, the parser uses "floating timestamp" inference because
# Jenkins does not emit explicit stage-end markers — instead it reads the
# timestamp of the next line to close the previous stage's duration.
#
# References: Zhang et al. (2019) — log instability and noise tolerance.
#             Bajpai & Lewis (2022) — credential redaction in secure pipelines.

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def clean_ansi_noise(line: str) -> str:
    # Removes ANSI colour/formatting codes that terminals inject into log output.
    # Example: "\x1b[32mSUCCESS\x1b[0m" becomes "SUCCESS"
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', line)


def mask_secrets(line: str) -> str:
    # Redacts anything that looks like a credential before any downstream processing.
    # Catches patterns like: Token=abc123, PASSWORD: secret, api_key=xyz
    return re.sub(
        r'(Key|Token|Password|Secret)(\s*[:=]\s*)(\S+)',
        r'\1\2*****',
        line,
        flags=re.IGNORECASE
    )


def calculate_duration(start_time: datetime, end_time: datetime) -> float:
    # Returns the number of seconds between two timestamps.
    # Adds 86,400 seconds (one day) if the result is negative — this handles
    # pipelines that run past midnight where the end timestamp appears earlier
    # than the start timestamp numerically.
    delta = (end_time - start_time).total_seconds()
    if delta < 0:
        delta += 86400.0
    return delta


def parse_log_file(file_path: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Main entry point. Reads a log file and returns a dictionary of pipeline jobs.

    Each key is a job name. Each value contains:
        - 'start'        : datetime the job began
        - 'duration'     : how long it ran in seconds
        - 'dependencies' : list of job names this job depends on

    Returns None if the file does not exist or contains no recognisable pipeline stages.
    """
    pipeline_data: Dict[str, Dict[str, Any]] = {}
    last_job_name: Optional[str] = None       # tracks the previous job for dependency chaining
    current_open_job: Optional[str] = None    # the job currently being timed
    last_seen_time: Optional[datetime] = None # most recent timestamp seen anywhere in the log

    # --- Compiled regex patterns ---
    ts_iso_pattern     = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")  # GitHub ISO 8601
    ts_simple_pattern  = re.compile(r"(\d{2}:\d{2}:\d{2})")                     # Jenkins HH:MM:SS
    gh_group_pattern   = re.compile(r"##\[group\](.+)")
    gh_group_end       = re.compile(r"##\[endgroup\]")
    gh_section_pattern = re.compile(r"##\[section\](Starting|Finishing): (.+)")
    jenkins_pattern    = re.compile(r"\[Pipeline\] \{ \((.+?)\)")

    logger.info(f"Parsing log file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            for line_num, line in enumerate(file, 1):
                line = clean_ansi_noise(line.strip())
                line = mask_secrets(line)

                # ── Timestamp extraction ──────────────────────────────────────
                # Try ISO format first (GitHub Actions), fall back to HH:MM:SS (Jenkins).
                current_time = None
                ts_iso_match = ts_iso_pattern.search(line)
                if ts_iso_match:
                    try:
                        current_time = datetime.strptime(ts_iso_match.group(1), "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        pass
                else:
                    ts_simple_match = ts_simple_pattern.search(line)
                    if ts_simple_match:
                        try:
                            current_time = datetime.strptime(ts_simple_match.group(1), "%H:%M:%S")
                        except ValueError:
                            pass

                if current_time:
                    last_seen_time = current_time

                    # Jenkins floating timestamp: if a job was declared without a
                    # timestamp (start=None), use the first timestamp we encounter
                    # afterwards as its start, and close the job before it.
                    if current_open_job and current_open_job in pipeline_data:
                        if pipeline_data[current_open_job].get('start') is None:
                            pipeline_data[current_open_job]['start'] = current_time
                            deps = pipeline_data[current_open_job].get('dependencies', [])
                            if deps:
                                prev_job = deps[0]
                                prev_start = pipeline_data.get(prev_job, {}).get('start')
                                if prev_start:
                                    pipeline_data[prev_job]['duration'] = calculate_duration(
                                        prev_start, current_time
                                    )

                # ── GitHub Actions: section-based ─────────────────────────────
                # Format: "2026-01-01T10:00:00 ##[section]Starting: Build"
                m_sect = gh_section_pattern.search(line)
                if m_sect and last_seen_time:
                    action   = m_sect.group(1)
                    job_name = m_sect.group(2).strip()

                    if action == "Starting":
                        if current_open_job and current_open_job in pipeline_data:
                            start_t = pipeline_data[current_open_job].get('start')
                            if start_t:
                                pipeline_data[current_open_job]['duration'] = calculate_duration(
                                    start_t, last_seen_time
                                )
                        if job_name not in pipeline_data:
                            pipeline_data[job_name] = {
                                'dependencies': [],
                                'start': last_seen_time
                            }
                            if last_job_name and last_job_name != job_name:
                                pipeline_data[job_name]['dependencies'].append(last_job_name)
                        current_open_job = job_name
                        last_job_name    = job_name

                    elif action == "Finishing":
                        if job_name in pipeline_data:
                            start_t = pipeline_data[job_name].get('start')
                            if start_t:
                                pipeline_data[job_name]['duration'] = calculate_duration(
                                    start_t, last_seen_time
                                )
                            if current_open_job == job_name:
                                current_open_job = None
                    continue

                # ── GitHub Actions: group-based ───────────────────────────────
                # Format: "##[group]Install Dependencies"
                m_group = gh_group_pattern.search(line)
                if m_group and last_seen_time:
                    job_name = m_group.group(1).strip()
                    if current_open_job and current_open_job in pipeline_data:
                        start_t = pipeline_data[current_open_job].get('start')
                        if start_t:
                            pipeline_data[current_open_job]['duration'] = calculate_duration(
                                start_t, last_seen_time
                            )
                    if job_name not in pipeline_data:
                        pipeline_data[job_name] = {
                            'dependencies': [],
                            'start': last_seen_time
                        }
                        if last_job_name and last_job_name != job_name:
                            pipeline_data[job_name]['dependencies'].append(last_job_name)
                    current_open_job = job_name
                    last_job_name    = job_name
                    continue

                if gh_group_end.search(line) and current_open_job and last_seen_time:
                    if current_open_job in pipeline_data:
                        start_t = pipeline_data[current_open_job].get('start')
                        if start_t:
                            pipeline_data[current_open_job]['duration'] = calculate_duration(
                                start_t, last_seen_time
                            )
                    current_open_job = None
                    continue

                # ── Jenkins Declarative Pipeline ──────────────────────────────
                # Format: "[Pipeline] { (StageName)"
                # Jenkins does not emit end markers, so start is set to None here
                # and filled in by the floating timestamp logic above.
                m_jenkins = jenkins_pattern.search(line)
                if m_jenkins:
                    job_name = m_jenkins.group(1).strip()
                    pipeline_data[job_name] = {
                        'dependencies': [last_job_name] if last_job_name else [],
                        'start': None
                    }
                    current_open_job = job_name
                    last_job_name    = job_name
                    continue

        # End of file — close any job that was still open
        if current_open_job and current_open_job in pipeline_data and last_seen_time:
            start_t = pipeline_data[current_open_job].get('start')
            if start_t:
                pipeline_data[current_open_job]['duration'] = calculate_duration(
                    start_t, last_seen_time
                )

    except FileNotFoundError:
        logger.error(f"Log file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during parsing: {str(e)}")
        return None

    # Only keep jobs that have a valid, non-negative duration
    clean_data = {
        k: v for k, v in pipeline_data.items()
        if 'duration' in v and v['duration'] >= 0
    }

    logger.info(f"Parsing complete. Extracted {len(clean_data)} valid pipeline stages.")
    return clean_data if clean_data else None
