# ⚡ DevOps Pipeline Optimiser

> **A Graph-Theoretic Critical Path Analysis & Recommendation Engine for CI/CD Pipelines.**
> *Design Science Research Artefact - Final Year Honours Project*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)
![NetworkX](https://img.shields.io/badge/NetworkX-DAG%20Math-green)
![Testing](https://img.shields.io/badge/pytest-passing-success)

## 📖 Overview
Modern CI/CD pipelines run multiple concurrent tasks. Identifying the true bottleneck requires more than reading logs sequentially. This tool ingests unstructured CI/CD logs (GitHub Actions, Jenkins), models them as a **Directed Acyclic Graph (DAG)**, and executes $O(V+E)$ topological sorting to mathematically prove which sequence of tasks is delaying deployment.

It then applies DevSecOps heuristics to recommend architectural optimisations (e.g., Parallel Sharding, Dependency Caching).

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
           │ Expert System Heuristics │
           │  (suggestion_engine.py)  │
           └──────────┬───────────────┘
                      │
           ┌──────────┴───────────────┐
           ▼                          ▼
  ┌──────────────────┐       ┌──────────────────┐
  │  Web Dashboard   │       │   Headless CLI   │
  │  (dashboard.py)  │       │     (app.py)     │
  └──────────────────┘       └──────────────────┘
