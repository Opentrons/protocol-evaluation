# Protocol Evaluation Client

This directory contains an HTTP client for interacting with the protocol evaluation service.

## Client Module

The `evaluate_client.py` module provides `EvaluationClient` and `AsyncEvaluationClient` classes for:

- Submitting protocols for evaluation
- Polling job status
- Retrieving analysis or simulation results

## Example Usage

See `../run_client.py` for a complete example that:

1. Connects to the API
2. Submits a protocol file
3. Polls until evaluation completes
4. Retrieves and displays the result

## Running the Example

Make sure the services are running:

```bash
make run
```

Then in another terminal:

```bash
make run-client
```

Or run directly:

```bash
uv run python run_client.py
```
