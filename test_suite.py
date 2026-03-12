import pytest
import networkx as nx
from datetime import datetime
import os

import data_parser
import analyser
import suggestion_engine
import visualiser
import orchestrator

# ==============================================================================
# MODULE: test_suite.py
# PURPOSE: Validates the correctness of all backend modules.
#
# RUN: pytest test_suite.py -v
#
# TEST STRATEGY:
#   - Parser tests: Verify ANSI cleaning, secret masking, temporal inference.
#   - Analyser tests: Verify DAG construction, critical path math, cycle detection.
#   - Suggestion engine tests: Verify noise filtering, keyword classification,
#     structured Recommendation output.
#   - Visualiser tests: Verify graph image generation (smoke test).
#   - Integration test: Verify the full pipeline via orchestrator.
# ==============================================================================


# ---------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------

@pytest.fixture
def mock_parsed_data():
    """
    A controlled pipeline with PARALLEL jobs to test critical path logic.

    Structure:
        Setup (4s) -> Install (45s) -> Unit Tests (30s)  -> Deploy (10s)
                                    -> SAST Scan (120s)  ->

    The critical path should be: Setup -> Install -> SAST -> Deploy = 179s
    Unit Tests (30s) runs parallel to SAST (120s) and should NOT be on the path.
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
    """Creates a minimal GitHub Actions log file for integration testing."""
    log_content = """
2026-02-24T10:00:00Z ##[section]Starting: Initial Setup
2026-02-24T10:00:10Z ##[section]Starting: Build Application
2026-02-24T10:00:40Z ##[section]Starting: Run Tests
2026-02-24T10:01:10Z ##[section]Finishing: Run Tests
    """
    test_file = tmp_path / "integration_test.txt"
    test_file.write_text(log_content)
    return str(test_file)


# ---------------------------------------------------------
# 1. PARSER TESTS
# ---------------------------------------------------------

def test_clean_ansi_noise():
    """Verifies ANSI escape sequences are stripped correctly."""
    noisy = "\x1b[32m[SUCCESS]\x1b[0m Job Completed"
    clean = data_parser.clean_ansi_noise(noisy)
    assert clean == "[SUCCESS] Job Completed"


def test_mask_secrets():
    """Verifies sensitive tokens are redacted."""
    line = "Connecting with AWS_SECRET_KEY=12345ABCDE"
    safe = data_parser.mask_secrets(line)
    assert "12345ABCDE" not in safe
    assert "*****" in safe


def test_mask_secrets_case_insensitive():
    """Verifies secret masking works regardless of case."""
    line = "Using token=mySecretValue123"
    safe = data_parser.mask_secrets(line)
    assert "mySecretValue123" not in safe


def test_calculate_duration_normal():
    """Verifies basic duration calculation."""
    start = datetime(2026, 1, 1, 10, 0, 0)
    end = datetime(2026, 1, 1, 10, 0, 30)
    assert data_parser.calculate_duration(start, end) == 30.0


def test_calculate_duration_midnight_rollover():
    """Verifies midnight rollover correction."""
    start = datetime(2026, 1, 1, 23, 59, 50)
    end = datetime(2026, 1, 1, 0, 0, 10)
    duration = data_parser.calculate_duration(start, end)
    assert duration == 20.0  # 10s before midnight + 10s after


def test_parser_temporal_inference(tmp_path):
    """Verifies the parser infers duration when end tags are missing."""
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
    """Verifies parser returns None for nonexistent files."""
    result = data_parser.parse_log_file("nonexistent_file.txt")
    assert result is None


def test_parser_returns_none_for_empty_log(tmp_path):
    """Verifies parser returns None when no valid stages are found."""
    test_file = tmp_path / "empty.txt"
    test_file.write_text("This file has no pipeline data at all.\n")

    result = data_parser.parse_log_file(str(test_file))
    assert result is None


# ---------------------------------------------------------
# 2. ANALYSER TESTS
# ---------------------------------------------------------

def test_build_dag(mock_parsed_data):
    """Verifies the DAG has the correct number of nodes and edges."""
    G = analyser.build_dag(mock_parsed_data)

    assert G.number_of_nodes() == 5
    assert G.number_of_edges() == 5
    assert G.has_edge("Install Dependencies", "Run Checkmarx SAST")
    assert G.has_edge("Install Dependencies", "Run Unit Tests")


def test_critical_path_calculation(mock_parsed_data):
    """
    Verifies the critical path math.

    Expected: Setup(4) + Install(45) + SAST(120) + Deploy(10) = 179s
    Unit Tests (30s) is parallel to SAST and must NOT appear on the path.
    """
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)

    assert duration == 179.0, f"Expected 179.0, got {duration}"
    assert "Run Checkmarx SAST" in path
    assert "Run Unit Tests" not in path


def test_critical_path_empty_graph():
    """Verifies graceful handling of an empty graph."""
    G = nx.DiGraph()
    path, duration = analyser.calculate_critical_path(G)
    assert path == []
    assert duration == 0.0


def test_cyclic_graph_detection():
    """Verifies cycle detection returns empty results."""
    G = nx.DiGraph()
    G.add_edge("Job A", "Job B")
    G.add_edge("Job B", "Job C")
    G.add_edge("Job C", "Job A")  # Creates a cycle

    path, duration = analyser.calculate_critical_path(G)
    assert path == []
    assert duration == 0.0


# ---------------------------------------------------------
# 3. SUGGESTION ENGINE TESTS
# ---------------------------------------------------------

def test_noise_filter(mock_parsed_data):
    """Verifies micro-tasks (like Setup at 4s) are filtered out."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)

    recs = suggestion_engine.generate_suggestions(
        path, mock_parsed_data, duration, threshold=0.10
    )

    # Setup Environment (4s out of 179s = 2.2%) should not appear
    job_names = [r.job_name for r in recs]
    assert "Setup Environment" not in job_names


