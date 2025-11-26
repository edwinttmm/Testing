#!/usr/bin/env python3
"""
LabJack HTTP Bridge Service
Provides HTTP REST API for LabJack hardware access from WSL/remote backend

This service runs on the machine with LabJack hardware (Windows/Linux)
and exposes an HTTP API on port 8080 for the backend to communicate.

Usage:
    python labjack_bridge_http.py [--port 8080] [--host 0.0.0.0]

Endpoints:
    GET  /status          - Get bridge and hardware status
    GET  /device-info     - Get detailed device information
    POST /read-analog     - Read analog input (AIN)
    POST /read-digital    - Read digital input (DIO)
    POST /stream-start    - Start stream mode
    POST /stream-read     - Read stream data
    POST /stream-stop     - Stop stream mode
    GET  /health          - Health check endpoint
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional

# Try to import LabJack library
try:
    import labjack.ljm as ljm
    LABJACK_AVAILABLE = True
    print("✅ LabJack library imported successfully")
except ImportError as e:
    LABJACK_AVAILABLE = False
    print(f"⚠️ LabJack library not available: {e}")
    print("💡 Install with: pip install labjack-ljm")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('labjack_bridge_http.log')
    ]
)
logger = logging.getLogger(__name__)


class LabJackBridge:
    """LabJack hardware interface"""

    def __init__(self):
        self.handle = None
        self.device_info = {}
        self.streaming = False
        self.stream_config = {}
        self.connect()

    def connect(self) -> bool:
        """Connect to LabJack device"""
        if not LABJACK_AVAILABLE:
            logger.warning("LabJack library not available")
            return False

        try:
            logger.info("🔌 Attempting to connect to LabJack...")

            # Try to open any LabJack device
            self.handle = ljm.openS("ANY", "ANY", "ANY")

            # Get device information
            info = ljm.getHandleInfo(self.handle)
            device_type_int = info[0]
            connection_type_int = info[1]
            serial_number = info[2]

            # Convert device type integer to string
            device_type_map = {
                4: "T4",
                7: "T7",
                200: "T8",
                6: "U6",
                3: "U3",
                9: "UE9"
            }
            device_type = device_type_map.get(device_type_int, f"Unknown({device_type_int})")

            # Convert connection type integer to string
            connection_type_map = {
                1: "USB",
                3: "ETHERNET",
                4: "WIFI"
            }
            connection_type = connection_type_map.get(connection_type_int, f"Unknown({connection_type_int})")

            self.device_info = {
                "device_type": device_type,
                "connection_type": connection_type,
                "serial_number": str(serial_number),
                "firmware_version": ljm.eReadName(self.handle, "FIRMWARE_VERSION"),
                "hardware_version": ljm.eReadName(self.handle, "HARDWARE_VERSION")
            }

            logger.info("✅ LabJack connected successfully!")
            logger.info(f"   Device: {device_type}")
            logger.info(f"   Connection: {connection_type}")
            logger.info(f"   Serial: {serial_number}")

            return True

        except Exception as e:
            logger.error(f"❌ LabJack connection failed: {e}")
            self.handle = None
            self.device_info = {}
            return False

    def disconnect(self):
        """Disconnect from LabJack"""
        if self.handle:
            try:
                if self.streaming:
                    self.stream_stop()
                ljm.close(self.handle)
                self.handle = None
                self.device_info = {}
                logger.info("🔌 LabJack disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            "bridge_active": True,
            "labjack_available": LABJACK_AVAILABLE,
            "connected": self.handle is not None,
            "device_info": self.device_info,
            "streaming": self.streaming,
            "timestamp": datetime.now().isoformat()
        }

    def read_analog(self, channel: str) -> float:
        """Read analog input channel"""
        if not self.handle:
            raise Exception("LabJack not connected")

        try:
            value = ljm.eReadName(self.handle, channel)
            logger.debug(f"📊 Read {channel}: {value:.4f}V")
            return value
        except Exception as e:
            logger.error(f"Error reading {channel}: {e}")
            raise

    def read_digital(self, channel: str) -> int:
        """Read digital input channel"""
        if not self.handle:
            raise Exception("LabJack not connected")

        try:
            value = int(ljm.eReadName(self.handle, channel))
            logger.debug(f"📊 Read {channel}: {value}")
            return value
        except Exception as e:
            logger.error(f"Error reading {channel}: {e}")
            raise

    def stream_start(self, channels: list, sample_rate: int) -> Dict[str, Any]:
        """Start stream mode"""
        if not self.handle:
            raise Exception("LabJack not connected")

        try:
            # Configure stream
            self.stream_config = {
                "channels": channels,
                "sample_rate": sample_rate,
                "scans_per_read": max(1, sample_rate // 10)  # Read 10 times per second
            }

            # Start stream
            scan_rate = ljm.eStreamStart(
                self.handle,
                len(channels),
                [ljm.nameToAddress(ch)[0] for ch in channels],
                sample_rate
            )

            self.streaming = True
            self.stream_config["actual_scan_rate"] = scan_rate

            logger.info(f"📡 Stream started: {channels} @ {scan_rate} Hz")

            return {
                "success": True,
                "channels": channels,
                "requested_rate": sample_rate,
                "actual_rate": scan_rate
            }

        except Exception as e:
            logger.error(f"Error starting stream: {e}")
            self.streaming = False
            raise

    def stream_read(self) -> Dict[str, Any]:
        """Read stream data"""
        if not self.streaming:
            raise Exception("Stream not active")

        try:
            # Read stream data
            ret = ljm.eStreamRead(self.handle)
            data = ret[0]

            # Organize data by channel
            num_channels = len(self.stream_config["channels"])
            channel_data = {}

            for i, channel in enumerate(self.stream_config["channels"]):
                channel_data[channel] = data[i::num_channels]

            return {
                "success": True,
                "data": channel_data,
                "samples_per_channel": len(channel_data[self.stream_config["channels"][0]]),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error reading stream: {e}")
            raise

    def stream_stop(self) -> Dict[str, Any]:
        """Stop stream mode"""
        if not self.streaming:
            return {"success": True, "message": "Stream not active"}

        try:
            ljm.eStreamStop(self.handle)
            self.streaming = False
            logger.info("⏹️ Stream stopped")

            return {
                "success": True,
                "message": "Stream stopped"
            }

        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            raise


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for bridge service"""

    bridge: Optional[LabJackBridge] = None

    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            if path == "/status":
                self.send_json_response(self.bridge.get_status())

            elif path == "/device-info":
                self.send_json_response({
                    "success": True,
                    "device_info": self.bridge.device_info,
                    "timestamp": datetime.now().isoformat()
                })

            elif path == "/health":
                self.send_json_response({
                    "status": "healthy",
                    "labjack_connected": self.bridge.handle is not None,
                    "timestamp": datetime.now().isoformat()
                })

            else:
                self.send_error_response(404, f"Unknown endpoint: {path}")

        except Exception as e:
            logger.error(f"GET error: {e}")
            self.send_error_response(500, str(e))

    def do_POST(self):
        """Handle POST requests"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(body.decode('utf-8')) if body else {}

            if path == "/read-analog":
                channel = data.get("channel", "AIN0")
                value = self.bridge.read_analog(channel)
                self.send_json_response({
                    "success": True,
                    "channel": channel,
                    "value": value,
                    "timestamp": datetime.now().isoformat()
                })

            elif path == "/read-digital":
                channel = data.get("channel", "DIO0")
                value = self.bridge.read_digital(channel)
                self.send_json_response({
                    "success": True,
                    "channel": channel,
                    "value": value,
                    "timestamp": datetime.now().isoformat()
                })

            elif path == "/stream-start":
                channels = data.get("channels", ["AIN0"])
                sample_rate = data.get("sample_rate", 1000)
                result = self.bridge.stream_start(channels, sample_rate)
                self.send_json_response(result)

            elif path == "/stream-read":
                result = self.bridge.stream_read()
                self.send_json_response(result)

            elif path == "/stream-stop":
                result = self.bridge.stream_stop()
                self.send_json_response(result)

            else:
                self.send_error_response(404, f"Unknown endpoint: {path}")

        except Exception as e:
            logger.error(f"POST error: {e}")
            self.send_error_response(500, str(e))

    def send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode('utf-8'))

    def send_error_response(self, status_code: int, message: str):
        """Send error response"""
        self.send_json_response({
            "success": False,
            "error": message,
            "timestamp": datetime.now().isoformat()
        }, status_code)

    def log_message(self, format, *args):
        """Override to use custom logger"""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='LabJack HTTP Bridge Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🌉 LabJack HTTP Bridge Service")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info("=" * 60)

    # Initialize LabJack bridge
    bridge = LabJackBridge()
    BridgeRequestHandler.bridge = bridge

    # Create HTTP server
    server = HTTPServer((args.host, args.port), BridgeRequestHandler)

    logger.info(f"✅ Bridge server started on http://{args.host}:{args.port}")
    logger.info("📡 Available endpoints:")
    logger.info("   GET  /status        - Bridge status")
    logger.info("   GET  /device-info   - Device information")
    logger.info("   GET  /health        - Health check")
    logger.info("   POST /read-analog   - Read analog channel")
    logger.info("   POST /read-digital  - Read digital channel")
    logger.info("   POST /stream-start  - Start streaming")
    logger.info("   POST /stream-read   - Read stream data")
    logger.info("   POST /stream-stop   - Stop streaming")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Shutting down bridge service...")
        bridge.disconnect()
        server.shutdown()
        logger.info("✅ Bridge service stopped")


if __name__ == "__main__":
    main()
