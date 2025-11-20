"""Configuration for the protocol analysis API."""

from pathlib import Path

# Base storage directory for analysis jobs
STORAGE_BASE_DIR = Path("storage/jobs")

# Ensure storage directory exists
STORAGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
