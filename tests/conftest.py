import pytest
import os
from dotenv import load_dotenv
from pathlib import Path

def pytest_configure(config):
    """Load environment variables before running tests."""
    # Get the backend directory path
    backend_dir = Path(__file__).parent.parent
    
    # Load .env file from backend directory
    env_path = backend_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}") 