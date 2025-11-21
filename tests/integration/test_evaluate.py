"""Integration tests for the /evaluate endpoint."""

import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_evaluate_endpoint_with_minimal_request(client):
    """Test /evaluate endpoint with only required protocol file."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test protocol"), "text/plain"),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 200
    data = response.json()
    assert data["protocol_file"] == "protocol.py"
    assert data["labware_files"] == []
    assert data["csv_file"] is None
    assert data["rtp"] is None
    assert "job_id" in data
    assert data["job_id"] is not None

    # Verify job directory was created and file was saved
    from api.file_storage import file_storage

    job_id = data["job_id"]
    assert file_storage.job_exists(job_id)
    job_dir = file_storage.get_job_directory(job_id)
    assert (job_dir / "protocol.py").exists()


def test_evaluate_endpoint_with_all_parameters(client):
    """Test /evaluate endpoint with all parameters provided."""
    files = [
        ("protocol_file", ("protocol.py", BytesIO(b"# test protocol"), "text/plain")),
        (
            "labware_files",
            ("labware1.json", BytesIO(b'{"name": "custom1"}'), "application/json"),
        ),
        (
            "labware_files",
            ("labware2.json", BytesIO(b'{"name": "custom2"}'), "application/json"),
        ),
        ("csv_file", ("data.csv", BytesIO(b"col1,col2\n1,2"), "text/csv")),
    ]
    data = {
        "rtp": json.dumps({"volume": 100, "temperature": 37}),
    }

    response = client.post(
        "/evaluate", files=files, data={**data, "robot_version": "8.7.0"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["protocol_file"] == "protocol.py"
    assert result["labware_files"] == ["labware1.json", "labware2.json"]
    assert result["csv_file"] == "data.csv"
    assert result["rtp"] == {"volume": 100, "temperature": 37}
    assert "job_id" in result

    # Verify files were saved
    from api.file_storage import file_storage

    job_id = result["job_id"]
    job_dir = file_storage.get_job_directory(job_id)
    assert (job_dir / "protocol.py").exists()
    assert (job_dir / "labware" / "labware1.json").exists()
    assert (job_dir / "labware" / "labware2.json").exists()
    assert (job_dir / "data.csv").exists()


def test_evaluate_endpoint_rejects_invalid_protocol_extension(client):
    """Test that /evaluate rejects protocol files without .py extension."""
    files = {
        "protocol_file": ("protocol.txt", BytesIO(b"# test"), "text/plain"),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 400
    assert "must have a .py extension" in response.json()["detail"]


def test_evaluate_endpoint_rejects_invalid_labware_extension(client):
    """Test that /evaluate rejects labware files without .json extension."""
    files = [
        ("protocol_file", ("protocol.py", BytesIO(b"# test"), "text/plain")),
        ("labware_files", ("labware.txt", BytesIO(b"invalid"), "text/plain")),
    ]

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 400
    assert "must have a .json extension" in response.json()["detail"]


def test_evaluate_endpoint_rejects_invalid_csv_extension(client):
    """Test that /evaluate rejects CSV files with invalid extensions."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
        "csv_file": ("data.json", BytesIO(b"data"), "application/json"),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 400
    assert "must have a .csv or .txt extension" in response.json()["detail"]


def test_evaluate_endpoint_accepts_txt_as_csv(client):
    """Test that /evaluate accepts .txt files as CSV."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
        "csv_file": ("data.txt", BytesIO(b"col1,col2\n1,2"), "text/plain"),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 200
    data = response.json()
    assert data["csv_file"] == "data.txt"


def test_evaluate_endpoint_with_rtp_object(client):
    """Test /evaluate endpoint with RTP parameter."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
    }
    data = {
        "rtp": json.dumps(
            {
                "pipette_volume": 20,
                "well_count": 96,
                "enabled": True,
            }
        ),
    }

    response = client.post(
        "/evaluate", files=files, data={**data, "robot_version": "8.7.0"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["rtp"] == {
        "pipette_volume": 20,
        "well_count": 96,
        "enabled": True,
    }


def test_evaluate_endpoint_rejects_invalid_rtp_json(client):
    """Test that /evaluate rejects invalid RTP JSON."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
    }
    data = {
        "rtp": "{invalid json}",
    }

    response = client.post(
        "/evaluate", files=files, data={**data, "robot_version": "8.7.0"}
    )

    assert response.status_code == 400
    assert "Invalid RTP JSON" in response.json()["detail"]


def test_evaluate_endpoint_with_multiple_labware_files(client):
    """Test /evaluate endpoint with multiple labware files."""
    files = [
        ("protocol_file", ("protocol.py", BytesIO(b"# test"), "text/plain")),
        (
            "labware_files",
            ("custom1.json", BytesIO(b'{"type": "plate"}'), "application/json"),
        ),
        (
            "labware_files",
            ("custom2.json", BytesIO(b'{"type": "tube"}'), "application/json"),
        ),
        (
            "labware_files",
            ("custom3.json", BytesIO(b'{"type": "reservoir"}'), "application/json"),
        ),
    ]

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["labware_files"]) == 3
    assert "custom1.json" in data["labware_files"]
    assert "custom2.json" in data["labware_files"]
    assert "custom3.json" in data["labware_files"]


def test_evaluate_endpoint_without_optional_files(client):
    """Test /evaluate endpoint without any optional files."""
    files = {
        "protocol_file": (
            "my_protocol.py",
            BytesIO(b"from opentrons import protocol_api"),
            "text/plain",
        ),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 200
    data = response.json()
    assert data["protocol_file"] == "my_protocol.py"
    assert data["labware_files"] == []
    assert data["csv_file"] is None
    assert data["rtp"] is None


def test_evaluate_endpoint_returns_json(client):
    """Test that /evaluate endpoint returns JSON content."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
    }

    response = client.post("/evaluate", files=files, data={"robot_version": "8.7.0"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_evaluate_endpoint_requires_protocol_file(client):
    """Test that /evaluate endpoint requires protocol_file."""
    response = client.post("/evaluate", data={"robot_version": "8.7.0"})

    assert response.status_code == 422  # Unprocessable Entity


def test_evaluate_endpoint_with_complex_rtp(client):
    """Test /evaluate endpoint with nested RTP structure."""
    files = {
        "protocol_file": ("protocol.py", BytesIO(b"# test"), "text/plain"),
    }
    rtp_data = {
        "volumes": [10, 20, 30, 40],
        "positions": {"A1": 1, "B2": 2},
        "metadata": {
            "author": "Test User",
            "date": "2024-01-01",
        },
    }
    data = {
        "rtp": json.dumps(rtp_data),
    }

    response = client.post(
        "/evaluate", files=files, data={**data, "robot_version": "8.7.0"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["rtp"] == rtp_data


def test_evaluate_endpoint_only_accepts_post(client):
    """Test that /evaluate endpoint only accepts POST requests."""
    response = client.get("/evaluate")
    assert response.status_code == 405  # Method Not Allowed

    response = client.put("/evaluate")
    assert response.status_code == 405

    response = client.delete("/evaluate")
    assert response.status_code == 405
