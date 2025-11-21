"""Unit tests for the /evaluate endpoint validation logic."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from api.main import evaluate_protocol


def create_upload_file(filename: str, content: bytes = b"test content") -> UploadFile:
    """Helper to create an UploadFile for testing."""
    return UploadFile(filename=filename, file=BytesIO(content))


@pytest.mark.asyncio
@patch("api.main.file_storage")
@patch("api.main.write_job_metadata")
@patch("api.main.write_job_status")
async def test_evaluate_protocol_with_valid_protocol_file(
    mock_write_status, mock_write_metadata, mock_storage
):
    """Test that evaluate_protocol accepts a valid .py file."""
    mock_storage.create_job_directory.return_value = "test-job-id"
    mock_storage.save_protocol_file = AsyncMock()
    mock_storage.base_dir.return_value = "/tmp"

    protocol_file = create_upload_file("protocol.py")

    response = await evaluate_protocol(
        robot_version="8.7.0",
        protocol_file=protocol_file,
        labware_files=[],
        csv_file=None,
        rtp=None,
    )

    assert response.protocol_file == "protocol.py"
    assert response.labware_files == []
    assert response.csv_file is None
    assert response.rtp is None
    assert response.job_id == "test-job-id"
    assert response.robot_version == "8.7.0"


@pytest.mark.asyncio
async def test_evaluate_protocol_rejects_non_py_protocol_file():
    """Test that evaluate_protocol rejects protocol files without .py extension."""
    protocol_file = create_upload_file("protocol.txt")

    with pytest.raises(HTTPException) as exc_info:
        await evaluate_protocol(
            robot_version="8.7.0",
            protocol_file=protocol_file,
            labware_files=[],
            csv_file=None,
            rtp=None,
        )

    assert exc_info.value.status_code == 400
    assert "must have a .py extension" in exc_info.value.detail


@pytest.mark.asyncio
async def test_evaluate_protocol_rejects_unsupported_version():
    """Test that evaluate_protocol rejects unsupported robot server versions."""
    protocol_file = create_upload_file("protocol.py")

    with pytest.raises(HTTPException) as exc_info:
        await evaluate_protocol(
            robot_version="99.99.99",
            protocol_file=protocol_file,
            labware_files=[],
            csv_file=None,
            rtp=None,
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported robot server version" in exc_info.value.detail
