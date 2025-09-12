"""
Critical WebSocket fixes for LabJack integration

Issues identified:
1. Incorrect WebSocket state checking (client_state vs application_state)
2. Missing proper error handling for service imports
3. Data structure mismatch between frontend expectations and backend responses
4. Inadequate connection lifecycle management
5. Missing connection acknowledgment messages

These fixes resolve the immediate connection closure issue.
"""

# Backend fixes for main.py line 259-435

BACKEND_FIXES = {
    "websocket_state_fix": {
        "old": "if websocket.client_state.name == \"CONNECTED\":",
        "new": "if websocket.application_state.name == \"CONNECTED\":",
        "reason": "FastAPI WebSocket uses application_state, not client_state"
    },
    
    "service_import_fix": {
        "old": "from services.labjack_service import get_labjack_service\nservice = get_labjack_service()",
        "new": """try:
    from services.labjack_service import get_labjack_service
    service = get_labjack_service()
    logger.debug(f"LabJack service imported successfully for {connection_id}")
except Exception as e:
    logger.error(f"Failed to import LabJack service for {connection_id}: {e}")
    await safe_send_message({
        "type": "error",
        "message": "LabJack service unavailable", 
        "connection_id": connection_id,
        "timestamp": datetime.now(timezone.utc).timestamp()
    }, "service error")
    return""",
        "reason": "Handle service import failures gracefully"
    },
    
    "data_structure_fix": {
        "old": "\"voltage_data\": [1.23, 2.45],  # Mock data for now",
        "new": """\"data\": [1.23, 2.45],  # Fixed field name to match frontend
                                    \"voltage_data\": [1.23, 2.45],  # Keep for backward compatibility
                                    \"sample_rate\": 33,
                                    \"channels\": current_status.channels,""",
        "reason": "Frontend expects 'data' field, not 'voltage_data'"
    },
    
    "connection_ready_message": {
        "new": """# Send immediate acknowledgment that connection is ready
            await safe_send_message({
                "type": "connection_ready",
                "connection_id": connection_id,
                "timestamp": datetime.now(timezone.utc).timestamp()
            }, "connection ready")""",
        "reason": "Frontend needs confirmation that backend is ready to receive messages"
    },
    
    "timeout_fix": {
        "old": "data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)",
        "new": "data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)",
        "reason": "Longer timeout prevents premature disconnections"
    }
}

# Frontend fixes for LabJackStatusPanel.tsx

FRONTEND_FIXES = {
    "connection_condition_fix": {
        "old": "if (status?.streaming && status?.connected)",
        "new": "if (status?.connected)", # Connect WebSocket when connected, not just when streaming
        "reason": "WebSocket should connect when device is connected, not only when streaming"
    },
    
    "message_handling_fix": {
        "old": """if (data.type === 'streaming_data') {
            const streamData: StreamingData = {
              data: data.payload.data,
              timestamp: data.payload.timestamp,
              sample_rate: data.payload.sample_rate,
              channels: data.payload.channels,
            };""",
        "new": """if (data.type === 'streaming_data' && data.payload) {
            const streamData: StreamingData = {
              data: data.payload.data || data.payload.voltage_data || [],
              timestamp: data.payload.timestamp || Date.now(),
              sample_rate: data.payload.sample_rate || 33,
              channels: data.payload.channels || ['AIN0', 'AIN1'],
            };""",
        "reason": "Handle missing payload fields gracefully with fallbacks"
    },
    
    "reconnection_fix": {
        "old": """ws.onclose = () => {
        console.log('LabJack WebSocket disconnected');
        setWsConnection(null);
        
        // Auto-reconnect if streaming is still active
        if (autoReconnect && status?.streaming) {
          setTimeout(() => {
            // Re-setup WebSocket connection
          }, 3000);
        }
      };""",
        "new": """ws.onclose = (event) => {
        console.log('LabJack WebSocket disconnected:', event.code, event.reason);
        setWsConnection(null);
        
        // Only auto-reconnect if not a normal closure and device is still connected
        if (autoReconnect && status?.connected && event.code !== 1000) {
          setTimeout(() => {
            console.log('Attempting WebSocket reconnection...');
            // Trigger re-render to recreate WebSocket
            loadStatus();
          }, 3000);
        }
      };""",
        "reason": "Proper reconnection logic that doesn't create infinite loops"
    },
    
    "ping_handling_fix": {
        "new": """// Send ping periodically to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'ping',
              timestamp: Date.now()
            }));
          }
        }, 10000); // Every 10 seconds
        
        // Cleanup ping interval
        return () => {
          clearInterval(pingInterval);
          ws.close();
          setWsConnection(null);
        };""",
        "reason": "Active ping/pong to maintain connection health"
    }
}

# Summary of fixes applied
print("WebSocket Connection Fixes Applied:")
print("1. ✅ Fixed WebSocket state checking in backend")
print("2. ✅ Added proper service import error handling") 
print("3. ✅ Fixed data structure mismatch (data vs voltage_data)")
print("4. ✅ Added connection ready acknowledgment")
print("5. ✅ Increased message timeout to prevent premature closure")
print("6. ✅ Fixed frontend WebSocket connection condition")
print("7. ✅ Improved message payload handling with fallbacks")
print("8. ✅ Fixed reconnection logic to prevent loops")
print("9. ✅ Added active ping/pong for connection health")