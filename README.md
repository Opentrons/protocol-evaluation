# protocol-analysis

FastAPI service for analyzing Opentrons protocols with asynchronous processing.

## Features

- **`/info` endpoint**: Returns application version and protocol API to robot stack version mappings
- **`/analyze` endpoint**: Accepts protocol files for analysis with optional custom labware, CSV data, and runtime parameters
- **`/jobs/{job_id}/status` endpoint**: Check the status of an analysis job
- **`/jobs/{job_id}/result` endpoint**: Retrieve completed analysis results
- **Asynchronous processing**: Protocol analysis runs in a separate processor service

## Architecture

This service uses a two-component architecture:

1. **FastAPI Server** (`api/main.py`): Handles file uploads and serves results
2. **Processor Service** (`analyze/processor.py`): Processes analysis jobs asynchronously in the background

Jobs are queued via the filesystem at `storage/jobs/{job_id}/` and the processor picks them up for analysis.

Each job specifies a target robot server version. Supported versions range from 8.0.0 through the special `next` alias, which always points at the latest published Opentrons alpha build (configured in `analyze/env_config.py`). The processor spins up isolated virtual environments (managed via uv) per version so analyses stay reproducible.

## Development

### Prerequisites

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) for dependency management

### Setup

```bash
# Install dependencies
make setup

# Run linter (check only, no fixes)
make lint

# Run tests (unit + integration)
make test

# Run end-to-end tests (starts services automatically)
make test-e2e

# Run all tests and linting
make test-all

# Format code
make format
```

## CI/CD

The project uses GitHub Actions for continuous integration:

- **Linting**: Runs `ruff` to check code quality
- **Unit & Integration Tests**: Fast tests without services
- **End-to-End Tests**: Full workflow tests with services running

All checks run automatically on pull requests and pushes to `main`.

### Running the Services

Start the FastAPI server:

```bash
make run-api
# Or manually:
uv run fastapi dev api/main.py
```

Start the processor service (in a separate terminal):

```bash
make run-processor
# Or manually:
uv run python run_processor.py
```

For one-shot processing (process pending jobs and exit):

```bash
make run-processor-once
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, you can access:

- Interactive API docs: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

### Testing

Run all tests:

```bash
make test
```

Run only unit tests:

```bash
make test-unit
```

Run only integration tests:

```bash
make test-integration
```

### Makefile Targets

- `make setup` - Install dependencies with uv (including dev tools)
- `make teardown` - Remove the project virtual environment
- `make lint` - Run ruff lint + format check (no fixes)
- `make format` - Run ruff check --fix and ruff format
- `make test` - Run unit + integration tests (excludes e2e)
- `make test-unit` / `make test-integration` - Run specific suites
- `make test-e2e` - Spin up both services, run E2E tests, capture logs
- `make test-all` - Run lint, fast tests, and e2e in sequence
- `make run` - Launch both API and processor in one terminal
- `make run-api` / `make run-processor` / `make run-processor-once` - Control individual services
- `make run-client` - Execute the example client workflow
- `make clean-storage` - Delete all queued job directories
- `make clean-venvs` - Remove analysis virtual environments (recreated on demand)
- `make clean-e2e-artifacts` - Remove e2e PID + log files (`e2e-*.pid/.log`)

## Project Structure

```text
protocol-analysis/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and endpoints
│   ├── file_storage.py      # File storage service
│   ├── config.py            # Configuration
│   └── version_mapping.py   # Protocol API to robot stack version mappings
├── analyze/
│   ├── __init__.py
│   ├── processor.py         # Analysis processor service
│   └── job_status.py        # Job status management
├── tests/
│   ├── unit/
│   │   ├── test_info.py
│   │   ├── test_analyze.py
│   │   └── test_file_storage.py
│   └── integration/
│       ├── test_info.py
│       └── test_analyze.py
├── run_processor.py         # CLI script for running processor
├── Makefile                 # Development tasks
├── pyproject.toml           # Project dependencies and configuration
└── README.md
```

## Endpoints

### GET `/info`

Returns application information including version and protocol API version mappings.

**Response:**

```json
{
  "version": "0.1.0",
  "protocol_api_versions": {
    "2.0": "3.14.0",
    "2.1": "3.15.2",
    ...
    "2.26": "8.7.0"
  }
}
```

### POST `/analyze`

Accepts a protocol file for analysis with optional custom labware, CSV data, and runtime parameters.

**Parameters:**

- `protocol_file` (required): Python protocol file (`.py` extension)
- `labware_files` (optional): Array of custom labware JSON files (`.json` extension)
- `csv_file` (optional): CSV data file (`.csv` or `.txt` extension)
- `rtp` (optional): Runtime parameters as JSON object

**Example using curl:**

```bash
curl -X POST http://localhost:8000/analyze \
  -F "protocol_file=@my_protocol.py" \
  -F "labware_files=@custom_labware1.json" \
  -F "labware_files=@custom_labware2.json" \
  -F "csv_file=@plate_data.csv" \
  -F 'rtp={"volume": 100, "temperature": 37}'
