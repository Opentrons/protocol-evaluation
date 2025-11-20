"""End-to-end test for protocol analysis workflow."""

from pathlib import Path

import pytest

from client.analyze_client import AnalysisClient


def test_analyze_protocol_e2e():
    """Test the complete workflow of submitting and analyzing a protocol."""
    # Path to the test protocol
    protocol_file = Path("test-files/simple/Flex_S_v2_24_P50_PAPI_Changes.py")

    assert protocol_file.exists(), f"Protocol file not found: {protocol_file}"

    with AnalysisClient() as client:
        # Check API info
        info = client.get_info()
        assert info["version"] == "0.1.0"
        assert "protocol_api_versions" in info
        assert "supported_robot_versions" in info
        assert len(info["supported_robot_versions"]) > 0

        # Submit protocol for analysis with robot version 8.7.0
        job_id_870 = client.submit_protocol(protocol_file, robot_version="8.7.0")
        assert job_id_870 is not None
        assert len(job_id_870) > 0

        # Submit protocol for analysis with robot version 8.8.0
        job_id_880 = client.submit_protocol(protocol_file, robot_version="8.8.0")
        assert job_id_880 is not None
        assert len(job_id_880) > 0

        # Poll for completion of both jobs
        status_870 = client.wait_for_completion(job_id_870, poll_interval=0.5)
        assert status_870["status"] == "completed"

        status_880 = client.wait_for_completion(job_id_880, poll_interval=0.5)
        assert status_880["status"] == "completed"

        # Get and verify results for 8.7.0
        result_870 = client.get_job_result(job_id_870)
        assert result_870["status"] == "completed"
        assert result_870["analysis"] is not None
        assert result_870["analysis"]["status"] == "success"
        assert result_870["analysis"]["robot_version"] == "8.7.0"
        assert result_870["analysis"]["analysis"]["result"] == "ok"

        # Get and verify results for 8.8.0
        result_880 = client.get_job_result(job_id_880)
        assert result_880["status"] == "completed"
        assert result_880["analysis"] is not None
        assert result_880["analysis"]["status"] == "success"
        assert result_880["analysis"]["robot_version"] == "8.8.0"
        assert result_880["analysis"]["analysis"]["result"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
