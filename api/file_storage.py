"""File storage service for managing analysis job files."""

import uuid
from pathlib import Path

from fastapi import UploadFile

from api.config import STORAGE_BASE_DIR


class FileStorage:
    """Service for storing uploaded files for analysis jobs."""

    def __init__(self, base_dir: Path = STORAGE_BASE_DIR):
        """Initialize the file storage service.

        Args:
            base_dir: Base directory for storing job files
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_job_directory(self, job_id: str | None = None) -> str:
        """Create a new job directory with a unique ID.

        Args:
            job_id: Optional job ID. If not provided, generates a new UUID.

        Returns:
            The job ID (UUID string)
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        return job_id

    def get_job_directory(self, job_id: str) -> Path:
        """Get the path to a job's directory.

        Args:
            job_id: The job ID

        Returns:
            Path to the job directory
        """
        return self.base_dir / job_id

    async def save_file(
        self, job_id: str, file: UploadFile, subdirectory: str | None = None
    ) -> Path:
        """Save an uploaded file to the job directory.

        Args:
            job_id: The job ID
            file: The uploaded file
            subdirectory: Optional subdirectory within the job directory

        Returns:
            Path to the saved file
        """
        job_dir = self.get_job_directory(job_id)

        if subdirectory:
            target_dir = job_dir / subdirectory
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = job_dir

        file_path = target_dir / (file.filename or "unnamed_file")

        # Write file content
        content = await file.read()
        file_path.write_bytes(content)

        # Reset file pointer for potential reuse
        await file.seek(0)

        return file_path

    async def save_protocol_file(self, job_id: str, protocol_file: UploadFile) -> Path:
        """Save the protocol file to the job directory.

        Args:
            job_id: The job ID
            protocol_file: The protocol file to save

        Returns:
            Path to the saved protocol file
        """
        return await self.save_file(job_id, protocol_file)

    async def save_labware_files(
        self, job_id: str, labware_files: list[UploadFile]
    ) -> list[Path]:
        """Save labware files to the job directory.

        Args:
            job_id: The job ID
            labware_files: List of labware files to save

        Returns:
            List of paths to saved labware files
        """
        saved_paths = []
        for labware_file in labware_files:
            path = await self.save_file(job_id, labware_file, subdirectory="labware")
            saved_paths.append(path)
        return saved_paths

    async def save_csv_file(self, job_id: str, csv_file: UploadFile) -> Path:
        """Save the CSV file to the job directory.

        Args:
            job_id: The job ID
            csv_file: The CSV file to save

        Returns:
            Path to the saved CSV file
        """
        return await self.save_file(job_id, csv_file)

    def job_exists(self, job_id: str) -> bool:
        """Check if a job directory exists.

        Args:
            job_id: The job ID

        Returns:
            True if the job directory exists, False otherwise
        """
        return self.get_job_directory(job_id).exists()


# Global file storage instance
file_storage = FileStorage()
