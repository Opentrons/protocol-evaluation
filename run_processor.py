#!/usr/bin/env python3
"""Command-line interface for running the protocol processor."""

import argparse
import sys

from evaluate.processor import ProtocolProcessor


def main() -> int:
    """Run the protocol processor.

    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        description="Protocol Analysis Processor - processes analysis jobs"
    )
    parser.add_argument(
        "--mode",
        choices=["once", "daemon"],
        default="daemon",
        help="Run mode: 'once' processes pending jobs and exits, 'daemon' runs continuously",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Polling interval in seconds for daemon mode (default: 5)",
    )

    args = parser.parse_args()

    processor = ProtocolProcessor()

    if args.mode == "once":
        print("Running processor in one-shot mode...")
        processed = processor.run_once()
        print(f"Processed {processed} job(s)")
        return 0
    else:
        print(
            f"Starting processor in daemon mode (poll interval: {args.poll_interval}s)"
        )
        try:
            processor.run_forever(poll_interval=args.poll_interval)
        except KeyboardInterrupt:
            print("\nShutting down processor...")
        return 0


if __name__ == "__main__":
    sys.exit(main())
