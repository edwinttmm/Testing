#!/usr/bin/env python3
"""
LabJack Quick Test Utility

Runs a short LabJack monitoring session and prints every detection observed
above the configured voltage threshold. Useful to verify hardware wiring
before running full HIL scenarios.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import List


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.labjack_detection_service import get_detection_service
from services.labjack_service import get_labjack_service, ConnectionStatus


def parse_channels(raw: str) -> List[str]:
    if not raw:
        return ["AIN0"]
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Quick LabJack detection tester")
    parser.add_argument("--duration", type=int, default=15, help="Seconds to capture (default 15)")
    parser.add_argument("--channels", type=str, default="AIN0", help="Comma-separated channels (default AIN0)")
    parser.add_argument("--threshold", type=float, default=2.5, help="Voltage threshold (default 2.5V)")
    parser.add_argument("--sample-rate", type=int, default=500, help="Sample rate in Hz (default 500)")
    parser.add_argument("--debounce", type=int, default=0, help="Debounce period ms (default 0)")
    parser.add_argument("--allow-mock", action="store_true", help="Allow mock LabJack fallback")
    parser.add_argument("--continuous", action="store_true", help="Enable continuous window mode (emits while within bounds)")
    parser.add_argument("--continuous-lower", type=float, help="Lower bound for continuous mode (defaults to threshold)")
    parser.add_argument("--continuous-upper", type=float, help="Upper bound for continuous mode (defaults to max voltage)")
    parser.add_argument(
        "--continuous-interval",
        type=int,
        default=50,
        help="Minimum interval between continuous samples in milliseconds (default 50ms)",
    )
    parser.add_argument(
        "--steady-high",
        action="store_true",
        help="Emit periodic detections while voltage stays above threshold",
    )
    parser.add_argument(
        "--steady-interval",
        type=int,
        default=200,
        help="Interval in milliseconds for steady-high logging (default 200ms)",
    )
    parser.add_argument(
        "--polling",
        action="store_true",
        help="Force polling mode (disable hardware stream) to sanity-check direct reads",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,  # override logging config set during backend imports
    )

    channels = parse_channels(args.channels)
    session_id = f"labjack_quick_test_{int(time.time())}"

    monitor = get_detection_service()
    labjack = get_labjack_service()

    if labjack.status != ConnectionStatus.CONNECTED:
        logging.info("Connecting to LabJack hardware...")
        connected = await labjack.connect(allow_mock=args.allow_mock)
        if not connected:
            logging.error("Unable to connect to LabJack. Aborting quick test.")
            return

    detections = []

    def detection_callback(event) -> None:
        timestamp = (
            event.timestamp.isoformat()
            if hasattr(event.timestamp, "isoformat")
            else str(event.timestamp)
        )
        print(
            f"DETECTION session={event.session_id} channel={event.channel} "
            f"voltage={event.voltage:.3f}V ts={timestamp}"
        )
        detections.append(event)

    monitor.add_detection_callback(detection_callback)

    logging.info(
        "Starting quick test session '%s' on %s (threshold %.2fV, sample rate %dHz)",
        session_id,
        ",".join(channels),
        args.threshold,
        args.sample_rate,
    )

    started = monitor.start_monitoring(
        session_id,
        channels=channels,
        voltage_threshold=args.threshold,
        sample_rate=args.sample_rate,
        debounce_ms=args.debounce,
        store_in_db=False,
        enable_websocket=False,
        continuous_mode=args.continuous,
        continuous_lower_bound=args.continuous_lower or args.threshold,
        continuous_upper_bound=args.continuous_upper,
        continuous_interval_ms=args.continuous_interval,
        steady_high_logging=args.steady_high,
        steady_high_interval_ms=args.steady_interval,
        use_stream_mode=not args.polling,
    )

    if not started:
        logging.error("Failed to start LabJack monitoring session.")
        monitor.remove_detection_callback(detection_callback)
        return

    logging.info(
        "Monitoring for %d seconds. Toggle the selected channels above %.2fV to see detections.",
        args.duration,
        args.threshold,
    )

    try:
        await asyncio.sleep(args.duration)
    finally:
        monitor.stop_monitoring(session_id)
        monitor.remove_detection_callback(detection_callback)

    logging.info("Session complete. Total detections captured: %d", len(detections))

    # Inspect in-memory events to help diagnose quiet streams
    try:
        events = monitor.get_detection_events(session_id, from_database=False)
        logging.info("Detection service recorded %d event(s) for session %s", len(events), session_id)
        if events:
            sample = events[-1]
            logging.info(
                "Last event snapshot: channel=%s voltage=%.3f state=%s timestamp=%s",
                sample.get("channel"),
                sample.get("labjack_voltage") or sample.get("voltage") or 0.0,
                sample.get("metadata", {}).get("state", "unknown"),
                sample.get("timestamp"),
            )
    except Exception as exc:
        logging.warning("Unable to read detection events: %s", exc)

    if not detections:
        logging.info(
            "No detections observed. Check wiring/thresholds or run with --allow-mock for simulation."
        )


if __name__ == "__main__":
    asyncio.run(main())
