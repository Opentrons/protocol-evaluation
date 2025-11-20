"""Unit tests for the file storage service."""

import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile

from api.file_storage import FileStorage


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary storage directory for testing."""
    return tmp_path / "test_storage"


@pytest.fixture
def storage(temp_storage_dir):
    """Create a FileStorage instance with a temporary directory."""
    return FileStorage(base_dir=temp_storage_dir)


def create_upload_file(filename: str, content: bytes = b"test content") -> UploadFile:
    """Helper to create an UploadFile for testing."""
    return UploadFile(filename=filename, file=BytesIO(content))


def test_file_storage_initialization(temp_storage_dir):
    """Test that FileStorage creates the base directory on initialization."""
    _ = FileStorage(base_dir=temp_storage_dir)
    assert temp_storage_dir.exists()
    assert temp_storage_dir.is_dir()


def test_create_job_directory_generates_uuid(storage):
    """Test that create_job_directory generates a valid UUID."""
    job_id = storage.create_job_directory()

    # Validate that it's a valid UUID
    uuid_obj = uuid.UUID(job_id)
    assert str(uuid_obj) == job_id

    # Verify directory was created
    job_dir = storage.get_job_directory(job_id)
    assert job_dir.exists()
    assert job_dir.is_dir()


def test_create_job_directory_with_custom_id(storage):
    """Test that create_job_directory accepts a custom job ID."""
    custom_id = "custom-job-123"
    job_id = storage.create_job_directory(job_id=custom_id)

    assert job_id == custom_id

    job_dir = storage.get_job_directory(job_id)
    assert job_dir.exists()
    assert job_dir.name == custom_id


def test_get_job_directory(storage):
    """Test that get_job_directory returns the correct path."""
    job_id = "test-job-id"
    job_dir = storage.get_job_directory(job_id)

    expected_path = storage.base_dir / job_id
    assert job_dir == expected_path


@pytest.mark.asyncio
async def test_save_protocol_file(storage):
    """Test saving a protocol file."""
    job_id = storage.create_job_directory()
    protocol_file = create_upload_file("protocol.py", b"# protocol content")

    saved_path = await storage.save_protocol_file(job_id, protocol_file)

    assert saved_path.exists()
    assert saved_path.name == "protocol.py"
    assert saved_path.read_bytes() == b"# protocol content"
    assert saved_path.parent == storage.get_job_directory(job_id)


@pytest.mark.asyncio
async def test_save_labware_files(storage):
    """Test saving multiple labware files."""
    job_id = storage.create_job_directory()
    labware_files = [
        create_upload_file("labware1.json", b'{"name": "custom1"}'),
        create_upload_file("labware2.json", b'{"name": "custom2"}'),
    ]

    saved_paths = await storage.save_labware_files(job_id, labware_files)

    assert len(saved_paths) == 2

    # Check first file
    assert saved_paths[0].exists()
    assert saved_paths[0].name == "labware1.json"
    assert saved_paths[0].read_bytes() == b'{"name": "custom1"}'
    assert saved_paths[0].parent.name == "labware"

    # Check second file
    assert saved_paths[1].exists()
    assert saved_paths[1].name == "labware2.json"
    assert saved_paths[1].read_bytes() == b'{"name": "custom2"}'
    assert saved_paths[1].parent.name == "labware"


@pytest.mark.asyncio
async def test_save_csv_file(storage):
    """Test saving a CSV file."""
    job_id = storage.create_job_directory()
    csv_file = create_upload_file("data.csv", b"col1,col2\n1,2")

    saved_path = await storage.save_csv_file(job_id, csv_file)

    assert saved_path.exists()
    assert saved_path.name == "data.csv"
    assert saved_path.read_bytes() == b"col1,col2\n1,2"
    assert saved_path.parent == storage.get_job_directory(job_id)


@pytest.mark.asyncio
async def test_save_file_with_subdirectory(storage):
    """Test saving a file to a subdirectory."""
    job_id = storage.create_job_directory()
    file = create_upload_file("test.txt", b"test content")

    saved_path = await storage.save_file(job_id, file, subdirectory="subdir")

    assert saved_path.exists()
    assert saved_path.name == "test.txt"
    assert saved_path.parent.name == "subdir"
    assert saved_path.read_bytes() == b"test content"


@pytest.mark.asyncio
async def test_save_file_without_subdirectory(storage):
    """Test saving a file without a subdirectory."""
    job_id = storage.create_job_directory()
    file = create_upload_file("test.txt", b"test content")

    saved_path = await storage.save_file(job_id, file)

    assert saved_path.exists()
    assert saved_path.parent == storage.get_job_directory(job_id)


def test_job_exists_returns_true_for_existing_job(storage):
    """Test that job_exists returns True for existing jobs."""
    job_id = storage.create_job_directory()

    assert storage.job_exists(job_id) is True


def test_job_exists_returns_false_for_nonexistent_job(storage):
    """Test that job_exists returns False for non-existent jobs."""
    assert storage.job_exists("nonexistent-job-id") is False


@pytest.mark.asyncio
async def test_complete_job_workflow(storage):
    """Test a complete workflow of creating a job and saving all file types."""
    # Create job
    job_id = storage.create_job_directory()
    assert storage.job_exists(job_id)

    # Save protocol file
    protocol_file = create_upload_file("protocol.py", b"# protocol")
    protocol_path = await storage.save_protocol_file(job_id, protocol_file)
    assert protocol_path.exists()

    # Save labware files
    labware_files = [
        create_upload_file("labware1.json", b"{}"),
        create_upload_file("labware2.json", b"{}"),
    ]
    labware_paths = await storage.save_labware_files(job_id, labware_files)
    assert len(labware_paths) == 2
    assert all(p.exists() for p in labware_paths)

    # Save CSV file
    csv_file = create_upload_file("data.csv", b"data")
    csv_path = await storage.save_csv_file(job_id, csv_file)
    assert csv_path.exists()

    # Verify directory structure
    job_dir = storage.get_job_directory(job_id)
    assert (job_dir / "protocol.py").exists()
    assert (job_dir / "labware").exists()
    assert (job_dir / "labware" / "labware1.json").exists()
    assert (job_dir / "labware" / "labware2.json").exists()
    assert (job_dir / "data.csv").exists()


@pytest.mark.asyncio
async def test_file_pointer_reset_after_save(storage):
    """Test that file pointer is reset after saving."""
    job_id = storage.create_job_directory()
    file = create_upload_file("test.txt", b"test content")

    # Save the file
    await storage.save_file(job_id, file)

    # Read the file content again (should work if pointer was reset)
    content = await file.read()
    assert content == b"test content"
