"""End-to-end test for protocol analysis workflow."""

import asyncio
from pathlib import Path

import pytest

from client.analyze_client import AsyncAnalysisClient

POLL_INTERVAL = 0.2


@pytest.mark.asyncio
async def test_analyze_protocol_e2e():
    """Test the complete workflow of submitting and analyzing a protocol."""
    # Path to the baseline test protocol
    protocol_file = Path("test-files/simple/Flex_S_v2_24_P50_PAPI_Changes.py")
    custom_protocol_file = Path(
        "test-files/custom-labware-only/Flex_S_v2_25_P50_P200_stacker_all_parts.py"
    )
    custom_labware_files = [
        Path(
            "test-files/custom-labware-only/custom_opentrons_tough_pcr_auto_sealing_lid.json"
        ),
        Path(
            "test-files/custom-labware-only/stackable_opentrons_96_wellplate_200ul_pcr_full_skirt.json"
        ),
    ]
    csv_protocol_file = Path("test-files/rtp-csv-only/OpentronsAI_CSV.py")
    csv_data_file = Path("test-files/rtp-csv-only/plates.csv")
    custom_csv_protocol_file = Path(
        "test-files/only-not-rtp-override/OpentronsAI_CSV_AND_CustomLabware.py"
    )
    custom_csv_labware_file = Path(
        "test-files/only-not-rtp-override/eppendorf_96_wellplate_150ul.json"
    )
    custom_csv_data_file = Path("test-files/only-not-rtp-override/plates.csv")

    assert protocol_file.exists(), f"Protocol file not found: {protocol_file}"
    assert custom_protocol_file.exists(), (
        f"Protocol file not found: {custom_protocol_file}"
    )
    for labware_path in custom_labware_files:
        assert labware_path.exists(), f"Labware file not found: {labware_path}"
    assert csv_protocol_file.exists(), f"Protocol file not found: {csv_protocol_file}"
    assert csv_data_file.exists(), f"CSV file not found: {csv_data_file}"
    assert custom_csv_protocol_file.exists(), (
        f"Protocol file not found: {custom_csv_protocol_file}"
    )
    assert custom_csv_labware_file.exists(), (
        f"Labware file not found: {custom_csv_labware_file}"
    )
    assert custom_csv_data_file.exists(), f"CSV file not found: {custom_csv_data_file}"

    async with AsyncAnalysisClient() as client:
        # Check API info
        info = await client.get_info()
        assert info["version"] == "0.1.0"
        assert "protocol_api_versions" in info
        assert "supported_robot_versions" in info
        assert len(info["supported_robot_versions"]) > 0

        (
            job_id_870,
            job_id_next,
            job_id_custom,
            job_id_csv,
            job_id_custom_csv,
        ) = await asyncio.gather(
            client.submit_protocol(protocol_file, robot_version="8.7.0"),
            client.submit_protocol(protocol_file, robot_version="next"),
            client.submit_protocol(
                custom_protocol_file,
                robot_version="8.7.0",
                labware_files=custom_labware_files,
            ),
            client.submit_protocol(
                csv_protocol_file,
                robot_version="8.7.0",
                csv_file=csv_data_file,
            ),
            client.submit_protocol(
                custom_csv_protocol_file,
                robot_version="8.7.0",
                labware_files=[custom_csv_labware_file],
                csv_file=custom_csv_data_file,
            ),
        )

        assert all(
            job_id
            for job_id in [
                job_id_870,
                job_id_next,
                job_id_custom,
                job_id_csv,
                job_id_custom_csv,
            ]
        )

        # Poll for completion of both jobs
        (
            status_870,
            status_next,
            status_custom,
            status_csv,
            status_custom_csv,
        ) = await asyncio.gather(
            client.wait_for_completion(job_id_870, poll_interval=POLL_INTERVAL),
            client.wait_for_completion(job_id_next, poll_interval=POLL_INTERVAL),
            client.wait_for_completion(job_id_custom, poll_interval=POLL_INTERVAL),
            client.wait_for_completion(job_id_csv, poll_interval=POLL_INTERVAL),
            client.wait_for_completion(job_id_custom_csv, poll_interval=POLL_INTERVAL),
        )
        assert status_870["status"] == "completed"
        assert status_next["status"] == "completed"
        assert status_custom["status"] == "completed"
        assert status_csv["status"] == "completed"
        assert status_custom_csv["status"] == "completed"

        # Get and verify results for 8.7.0
        (
            result_870,
            result_next,
            result_custom,
            result_csv,
            result_custom_csv,
        ) = await asyncio.gather(
            client.get_job_result(job_id_870),
            client.get_job_result(job_id_next),
            client.get_job_result(job_id_custom),
            client.get_job_result(job_id_csv),
            client.get_job_result(job_id_custom_csv),
        )

        assert result_870["status"] == "completed"
        assert result_870["analysis"] is not None
        assert result_870["analysis"]["status"] == "success"
        assert result_870["analysis"]["robot_version"] == "8.7.0"
        assert result_870["analysis"]["analysis"]["result"] == "ok"

        # Get and verify results for 'next'
        assert result_next["status"] == "completed"
        assert result_next["analysis"] is not None
        assert result_next["analysis"]["status"] == "success"
        assert result_next["analysis"]["robot_version"] == "next"
        assert result_next["analysis"]["analysis"]["result"] == "ok"

        # Get and verify results for protocol with custom labware
        assert result_custom["status"] == "completed"
        assert result_custom["analysis"] is not None
        assert result_custom["analysis"]["status"] == "success"
        assert result_custom["analysis"]["robot_version"] == "8.7.0"
        assert result_custom["analysis"]["analysis"]["result"] == "ok"

        analyzed_labware = result_custom["analysis"]["files_analyzed"]["labware_files"]
        assert analyzed_labware is not None, "Expected labware files in analysis output"
        expected_labware_names = {path.name for path in custom_labware_files}
        assert set(analyzed_labware) >= expected_labware_names

        # Get and verify results for protocol with CSV input
        assert result_csv["status"] == "completed"
        assert result_csv["analysis"] is not None
        assert result_csv["analysis"]["status"] == "success"
        assert result_csv["analysis"]["robot_version"] == "8.7.0"
        assert result_csv["analysis"]["analysis"]["result"] == "ok"
        analyzed_csv = result_csv["analysis"]["files_analyzed"]["csv_file"]
        assert analyzed_csv, "Expected csv file in analysis output"
        assert analyzed_csv == csv_data_file.name

        # Get and verify results for protocol requiring both labware and CSV
        assert result_custom_csv["status"] == "completed"
        assert result_custom_csv["analysis"] is not None
        assert result_custom_csv["analysis"]["status"] == "success"
        assert result_custom_csv["analysis"]["robot_version"] == "8.7.0"
        assert result_custom_csv["analysis"]["analysis"]["result"] == "ok"
        analyzed_custom_csv = result_custom_csv["analysis"]["files_analyzed"]
        assert analyzed_custom_csv["csv_file"] == custom_csv_data_file.name
        assert custom_csv_labware_file.name in analyzed_custom_csv["labware_files"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
