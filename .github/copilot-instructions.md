# Protocol Analysis Service - AI Coding Agent Guide

## Architecture Overview

This is a **two-component asynchronous protocol analysis service** for Opentrons laboratory automation protocols:

1. **FastAPI Server** (`api/main.py`) - Handles file uploads, serves results, manages REST API
2. **Processor Service** (`analyze/processor.py`) - Asynchronously processes analysis jobs using filesystem-based job queue

**Critical Design Pattern**: Jobs communicate via filesystem at `storage/jobs/{job_id}/`. The API writes files/metadata, sets status to `PENDING`, and the processor polls for pending jobs, analyzes them in isolated venvs, and writes results back.

### Multi-Version Analysis System

**Key Concept**: This service analyzes protocols against **multiple Opentrons robot server versions** (8.0.0 through `next`) by creating isolated Python virtual environments for each version.

- `analyze/env_config.py` - Maps robot versions to pip install specs (including a `next` alias that follows the latest published alpha build)
- `analyze/venv_manager.py` - Creates/manages venvs in `.venvs/opentrons-{version}/` using the uv-managed Python interpreter to keep versions consistent
- `api/version_mapping.py` - Maps Protocol API versions (2.20-2.27) to robot stack versions

**Pattern**: Each analysis job specifies a `robot_version`, which determines which venv to use. The processor creates venvs on-demand and runs `opentrons.cli.analyze` within the correct environment.

## Development Workflow

### Essential Commands (via `uv` package manager)

```bash
make setup              # Install dependencies with uv
make test               # Run unit + integration tests (fast, no services)
make test-e2e           # Run e2e tests (auto-starts/stops services)
make test-all           # Run lint + all tests
make lint               # Check code with ruff (no fixes)
make format             # Auto-format with ruff
make clean-storage      # Delete all job files
make clean-venvs        # Delete all opentrons venvs
make clean-e2e-artifacts # Remove PID/log files written by make test-e2e
```

### Running Services Locally

**Two-service architecture requires both running simultaneously:**

```bash
# Terminal 1: API server
make run-api            # FastAPI dev server on :8000

# Terminal 2: Processor daemon
make run-processor      # Continuous polling mode
# OR
make run-processor-once # Process pending jobs and exit
```

**Shortcut** (both services in one terminal):
```bash
make run              # Starts both with Ctrl+C to stop
```

### Testing Strategy

- **Unit tests** (`tests/unit/`) - Test individual components in isolation (file storage, status management)
- **Integration tests** (`tests/integration/`) - Test API endpoints with TestClient (no real services)
- **E2E tests** (`tests/e2e/`) - Test full workflow with both services running (auto-managed by `make test-e2e`)

**Critical Pattern**: E2E tests in `Makefile` start services, wait 3s, run tests, then kill processes by name. Always use `make test-e2e` instead of running pytest directly.

## Code Conventions

### File Upload & Storage Patterns

**Pattern** (`api/file_storage.py`): 
- Protocol files: Save to `storage/jobs/{job_id}/{filename}.py`
- Labware files: Save to `storage/jobs/{job_id}/labware/{filename}.json`
- CSV files: Save to `storage/jobs/{job_id}/{filename}.csv` or `.txt`

**Convention**: Use `FileStorage.save_file()` with `subdirectory` parameter for labware files only.

### Job Status State Machine

Jobs follow strict state transitions (`analyze/job_status.py`):

```
PENDING → PROCESSING → COMPLETED (with completed_analysis.json)
                    ↘ FAILED (with error message)
```

**Critical Files per Job**:
- `metadata.json` - Created at upload, contains `robot_version`, `created_at`
- `status.json` - Updated by processor, contains `status`, `updated_at`, optional `error`
- `completed_analysis.json` - Written on success, contains full analysis result

### Analysis Execution Pattern

**Key Implementation** (`analyze/processor.py._run_analysis()`):

Uses subprocess to run Python code in the target venv that:
1. Imports `opentrons.cli.analyze._analyze` and `_Output`
2. Runs analysis with JSON output to BytesIO stream
3. Returns JSON via stdout (processor parses it)

**Why**: Cannot directly import opentrons library (version conflicts). Must use subprocess with correct venv's Python executable.

### API Validation Patterns

**Consistent validation in `api/main.py`**:
- Robot version: Must be in `VALID_ROBOT_VERSIONS` set (from `version_mapping.py`)
- Protocol file: Must end with `.py`
- Labware files: Must end with `.json`
- CSV files: Must end with `.csv` or `.txt`
- RTP parameter: Validate JSON parsing before storage

**Error Response Pattern**: Raise `HTTPException(status_code=400, detail=<specific message>)` for validation errors.

## Client Usage Pattern

**Example** (`run_client.py`, `client/analyze_client.py`):

```python
with AnalysisClient() as client:
    job_id = client.submit_protocol(protocol_file, robot_version="8.7.0")
    status = client.wait_for_completion(job_id, poll_interval=0.5)
    result = client.get_job_result(job_id)
```

**Pattern**: Client polls `/jobs/{job_id}/status` until status is `completed` or `failed`, then fetches result from `/jobs/{job_id}/result`.

## Important Quirks & Gotchas

1. **`next` alpha installs from PyPI**: Uses the latest published `opentrons` alpha (currently 8.8.0a8). First-time installs can still take ~1 minute while pip resolves dependencies, so prefer reusing venvs when possible.

2. **Test file exclusions**: `ruff` config excludes `test-files/` directory (contains actual protocol files that may not follow linting rules).

3. **E2E test cleanup**: `make test-e2e` runs `make clean-storage` first to ensure clean state. Always use make target, not pytest directly.

4. **JSON extraction fallback**: `processor._extract_first_json_object()` handles cases where opentrons CLI output includes stderr/warnings before JSON (uses regex to find first `{...}` object).

5. **Async file operations**: Even though file I/O is synchronous, upload handlers use `async/await` for FastAPI compatibility and to reset file pointers with `await file.seek(0)`.

## Adding Support for New Robot Versions

1. Add to `PROTOCOL_API_TO_ROBOT_STACK` in `api/version_mapping.py`
2. Add to `ENVIRONMENT_CONFIGS` in `analyze/env_config.py` with install spec
3. Update `README.md` documentation
4. Test with `make test-all` (especially e2e tests)

## Debugging Tips

- Check `e2e-api.log` and `e2e-processor.log` after e2e test failures (created by `make test-e2e`)
- Inspect `storage/jobs/{job_id}/` to see uploaded files and status transitions
- Run `make run-processor-once` to process a single job and see output without daemon loop
- Use `make clean-venvs` if venvs become corrupted (they'll be recreated on next analysis)
