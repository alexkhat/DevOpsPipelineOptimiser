import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional


# ==============================================================================
# MODULE: Data_parser.py
# ACADEMIC JUSTIFICATION:
# 1. Handling "Log Instability" (Zhang et al., 2019).
# 2. Sequential Temporal Inference for missing DAG boundaries
# ==============================================================================

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def clean_ansi_noise(line: str) -> str:
    """
    Sanitises unstructured log lines by removing ANSI escape sequences.

    Args:
        line (str): The raw log line.
    Returns:
        str: The cleaned log line.
   """
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', line)


def mask_secrets(line: str) -> str:
    """
    Masks potential secrets in the logs to ensure zero-trust security compliance.

    Args:
        line (str): The sanitised log line.
    Returns:
        str: The log line with masked secrets.
    """
    return re.sub(r'(Key|Token|Password|Secret)(\s*[:=]\s*)(\S+)', r'\1\2*****', line, flags=re.IGNORECASE)


def parse_log_file(file_path: str) -> Optional[Dict[str, Dict[str, Any]]]:
    pipeline_data: Dict[str, Dict[str, Any]] = {}
    last_job_name: Optional[str] = None
    current_open_job: Optional[str] = None

    # ---------------------------------------------------------
    # REGEX PATTERNS
    # ---------------------------------------------------------

    # ISO Timestamp
    ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")

    # Matches: ##[group]Job Name
    gh_group_pattern = re.compile(r"##\[group\](.+)")
    gh_group_end = re.compile(r"##\[endgroup\]")

    # Matches: ##[section]Starting: Job Name
    gh_section_pattern = re.compile(r"##\[section\](Starting|Finishing): (.+)")

    # Jenkins Pipeline
    jenkins_pattern = re.compile(r"\[Pipeline\] \{ \((.+?)\)")

    #Simple Format
    simple_start = re.compile(r"Starting job: (.+)")
    simple_end = re.compile(r"Job (.+) finished at (.+)")

    logger.info(f"Initiating parsing of unstable log artefact: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            for line_num, line in enumerate(file, 1):
                line = clean_ansi_noise(line.strip())
                line = mask_secrets(line)

                # --- EXTRACT TIMESTAMP ---
                ts_match = ts_pattern.search(line)
                current_time: Optional[datetime] = None

                if ts_match:
                    try:
                        current_time = datetime.strptime(ts_match.group(1), "%Y-%m-%dT%H:%M:%S")
                    except ValueError as ve:
                        logger.debug(f"Timestamp parse error on line {line_num}: {ve}")
                        pass


                if not current_time: continue # Skip noise lines without temporal data

                # =========================================================
                # LOGIC A: GITHUB WORKFLOW LOGS (##[section])
                # =========================================================
                m_sect = gh_section_pattern.search(line)
                if m_sect:
                    action = m_sect.group(1)
                    job_name = m_sect.group(2).strip()

                    if action == "Starting":
                        # Auto-close previous (Sequential Inference)
                        if current_open_job and current_open_job in pipeline_data:
                            start_t = pipeline_data[current_open_job]['start']
                            pipeline_data[current_open_job]['end'] = current_time
                            pipeline_data[current_open_job]['duration'] = (current_time - start_t).total_seconds()


                        # Register new job
                        if job_name not in pipeline_data:
                            pipeline_data[job_name] = {'dependencies': [], 'start': current_time}
                            if last_job_name and last_job_name != job_name:
                                pipeline_data[job_name]['dependencies'].append(last_job_name)

                        current_open_job = job_name
                        last_job_name = job_name

                    elif action == "Finishing":
                        if job_name in pipeline_data:
                            start_t = pipeline_data[job_name]['start']
                            pipeline_data[job_name]['end'] = current_time
                            pipeline_data[job_name]['duration'] = (current_time - start_t).total_seconds()
                            if current_open_job == job_name:
                                current_open_job = None

                    continue  # Move to next line

                # =========================================================
                # LOGIC B: GITHUB RAW LOGS (##[group])
                # =========================================================
                m_group = gh_group_pattern.search(line)
                if m_group:
                    job_name = m_group.group(1).strip()

                    # Close previous
                    if current_open_job and current_open_job in pipeline_data:
                        start_t = pipeline_data[current_open_job]['start']
                        pipeline_data[current_open_job]['end'] = current_time
                        pipeline_data[current_open_job]['duration'] = (current_time - start_t).total_seconds()

                    # Start new
                    if job_name not in pipeline_data:
                        pipeline_data[job_name] = {'dependencies': [], 'start': current_time}
                        if last_job_name and last_job_name != job_name:
                            pipeline_data[job_name]['dependencies'].append(last_job_name)

                    current_open_job = job_name
                    last_job_name = job_name
                    continue

                if gh_group_end.search(line) and current_open_job:
                    start_t = pipeline_data[current_open_job]['start']
                    pipeline_data[current_open_job]['end'] = current_time
                    pipeline_data[current_open_job]['duration'] = (current_time - start_t).total_seconds()
                    current_open_job = None
                    continue

                # =========================================================
                # LOGIC C: JENKINS & SIMPLE
                # =========================================================
                m_jenkins = jenkins_pattern.search(line)
                if m_jenkins:
                    job_name = m_jenkins.group(1).strip()
                    if last_job_name and last_job_name in pipeline_data:
                        start_t = pipeline_data[last_job_name]['start']
                        pipeline_data[last_job_name]['end'] = current_time
                        pipeline_data[last_job_name]['duration'] = (
                                    current_time - start_t).total_seconds()
                        pipeline_data[job_name] = {'dependencies': [last_job_name], 'start': current_time}
                    else:
                        pipeline_data[job_name] = {'dependencies': [], 'start': current_time}
                    last_job_name = job_name
                    continue



    except FileNotFoundError:
        logger.error(f"Critical Error: File '{file_path}'not found.")
        return None
    except Exception as e:
        logger.error(f"Critical Error during parsing: {str(e)}")
        return None

    # Mathematical Validation: Filter out nodes lacking a valid calculated duration weight
    clean_data = {k: v for k, v in pipeline_data.items() if 'duration' in v}
    logger.info(f"Parsing Complete. Reconstructed graph topology with {len(clean_data)} valid nodes.")
    return clean_data
