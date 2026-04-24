import pytest
import networkx as nx
from datetime import datetime
import os

import data_parser
import analyser
import suggestion_engine
import visualiser
import orchestrator

# test_suite.py
# Full test suite for all backend modules.
# Run with: pytest test_suite.py -v
#
# Coverage:
#   Parser           — ANSI cleaning, secret masking, timestamp inference, edge cases
#   Analyser         — DAG construction, critical path maths, cycle detection
#   Suggestion engine — noise filtering, keyword classification, structured output
#   Visualiser       — graph image generation (smoke test)
#   Integration      — full pipeline via orchestrator on a real log format


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_parsed_data():
    """
    A hand-crafted pipeline with two parallel branches after Install.

    Structure:
        Setup (4s) → Install (45s) → Run Unit Tests (30s)      → Deploy (10s)
                                   → Run Checkmarx SAST (120s) →

    Expected critical path: Setup → Install → SAST → Deploy = 179s
    Unit Tests (30s) runs in parallel with SAST and must NOT appear on the path.
    """
    return {
        "Setup Environment": {
            "start": datetime(2026, 1, 1, 12, 0, 0),
            "duration": 4.0,
            "dependencies": []
        },
        "Install Dependencies": {
            "start": datetime(2026, 1, 1, 12, 0, 4),
            "duration": 45.0,
            "dependencies": ["Setup Environment"]
        },
        "Run Unit Tests": {
            "start": datetime(2026, 1, 1, 12, 0, 49),
            "duration": 30.0,
            "dependencies": ["Install Dependencies"]
        },
        "Run Checkmarx SAST": {
            "start": datetime(2026, 1, 1, 12, 0, 49),
            "duration": 120.0,
            "dependencies": ["Install Dependencies"]
        },
        "Deploy to Production": {
            "start": datetime(2026, 1, 1, 12, 2, 49),
            "duration": 10.0,
            "dependencies": ["Run Unit Tests", "Run Checkmarx SAST"]
        }
    }


@pytest.fixture
def sample_log_file(tmp_path):
    """Minimal GitHub Actions section-format log for the integration test."""
    log_content = """
2026-02-24T10:00:00Z ##[section]Starting: Initial Setup
2026-02-24T10:00:10Z ##[section]Starting: Build Application
2026-02-24T10:00:40Z ##[section]Starting: Run Tests
2026-02-24T10:01:10Z ##[section]Finishing: Run Tests
    """
    test_file = tmp_path / "integration_test.txt"
    test_file.write_text(log_content)
    return str(test_file)


# ── 1. Parser tests ───────────────────────────────────────────────────────────

def test_clean_ansi_noise():
    """ANSI colour codes should be stripped, leaving plain text."""
    noisy = "\x1b[32m[SUCCESS]\x1b[0m Job Completed"
    assert data_parser.clean_ansi_noise(noisy) == "[SUCCESS] Job Completed"


def test_mask_secrets():
    """Credential values should be replaced with asterisks."""
    line = "Connecting with AWS_SECRET_KEY=12345ABCDE"
    safe = data_parser.mask_secrets(line)
    assert "12345ABCDE" not in safe
    assert "*****" in safe


def test_mask_secrets_case_insensitive():
    """Secret masking must work regardless of keyword capitalisation."""
    line = "Using token=mySecretValue123"
    safe = data_parser.mask_secrets(line)
    assert "mySecretValue123" not in safe


def test_calculate_duration_normal():
    """Standard duration between two timestamps should return correct seconds."""
    start = datetime(2026, 1, 1, 10, 0, 0)
    end   = datetime(2026, 1, 1, 10, 0, 30)
    assert data_parser.calculate_duration(start, end) == 30.0


def test_calculate_duration_midnight_rollover():
    """Negative delta means the pipeline crossed midnight — 86,400s correction applied."""
    start    = datetime(2026, 1, 1, 23, 59, 50)
    end      = datetime(2026, 1, 1, 0, 0, 10)
    assert data_parser.calculate_duration(start, end) == 20.0


def test_parser_temporal_inference(tmp_path):
    """Without an explicit end marker, the next timestamp closes the previous stage."""
    log_content = """
    2026-02-24T10:00:00Z ##[section]Starting: Initial Job
    2026-02-24T10:00:10Z ##[section]Starting: Second Job
    """
    test_file = tmp_path / "inference_test.txt"
    test_file.write_text(log_content)
    data = data_parser.parse_log_file(str(test_file))
    assert data is not None
    assert "Initial Job" in data
    assert data["Initial Job"]["duration"] == 10.0


def test_parser_returns_none_for_invalid_file():
    """Parser should return None gracefully for a non-existent file."""
    assert data_parser.parse_log_file("nonexistent_file.txt") is None


