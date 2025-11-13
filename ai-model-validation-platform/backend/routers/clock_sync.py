"""
Clock Synchronization Router

Provides high-precision server time for client-server clock synchronization.
Implements NTP-style time sync to prevent timestamp mismatches.

Critical for:
- Video playback timing accuracy
- LabJack event correlation
- Ground truth matching within tolerance windows
"""

from fastapi import APIRouter
from datetime import datetime
import time

router = APIRouter()


@router.get("/api/clock-sync")
async def get_server_time():
    """
    Return high-precision server time for client synchronization.

    Client should:
    1. Record t0 = client time before request
    2. Send request to this endpoint
    3. Record t1 = client time after response
    4. Calculate RTT = t1 - t0
    5. Calculate offset = server_time_ms - (client_time + RTT/2)

    Returns:
        dict: Server time in multiple formats for maximum precision
            - server_time_ms: Milliseconds since epoch (integer)
            - server_time_ns: Nanoseconds since epoch (integer)
            - timestamp: ISO format UTC timestamp (string)

    Example Response:
        {
            "server_time_ms": 1699564800000,
            "server_time_ns": 1699564800000000000,
            "timestamp": "2023-11-10T00:00:00"
        }
    """
    return {
        "server_time_ms": int(time.time() * 1000),
        "server_time_ns": time.time_ns(),
        "timestamp": datetime.utcnow().isoformat()
    }
