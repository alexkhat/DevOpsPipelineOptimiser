# DevOps Pipeline Optimiser

> **A deterministic, graph-theoretic tool for CI/CD bottleneck detection and explainable optimisation.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.32%2B-red.svg)](https://streamlit.io/)
[![NetworkX](https://img.shields.io/badge/networkx-3.0%2B-orange.svg)](https://networkx.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## What It Does

Modern CI/CD pipelines slow down over time due to structural bottlenecks — but existing platforms like GitHub Actions and Jenkins only report *what happened*, not *why* a pipeline is slow or *what to change*.

This tool reads a **single raw log file**, reconstructs the pipeline as a **Directed Acyclic Graph (DAG)**, and pinpoints exactly which stages cause delays — with a clear mathematical explanation and no machine learning black box.

**Key properties:**
- **Deterministic** — identical input always produces identical output
- **Explainable** — every recommendation is arithmetically verifiable
- **No config files, no training data** — operates from a single raw log

---

## Features

| Feature | Description |
|---|---|
| 🔍 **Log Parsing** | Handles GitHub Actions (`##[section]`, `##[group]`) and Jenkins (`[Pipeline]`) formats; strips ANSI noise and redacts credentials |
| 🕸️ **DAG Construction** | Builds a weighted Directed Acyclic Graph using NetworkX with `O(V+E)` topological sort |
| 📊 **Critical Path Analysis** | Identifies the longest dependency chain (the makespan-determining path) using forward-pass edge relaxation |
| 💡 **Recommendations** | Classifies bottlenecks as **Compute-bound**, **I/O-bound**, or **General** with specific optimisation strategies |
| 📈 **Interactive Dashboard** | Streamlit web UI with Gantt timeline, DAG visualisation, and What-If simulator |
| 🖥️ **CLI Mode** | Headless `argparse`-based interface for scripting and automation |
| ✅ **Test Suite** | 20 `pytest` tests covering unit, integration, and edge-case scenarios |

---

## Architecture

The system follows a strict **Input-Process-Output (IPO)** architecture with four independent modules coordinated by a central Orchestrator:

```
Raw Log File  ──►  data_parser.py   ──►  analyser.py   ──►  suggestion_engine.py
                   (Parse & Sanitise)    (Build DAG +        (Classify &
                                          Critical Path)      Recommend)
                                               │
                                        orchestrator.py
                                        (AnalysisResult)
                                         /          \
                                   app.py         dashboard.py
                                   (CLI)           (Streamlit)
```

| Module | Role | Responsibility |
|---|---|---|
| `data_parser.py` | Input | Ingests logs; strips ANSI sequences; redacts credentials; extracts job names, timestamps, durations; applies temporal inference for Jenkins |
| `analyser.py` | Process | Constructs NetworkX DiGraph; executes topological sort with forward-pass edge relaxation at `O(V+E)` |
| `suggestion_engine.py` | Process | Evaluates critical-path jobs against impact threshold; classifies bottlenecks; returns structured `Recommendation` dataclass objects |
| `visualiser.py` | Output | Renders annotated DAG as PNG (CLI) or interactive Plotly graph (dashboard); generates Gantt timeline |
| `orchestrator.py` | Coordinator | Coordinates all four modules; packages outputs into a single `AnalysisResult` dataclass |
| `app.py` | Interface | CLI via `argparse`; no analytical logic |
| `dashboard.py` | Interface | Streamlit web dashboard; no analytical logic |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/alexkhat/DevOpsPipelineOptimiser.git
cd DevOpsPipelineOptimiser
pip install -r requirements.txt
```

### 2. Run the web dashboard

```bash
streamlit run dashboard.py
```

Then open [http://localhost:8501](http://localhost:8501) and upload a pipeline log file from the sidebar.

### 3. Run the CLI

```bash
python app.py -f sample_github_actions.txt
```

With a custom bottleneck sensitivity threshold:

```bash
python app.py -f sample_jenkins.txt -t 0.15
```

---

## Supported Log Formats

| Platform | Format | Example Marker |
|---|---|---|
| GitHub Actions (section) | `##[section]Starting: <job>` | `2026-01-01T10:00:00Z ##[section]Starting: Build` |
| GitHub Actions (group) | `##[group]<job>` / `##[endgroup]` | `##[group]Install dependencies` |
| Jenkins | `[Pipeline] { (<stage>)` | `[Pipeline] { (Run Tests)` |

Two sample log files are included:

- `sample_github_actions.txt` — GitHub Actions log from the `facebook/react` repository
- `sample_jenkins.txt` — Apache Kafka Jenkins pipeline log

---

## CLI Reference

```
usage: app.py [-h] -f FILE [-t THRESHOLD]

DevOps Pipeline Optimiser — CLI Mode

options:
  -h, --help            Show this help message and exit
  -f FILE, --file FILE  Path to the pipeline log file (.txt or .log)
  -t THRESHOLD          Bottleneck sensitivity threshold (default: 0.20 = 20%)
```

**Example output:**

```
============================================================
 DevOps Pipeline Optimiser (CLI)
============================================================

[*] Analysing: sample_github_actions.txt
[+] Stages extracted: 8
[+] Makespan: 312.00s
[+] Critical path: Setup -> Install -> SAST Scan -> Deploy

[*] Recommendations (threshold: 20%):
============================================================
  1. [COMPUTE] 'SAST Scan' consumes 38.5% of total time (120.0s).
     Consider parallel sharding, matrix execution, or splitting into
     smaller independent test suites.
  2. [I/O] 'Install Dependencies' consumes 22.1% of total time (69.0s).
     Consider dependency caching, artifact proxying, or pre-built
     base images to reduce download time.
============================================================
```

---

## Running the Tests

```bash
pytest test_suite.py -v
```

All 20 tests should pass. The test suite includes a **hand-verifiable critical path proof**:

```
Structure:
    Setup (4s) ──► Install (45s) ──► Unit Tests (30s)  ──► Deploy (10s)
                                  └► SAST Scan (120s)  ──►

Critical path: Setup → Install → SAST Scan → Deploy
Expected makespan: 4 + 45 + 120 + 10 = 179s  ✓
Unit Tests (30s) runs in parallel and does NOT affect makespan.
```

---

## Design Decisions

**No machine learning.** The overwhelming majority of AI-based CI/CD tools use probabilistic models that require historical training data and cannot explain their decisions. This tool uses graph theory and arithmetic — every output is independently verifiable.

**No configuration files.** The tool infers pipeline topology directly from log timestamps and stage markers. Zero setup required.

**Determinism guaranteed.** Because the Streamlit dashboard and CLI share the same `orchestrator.py` analytical core, both interfaces always produce identical results for the same input.

**O(V+E) complexity.** Critical path analysis uses topological sort with forward-pass edge relaxation (Agarwal, 2025), replacing brute-force `O(2^V)` path enumeration.

---

## Known Limitations

1. **1-second timestamp resolution** — Sub-second stages may report 0s duration. This affects pipelines with very fast stages (< 1s).
2. **Sequential dependency inference** — The parser infers dependencies from job appearance order. Highly concurrent pipelines with explicit parallelism may be modelled as sequential chains. The analyser *can* handle parallel DAGs when dependency data is correctly provided.

Both limitations are addressed in the planned Phase 2 roadmap (direct YAML configuration parsing + CI/CD API integration).

---

## Tech Stack

| Library | Version | Purpose |
|---|---|---|
| Python | 3.8+ | Core language |
| NetworkX | ≥ 3.0 | DAG construction and topological analysis |
| Streamlit | ≥ 1.32 | Interactive web dashboard |
| Plotly | ≥ 5.18 | Gantt timeline and DAG visualisation |
| pandas | ≥ 2.0 | Gantt data transformation |
| matplotlib | ≥ 3.7 | Static PNG graph export (CLI) |
| pytest | ≥ 7.4 | Automated test suite |

---

---

## Academic Context

This tool was developed as a BEng (Hons) Software Engineering Honours Project at **Edinburgh Napier University** (2026), supervised by Dr Amjad Ullah.

**Research gap addressed:** 83.69% of AI–CI/CD research stays at proposal stage and only 1.08% reaches practitioners (Farihane et al., 2025). Existing ML models are black-box, require historical training data, and cannot explain decisions in operationally verifiable terms. This tool fills the gap with a deterministic, graph-theoretic approach.

**Empirical evaluation:** Tested against five real-world CI/CD log files from GitHub Actions and Jenkins (including `facebook/react` and Apache Kafka), covering 65 pipeline stages with makespans from 3 to 1,360 seconds. All five runs completed within the 5-second performance threshold (maximum observed: 406ms).

---

## License

MIT License — see [LICENSE](LICENSE) for details.
