#!/usr/bin/env python3
"""Example client that submits a protocol and retrieves the analysis."""

import json
import sys
from pathlib import Path

from client.analyze_client import AnalysisClient


def main():
    """Run the example client."""
    # Path to the test protocol
    protocol_file = Path("test-files/simple/Flex_S_v2_24_P50_PAPI_Changes.py")

    if not protocol_file.exists():
        print(f"Error: Protocol file not found: {protocol_file}")
        sys.exit(1)

    print(f"Submitting protocol: {protocol_file.name}")
    print("-" * 80)

    with AnalysisClient() as client:
        # Check API info
        info = client.get_info()
        print(f"API Version: {info['version']}")
        print(f"Supported versions: {info.get('protocol_api_versions', {}).keys()}")
        print()

        # Submit protocol using robot server versions
        print("Submitting protocol for analysis...")
        print("  - Submitting for robot server version 8.7.0 (current release)")
        job_id_870 = client.submit_protocol(protocol_file, robot_version="8.7.0")
        print(f"    Job ID: {job_id_870}")

        print("  - Submitting for robot server version 8.8.0 (next release)")
        job_id_880 = client.submit_protocol(protocol_file, robot_version="8.8.0")
        print(f"    Job ID: {job_id_880}")
        print()

        # Poll for completion of both jobs
        print("Waiting for analyses to complete...")
        print("  - Waiting for 8.7.0 analysis...")
        status_870 = client.wait_for_completion(job_id_870, poll_interval=0.5)
        print(f"    Status: {status_870['status']}")

        print("  - Waiting for 8.8.0 analysis...")
        status_880 = client.wait_for_completion(job_id_880, poll_interval=0.5)
        print(f"    Status: {status_880['status']}")
        print()

        # Get results for both versions
        for version, job_id, status in [
            ("8.7.0", job_id_870, status_870),
            ("8.8.0", job_id_880, status_880),
        ]:
            print(f"\n{'=' * 80}")
            print(f"Results for Robot Server Version {version}")
            print("=" * 80)

            if status["status"] == "completed":
                result = client.get_job_result(job_id)

                # Print first 50 lines of the result
                result_json = json.dumps(result, indent=2)
                lines = result_json.split("\n")

                print("Analysis Result (first 50 lines):")
                print("-" * 80)
                for i, line in enumerate(lines[:50], 1):
                    print(line)

                if len(lines) > 50:
                    print(f"\n... ({len(lines) - 50} more lines)")
            else:
                print(f"Analysis failed with status: {status['status']}")
                result = client.get_job_result(job_id)
                print(f"Error details: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