def test_parser_returns_none_for_empty_log(tmp_path):
    """Parser should return None when the file contains no recognisable stages."""
    test_file = tmp_path / "empty.txt"
    test_file.write_text("This file has no pipeline data at all.\n")
    assert data_parser.parse_log_file(str(test_file)) is None


# ── 2. Analyser tests ─────────────────────────────────────────────────────────

def test_build_dag(mock_parsed_data):
    """DAG should have exactly 5 nodes and 5 edges matching the fixture structure."""
    G = analyser.build_dag(mock_parsed_data)
    assert G.number_of_nodes() == 5
    assert G.number_of_edges() == 5
    assert G.has_edge("Install Dependencies", "Run Checkmarx SAST")
    assert G.has_edge("Install Dependencies", "Run Unit Tests")


def test_critical_path_calculation(mock_parsed_data):
    """Setup(4) + Install(45) + SAST(120) + Deploy(10) = 179s. Unit Tests must not appear."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)
    assert duration == 179.0, f"Expected 179.0, got {duration}"
    assert "Run Checkmarx SAST" in path
    assert "Run Unit Tests" not in path


def test_critical_path_empty_graph():
    """An empty graph should return an empty path and zero duration."""
    G = nx.DiGraph()
    path, duration = analyser.calculate_critical_path(G)
    assert path == [] and duration == 0.0


def test_cyclic_graph_detection():
    """A graph containing a cycle should return empty results."""
    G = nx.DiGraph()
    G.add_edge("Job A", "Job B")
    G.add_edge("Job B", "Job C")
    G.add_edge("Job C", "Job A")  # cycle
    path, duration = analyser.calculate_critical_path(G)
    assert path == [] and duration == 0.0


# ── 3. Suggestion engine tests ────────────────────────────────────────────────

def test_noise_filter(mock_parsed_data):
    """Setup Environment (4s = 2.2% of 179s) is below the noise floor — should be excluded."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)
    recs = suggestion_engine.generate_suggestions(path, mock_parsed_data, duration, threshold=0.10)
    assert "Setup Environment" not in [r.job_name for r in recs]


def test_compute_classification(mock_parsed_data):
    """'Run Checkmarx SAST' contains 'scan' — should be classified as compute-bound."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)
    recs = suggestion_engine.generate_suggestions(path, mock_parsed_data, duration, threshold=0.20)
    sast = [r for r in recs if r.job_name == "Run Checkmarx SAST"]
    assert len(sast) == 1 and sast[0].category == 'compute'


def test_io_classification(mock_parsed_data):
    """'Install Dependencies' contains 'install' — should be classified as I/O-bound."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)
    recs = suggestion_engine.generate_suggestions(path, mock_parsed_data, duration, threshold=0.10)
    install = [r for r in recs if r.job_name == "Install Dependencies"]
    assert len(install) == 1 and install[0].category == 'io'


def test_recommendations_are_structured(mock_parsed_data):
    """Every recommendation must be a Recommendation dataclass with all five fields."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)
    recs = suggestion_engine.generate_suggestions(path, mock_parsed_data, duration, threshold=0.20)
    for rec in recs:
        assert hasattr(rec, 'category')
        assert hasattr(rec, 'job_name')
        assert hasattr(rec, 'impact_pct')
        assert hasattr(rec, 'duration')
        assert hasattr(rec, 'message')


def test_zero_duration_pipeline():
    """A zero-duration pipeline should return a single informational recommendation."""
    recs = suggestion_engine.generate_suggestions([], {}, 0.0)
    assert len(recs) == 1 and recs[0].category == 'info'


# ── 4. Visualiser tests ───────────────────────────────────────────────────────

def test_graph_image_generation(mock_parsed_data, tmp_path):
    """Visualiser should produce a PNG file at the specified output path."""
    G = analyser.build_dag(mock_parsed_data)
    path, _ = analyser.calculate_critical_path(G)
    output = str(tmp_path / "test_graph.png")
    assert visualiser.save_pipeline_graph(G, path, output) is True
    assert os.path.exists(output)


def test_empty_graph_visualisation():
    """An empty graph should return False without raising an exception."""
    assert visualiser.save_pipeline_graph(nx.DiGraph(), []) is False


# ── 5. Integration test ───────────────────────────────────────────────────────

def test_full_pipeline_integration(sample_log_file):
    """
    End-to-end: log file → parse → DAG → CPA → recommendations.
    Verifies the orchestrator produces a valid AnalysisResult from a real
    GitHub Actions log format without any intermediate mocking.
    """
    result = orchestrator.run_analysis(sample_log_file, threshold=0.20)
    assert result is not None
    assert result.makespan > 0
    assert len(result.critical_path) > 0
    assert len(result.recommendations) > 0
    assert result.graph.number_of_nodes() > 0
