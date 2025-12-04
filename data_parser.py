import pandas as pd
import json
from typing import Dict, List, Any


def parse_ci_log(log_path: str) -> pd.DataFrame:
    """
    PURPOSE: Ingests raw CI/CD log data (in simulated JSON format) and transforms
    it into a standardized pandas DataFrame structure.

    This function acts as the necessary input bridge, ensuring the analytical
    engine receives only clean, structured data, adhering to the Single
    Responsibility Principle.
    """
    print(f"--- Parsing log from: {log_path} ---")

    try:
        # Step 1: Attempt to load the raw file. We assume JSON format for the MVP.
        with open(log_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        # Robust error handling for a missing file (essential for production-grade code).
        print("Error: Log file not found. Check the file path.")
        return pd.DataFrame()
    except json.JSONDecodeError:
        # Error handling for improperly formatted JSON.
        print("Error: Log file is not valid JSON. Check for syntax errors.")
        return pd.DataFrame()

    # Check if the expected key exists (a guard for empty or malformed files)
    if 'workflow_steps' not in data:
        print("Error: Log data structure missing 'workflow_steps' key.")
        return pd.DataFrame()

    # Step 2: Convert the list of workflow steps into a DataFrame.
    # pandas is used here for fast, structured data manipulation.
    df = pd.DataFrame(data['workflow_steps'])

    # Step 3: Data Cleaning/Conversion.
    # Ensure the critical 'duration' column is explicitly an integer, which is
    # necessary for accurate mathematical calculations in the Analyzer.
    try:
        df['duration_seconds'] = df['duration_seconds'].astype(int)
    except ValueError:
        print("Error: 'duration_seconds' column contains non-numeric data.")
        return pd.DataFrame()

    # Step 4: Select the essential data fields required for DAG construction.
    # The Analyzer only needs these three facts to build the Critical Path Model.
    required_cols = ['task_name', 'duration_seconds', 'dependencies']
    return df[required_cols]