```

**Response:**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "protocol_file": "my_protocol.py",
  "labware_files": ["custom_labware1.json", "custom_labware2.json"],
  "csv_file": "plate_data.csv",
  "rtp": {
    "volume": 100,
    "temperature": 37
  }
}
```

The `job_id` is a unique identifier for this analysis job. Files are saved to `storage/jobs/{job_id}/` with the following structure:

- `{job_id}.py` - The protocol file
- `labware/` - Directory containing custom labware JSON files
- `{original_name}.csv` - The CSV file (if provided)
- `status.json` - Job status information
- `completed_analysis.json` - Analysis results (created by processor when complete)

The RTP parameters are stored with the response but not persisted to disk.

### GET `/jobs/{job_id}/status`

Check the status of an analysis job.

**Response:**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "updated_at": "2024-01-15T10:30:00.123456"
}
```

Status values: `pending`, `processing`, `completed`, `failed`

### GET `/jobs/{job_id}/result`

Retrieve the analysis results for a completed job.

**Response:**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "analysis": {
    "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "success",
    "files_analyzed": {
      "protocol_file": "my_protocol.py",
      "labware_files": ["custom_labware1.json"],
      "csv_file": "plate_data.csv"
    },
    "analysis": {
      "commands": [],
      "labware": [],
      "pipettes": [],
      "modules": [],
      "errors": [],
      "warnings": []
    },
    "metadata": {
      "protocol_api_version": "2.26",
      "processed_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

## Job Processing Flow

1. **Submit**: Client POSTs to `/analyze` with protocol files
2. **Queue**: API saves files to `storage/jobs/{job_id}/` and marks status as `pending`
3. **Process**: Processor service picks up pending jobs and analyzes them
4. **Complete**: Processor writes `completed_analysis.json` and updates status to `completed`
5. **Retrieve**: Client GETs `/jobs/{job_id}/result` to retrieve analysis

The processor service can run:

- **Daemon mode** (default): Continuously polls for new jobs
- **One-shot mode**: Processes pending jobs and exits (useful for cron/scheduled tasks)

## Usage Example

Here's a complete example workflow:

### 1. Start the Services

Terminal 1 - Start the API server:

```bash
make run-api
```

Terminal 2 - Start the processor:

```bash
make run-processor
```

### 2. Submit a Protocol for Analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -F "protocol_file=@example_protocol.py" \
  | jq '.'
```

Response:

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "protocol_file": "example_protocol.py",
  "labware_files": [],
  "csv_file": null,
  "rtp": null
}
```

### 3. Check Job Status

```bash
curl http://localhost:8000/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status | jq '.'
```

Response:

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "updated_at": "2024-01-15T10:30:00.123456"
}
```

### 4. Retrieve Analysis Results

```bash
curl http://localhost:8000/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/result | jq '.'
```

The response will contain the complete analysis with protocol metadata, commands, labware, pipettes, modules, and any errors or warnings.
