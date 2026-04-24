# ⚡ DevOps Pipeline Optimiser

> **A Graph-Theoretic Critical Path Analysis & Recommendation Engine for CI/CD Pipelines.**
> *Final Year Honours Project — Edinburgh Napier University*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)
![NetworkX](https://img.shields.io/badge/NetworkX-DAG%20Math-green)
![Testing](https://img.shields.io/badge/pytest-20%2F20%20passing-success)

---

## 📖 Overview

Modern CI/CD pipelines run multiple concurrent tasks. Identifying the true bottleneck requires more than reading logs sequentially. This tool ingests unstructured CI/CD logs from GitHub Actions and Jenkins, models them as a **Directed Acyclic Graph (DAG)**, and executes O(V+E) topological sorting to mathematically identify which sequence of tasks is delaying deployment.

It then applies rule-based heuristics to recommend architectural optimisations such as parallel sharding or dependency caching — with no machine learning involved. Every recommendation is directly traceable to a job name, duration, and percentage of makespan, verifiable with simple arithmetic.

**Supported platforms:** GitHub Actions · Jenkins Declarative Pipeline

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│       Unstructured CI/CD Pipeline Logs (.txt, .log)         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
           ┌──────────────────────────┐
           │    Log Sanitisation &    │
           │      Parsing Engine      │
           │     (data_parser.py)     │
           └──────────┬───────────────┘
                      │
                      ▼
           ┌──────────────────────────┐
           │   Mathematical Engine    │
           │      (analyser.py)       │
           │ • NetworkX DAG Builder   │
           │ • O(V+E) Topological Sort│
           └──────────┬───────────────┘
                      │
                      ▼
           ┌──────────────────────────┐
           │  Rule-Based Heuristics   │
           │  (suggestion_engine.py)  │
           └──────────┬───────────────┘
                      │
           ┌──────────┴───────────────┐
           ▼                          ▼
  ┌──────────────────┐       ┌──────────────────┐
  │  Web Dashboard   │       │   Headless CLI   │
  │  (dashboard.py)  │       │     (app.py)     │
  └──────────────────┘       └──────────────────┘
```

| Module | Responsibility |
|---|---|
| `data_parser.py` | Parses raw logs into structured job data |
| `analyser.py` | Builds the DAG and computes the critical path |
| `suggestion_engine.py` | Generates rule-based recommendations |
| `visualiser.py` | Produces the DAG PNG image |
| `orchestrator.py` | Single entry point coordinating all four components |
| `dashboard.py` | Streamlit web dashboard (primary interface) |
| `app.py` | CLI interface for headless use |
| `test_suite.py` | Full pytest test suite — 20 tests |

---

## ✨ Features

- Parses GitHub Actions (`##[section]`, `##[group]`) and Jenkins (`[Pipeline]`) log formats
- Builds a weighted DAG from extracted job data
- Computes the critical path using topological sort + forward-pass edge relaxation — O(V+E)
- Classifies bottlenecks as **compute-bound** or **I/O-bound** via keyword matching
- Interactive **What-If Simulator** — test hypothetical optimisations before changing infrastructure
- Gantt timeline chart of all pipeline stages
- DAG visualisation with critical path highlighted in red
- Full CLI mode for headless / scripted use
- 20/20 automated tests passing via pytest

---

## 🚀 Getting Started

### Installation

```bash
git clone https://github.com/alexkhat/DevOpsPipelineOptimiser.git
cd DevOpsPipelineOptimiser
pip install -r requirements.txt
```

### Run the Dashboard

```bash
streamlit run dashboard.py
```

Open your browser at `http://localhost:8501`, upload a `.txt` or `.log` pipeline log file and the tool will analyse it automatically.

### Run the CLI

```bash
python app.py -f path/to/logfile.txt
python app.py -f path/to/logfile.txt -t 0.15
```

| Flag | Description | Default |
|---|---|---|
| `-f` | Path to the log file | required |
| `-t` | Bottleneck threshold (fraction of makespan) | `0.20` |

### Run the Tests

```bash
pytest test_suite.py -v
```

All 20 tests pass in under 5 seconds.

---

## ⚙️ How It Works

### 1. Parsing
The parser reads the log line by line, stripping ANSI colour codes and redacting any credentials. It detects stage boundaries using regex patterns for three log formats and infers durations from timestamps. For Jenkins logs a **floating timestamp** approach is used — the parser assigns a stage's start time from the first timestamp encountered after the stage declaration.

### 2. DAG Construction
Each pipeline stage becomes a node weighted by its duration. Each dependency relationship becomes a directed edge. NetworkX's `DiGraph` provides built-in cycle detection and topological ordering.

### 3. Critical Path Analysis
The critical path is found using topological sort followed by forward-pass edge relaxation — the standard O(V+E) DAG longest-path algorithm. The result is the sequence of stages whose combined duration equals the **makespan** (minimum possible pipeline duration).

### 4. Recommendations
Only stages on the critical path are analysed. A stage is flagged if it exceeds 20% of makespan OR runs for more than 60 seconds in absolute terms. Stages are classified using keyword sets derived from real-world CI/CD log analysis.

---

## 🧪 Test Results

| Test | Description | Result |
|---|---|---|
| 1 | ANSI noise cleaning | ✅ Pass |
| 2–3 | Secret masking (case-insensitive) | ✅ Pass |
| 4 | Duration calculation | ✅ Pass |
| 5 | Midnight rollover correction | ✅ Pass |
| 6 | Temporal inference (no end marker) | ✅ Pass |
| 7–8 | Parser edge cases (invalid / empty file) | ✅ Pass |
| 9 | DAG construction (nodes and edges) | ✅ Pass |
| 10 | Critical path maths (179s ground truth) | ✅ Pass |
| 11–12 | Empty graph / cycle detection | ✅ Pass |
| 13 | Noise filter (micro-tasks excluded) | ✅ Pass |
| 14 | Compute-bound classification | ✅ Pass |
| 15 | I/O-bound classification | ✅ Pass |
| 16 | Structured Recommendation output | ✅ Pass |
| 17 | Zero-duration pipeline handling | ✅ Pass |
| 18–19 | Graph image generation / empty graph | ✅ Pass |
| 20 | End-to-end integration test | ✅ Pass |

**20/20 passing in ~3s**

---

## 📊 Evaluation

Evaluated against five real-world CI/CD logs across two platforms:

| Log | Platform | Stages | Makespan | Recommendations |
|---|---|---|---|---|
| facebook/react | GitHub Actions | 17 | 340s | 3 |
| Apache Kafka | GitHub Actions | 14 | 1,360s | 3 |
| React Fuzz | GitHub Actions | 6 | 3s | 1 |
| Jenkins DevSecOps | Jenkins | 14 | 256s | 3 |
| vercel/next.js | GitHub Actions | 14 | 411s | 5 |

All 15 recommendations were verified as objectively correct against the parsed data.

---

## ⚠️ Known Limitations

- **Timestamp resolution:** Stages completing within the same second receive a zero-second duration and are excluded. This is a source data constraint, not a parser defect.
- **Parallel execution inference:** The parser infers sequential dependencies from log order. Pipelines with parallel jobs are modelled as sequential chains, which overestimates makespan. A future phase would address this with YAML config parsing and the GitHub Actions API.

---

## 📦 Requirements

```
streamlit>=1.32.0
networkx>=3.2
matplotlib>=3.8
pandas>=2.1
plotly>=5.18
pytest>=8.0
```
