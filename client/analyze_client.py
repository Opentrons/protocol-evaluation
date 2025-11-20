"""Client for uploading protocols and retrieving analysis results."""

import time
from pathlib import Path
from typing import Any

import httpx


class AnalysisClient:
    """Client for interacting with the protocol analysis API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """Initialize the client with the base API URL."""
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def get_info(self) -> dict[str, Any]:
        """Get API information."""
        response = self.client.get(f"{self.base_url}/info")
        response.raise_for_status()
        return response.json()

    def submit_protocol(
        self,
        protocol_file: Path,
        robot_version: str = "8.7.0",
    ) -> str:
        """
        Submit a protocol for analysis.

        Args:
            protocol_file: Path to the protocol file
            robot_version: Robot server version (e.g., '8.7.0', '8.8.0')

        Returns:
            Job ID for tracking the analysis
        """
        with open(protocol_file, "rb") as f:
            files = {"protocol_file": (protocol_file.name, f, "text/x-python")}
            data = {"robot_version": robot_version}

            response = self.client.post(
                f"{self.base_url}/analyze",
                files=files,
                data=data,
            )
            response.raise_for_status()
            result = response.json()
            return result["job_id"]

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the status of a job."""
        response = self.client.get(f"{self.base_url}/jobs/{job_id}/status")
        response.raise_for_status()
        return response.json()

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Get the result of a completed job."""
        response = self.client.get(f"{self.base_url}/jobs/{job_id}/result")
        response.raise_for_status()
        return response.json()

    def wait_for_completion(
        self, job_id: str, poll_interval: float = 1.0, max_wait: float = 300.0
    ) -> dict[str, Any]:
        """
        Poll job status until completion or timeout.

        Args:
            job_id: Job ID to poll
            poll_interval: Seconds between polls
            max_wait: Maximum seconds to wait

        Returns:
            Final job status

        Raises:
            TimeoutError: If job doesn't complete within max_wait
        """
        start_time = time.time()
        while True:
            status = self.get_job_status(job_id)

            if status["status"] in ["completed", "failed"]:
                return status

            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {max_wait} seconds"
                )

            time.sleep(poll_interval)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
