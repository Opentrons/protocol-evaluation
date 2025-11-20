"""Protocol analysis processor service.

This service monitors for new analysis jobs and processes them.
It's designed to run separately from the FastAPI server.
"""

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from analyze.env_config import get_environment_for_version
from analyze.job_status import (
    JobStatus,
    read_job_metadata,
    read_job_status,
    write_job_status,
)
from analyze.venv_manager import VenvManager
from api.config import STORAGE_BASE_DIR

ANALYSIS_TIMEOUT = 120  # Timeout per protocol in seconds


class ProtocolProcessor:
    """Process protocol analysis jobs."""

    def __init__(self, storage_dir: Path = STORAGE_BASE_DIR):
        """Initialize the processor.

        Args:
            storage_dir: Base directory for job storage
        """
        self.storage_dir = storage_dir
        self.venv_manager = VenvManager()

    def get_job_files(self, job_id: str) -> dict[str, Any]:
        """Get all files for a job.

        Args:
            job_id: The job ID

        Returns:
            Dictionary with file paths and metadata
        """
        job_dir = self.storage_dir / job_id

        files: dict[str, Any] = {
            "job_id": job_id,
            "job_dir": str(job_dir),
            "protocol_file": None,
            "labware_files": [],
            "csv_file": None,
        }

        # Find protocol file
        for py_file in job_dir.glob("*.py"):
            files["protocol_file"] = str(py_file)
            break

        # Find labware files
        labware_dir = job_dir / "labware"
        if labware_dir.exists():
            files["labware_files"] = [str(f) for f in labware_dir.glob("*.json")]

        # Find CSV file
        for csv_file in job_dir.glob("*.csv"):
            files["csv_file"] = str(csv_file)
            break

        if not files["csv_file"]:
            for txt_file in job_dir.glob("*.txt"):
                files["csv_file"] = str(txt_file)
                break

        return files

    def process_job(self, job_id: str) -> None:
        """Process a single job.

        Args:
            job_id: The job ID to process
        """
        job_dir = self.storage_dir / job_id

        if not job_dir.exists():
            print(f"Job directory not found: {job_id}")
            return

        # Check if already completed
        if (job_dir / "completed_analysis.json").exists():
            print(f"Job {job_id} already completed")
            return

        # Update status to processing
        write_job_status(job_dir, JobStatus.PROCESSING)
        print(f"Processing job {job_id}...")

        try:
            # Read job metadata to get robot server version
            metadata = read_job_metadata(job_dir)
            robot_version = metadata.get("robot_version")

            if not robot_version:
                raise ValueError(
                    "Job metadata missing robot_version. "
                    "This job may have been created before version support was added."
                )

            print(f"Job requires robot server version: {robot_version}")

            # Get environment configuration for this version
            env_config = get_environment_for_version(robot_version)

            # Ensure the virtual environment exists
            python_path = self.venv_manager.ensure_venv_exists(env_config)
            print(f"Using Python: {python_path}")

            # Get all job files
            files = self.get_job_files(job_id)

            # Run the actual analysis using the protocol in the correct venv
            analysis_result = self._run_analysis(python_path, files, robot_version)

            # Write completed analysis
            completed_file = job_dir / "completed_analysis.json"
            completed_file.write_text(json.dumps(analysis_result, indent=2))

            # Update status to completed
            write_job_status(job_dir, JobStatus.COMPLETED)
            print(f"Job {job_id} completed successfully")

        except Exception as e:
            import traceback

            error_msg = f"Error processing job: {str(e)}"
            print(f"Job {job_id} failed: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            write_job_status(job_dir, JobStatus.FAILED, error=error_msg)

    def _extract_first_json_object(self, text: str) -> dict[str, Any] | None:
        """
        Attempts to extract the first valid JSON object from the given text string.
        Returns the parsed dict, or None if extraction fails.
        """
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _run_analysis(
        self, python_path: Path, files: dict[str, Any], robot_version: str
    ) -> dict[str, Any]:
        """Run protocol analysis in the specified virtual environment.

        Args:
            python_path: Path to the Python executable in the venv
            files: Dictionary containing file paths
            robot_version: Robot server version being used

        Returns:
            Analysis result dictionary
        """
        protocol_file = files.get("protocol_file")
        if not protocol_file:
            return {
                "job_id": files["job_id"],
                "status": "error",
                "error": "No protocol file found",
                "robot_version": robot_version,
            }

        # Build the analysis command using opentrons.cli.analyze
        cmd = [
            str(python_path),
            "-c",
            """
import asyncio
import io
import json
import sys
from pathlib import Path
from opentrons.cli.analyze import _analyze, _Output

protocol_file = Path(sys.argv[1])
labware_files = [Path(p) for p in sys.argv[2].split(',') if p]
files = labware_files + [protocol_file]
json_output_stream = io.BytesIO()
outputs = [_Output(to_file=json_output_stream, kind='json')]

try:
    exit_code = asyncio.run(_analyze(files, '{}', '{}', outputs, False, False, False))
except Exception as e:
    print(json.dumps({'error': f'Exception: {str(e)}'}), file=sys.stdout)
    sys.exit(1)

json_output_stream.seek(0)
json_bytes = json_output_stream.read()
try:
    json_str = json_bytes.decode('utf-8')
    result_json = json.loads(json_str)
except Exception:
    result_json = {'error': 'Failed to decode JSON output'}

print(json.dumps(result_json), file=sys.stdout)
sys.exit(exit_code)
""",
            protocol_file,
            ",".join(files.get("labware_files", [])),
        ]

        try:
            # Run the analysis with a timeout
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=ANALYSIS_TIMEOUT,
            )

            stdout = proc.stdout
            stderr = proc.stderr

            # Parse the result
            result_json = None
            try:
                result_json = json.loads(stdout)
            except Exception:
                result_json = self._extract_first_json_object(stdout)
                if result_json is None:
                    result_json = {
                        "error": "Failed to decode JSON output",
                        "raw": stdout,
                        "stderr": stderr,
                    }

            # Wrap the analysis result with our metadata
            return {
                "job_id": files["job_id"],
                "status": "success" if proc.returncode == 0 else "error",
                "robot_version": robot_version,
                "files_analyzed": {
                    "protocol_file": Path(protocol_file).name,
                    "labware_files": [
                        Path(f).name for f in files.get("labware_files", [])
                    ],
                    "csv_file": Path(files["csv_file"]).name
                    if files.get("csv_file")
                    else None,
                },
                "analysis": result_json,
                "logs": stderr,
                "metadata": {
                    "robot_version": robot_version,
                    "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "python_path": str(python_path),
                    "exit_code": proc.returncode,
                },
            }

        except subprocess.TimeoutExpired:
            return {
                "job_id": files["job_id"],
                "status": "error",
                "error": f"Analysis timed out after {ANALYSIS_TIMEOUT} seconds",
                "robot_version": robot_version,
                "files_analyzed": {
                    "protocol_file": Path(protocol_file).name,
                },
            }
        except Exception as e:
            return {
                "job_id": files["job_id"],
                "status": "error",
                "error": f"Analysis failed with error: {str(e)}",
                "robot_version": robot_version,
                "files_analyzed": {
                    "protocol_file": Path(protocol_file).name,
                },
            }

    def find_pending_jobs(self) -> list[str]:
        """Find all pending jobs that need processing.

        Returns:
            List of job IDs that are pending
        """
        pending_jobs: list[str] = []

        if not self.storage_dir.exists():
            return pending_jobs

        for job_dir in self.storage_dir.iterdir():
            if not job_dir.is_dir():
                continue

            job_id = job_dir.name

            # Skip if already has completed analysis
            if (job_dir / "completed_analysis.json").exists():
                continue

            # Check status
            status_data = read_job_status(job_dir)
            if status_data.get("status") in [
                JobStatus.PENDING.value,
                JobStatus.FAILED.value,
            ]:
                pending_jobs.append(job_id)

        return pending_jobs

    def run_once(self) -> int:
        """Process all pending jobs once.

        Returns:
            Number of jobs processed
        """
        pending_jobs = self.find_pending_jobs()

        for job_id in pending_jobs:
            self.process_job(job_id)

        return len(pending_jobs)

    def run_forever(self, poll_interval: int = 5) -> None:
        """Run the processor in a loop, checking for new jobs.

        Args:
            poll_interval: Seconds to wait between checks
        """
        print(f"Protocol processor started, polling every {poll_interval}s")
        print(f"Monitoring: {self.storage_dir}")

        while True:
            try:
                processed = self.run_once()
                if processed > 0:
                    print(f"Processed {processed} job(s)")
            except KeyboardInterrupt:
                print("\nShutting down processor...")
                break
            except Exception as e:
                print(f"Error in processor loop: {e}")

            time.sleep(poll_interval)


if __name__ == "__main__":
    processor = ProtocolProcessor()
    processor.run_forever()