def test_compute_classification(mock_parsed_data):
    """Verifies compute-bound jobs are classified correctly."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)

    recs = suggestion_engine.generate_suggestions(
        path, mock_parsed_data, duration, threshold=0.20
    )

    # SAST scan should be classified as compute
    sast_recs = [r for r in recs if r.job_name == "Run Checkmarx SAST"]
    assert len(sast_recs) == 1
    assert sast_recs[0].category == 'compute'


def test_io_classification(mock_parsed_data):
    """Verifies I/O-bound jobs are classified correctly."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)

    recs = suggestion_engine.generate_suggestions(
        path, mock_parsed_data, duration, threshold=0.10
    )

    # Install Dependencies should be classified as I/O
    install_recs = [r for r in recs if r.job_name == "Install Dependencies"]
    assert len(install_recs) == 1
    assert install_recs[0].category == 'io'


def test_recommendations_are_structured(mock_parsed_data):
    """Verifies recommendations use the Recommendation dataclass."""
    G = analyser.build_dag(mock_parsed_data)
    path, duration = analyser.calculate_critical_path(G)

    recs = suggestion_engine.generate_suggestions(
        path, mock_parsed_data, duration, threshold=0.20
    )

    for rec in recs:
        assert hasattr(rec, 'category')
        assert hasattr(rec, 'job_name')
        assert hasattr(rec, 'impact_pct')
        assert hasattr(rec, 'duration')
        assert hasattr(rec, 'message')


def test_zero_duration_pipeline():
    """Verifies graceful handling of zero-duration pipelines."""
    recs = suggestion_engine.generate_suggestions([], {}, 0.0)
    assert len(recs) == 1
    assert recs[0].category == 'info'


# ---------------------------------------------------------
# 4. VISUALISER TESTS
# ---------------------------------------------------------

def test_graph_image_generation(mock_parsed_data, tmp_path):
    """Verifies the visualiser produces a PNG file."""
    G = analyser.build_dag(mock_parsed_data)
    path, _ = analyser.calculate_critical_path(G)

    output = str(tmp_path / "test_graph.png")
    result = visualiser.save_pipeline_graph(G, path, output)

    assert result is True
    assert os.path.exists(output)


def test_empty_graph_visualisation():
    """Verifies the visualiser handles empty graphs gracefully."""
    G = nx.DiGraph()
    result = visualiser.save_pipeline_graph(G, [])
    assert result is False


# ---------------------------------------------------------
# 5. INTEGRATION TEST (via Orchestrator)
# ---------------------------------------------------------

def test_full_pipeline_integration(sample_log_file):
    """
    End-to-end test: log file -> parse -> analyse -> recommend.
    Verifies the orchestrator produces valid results from a real log format.
    """
    result = orchestrator.run_analysis(sample_log_file, threshold=0.20)

    assert result is not None
    assert result.makespan > 0
    assert len(result.critical_path) > 0
    assert len(result.recommendations) > 0
    assert result.graph.number_of_nodes() > 0
