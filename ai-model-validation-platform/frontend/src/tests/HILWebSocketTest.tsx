import React, { useEffect, useState, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import websocketService from '../services/websocketService';

interface TestMessage {
  id: string;
  event: string;
  data: any;
  timestamp: string;
}

interface ConnectionStats {
  isConnected: boolean;
  connectionState: string;
  totalMessages: number;
  lastMessageTime?: string;
  errors: string[];
}

const HILWebSocketTest: React.FC = () => {
  const [messages, setMessages] = useState<TestMessage[]>([]);
  const [stats, setStats] = useState<ConnectionStats>({
    isConnected: false,
    connectionState: 'disconnected',
    totalMessages: 0,
    errors: []
  });
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});
  const messageCountRef = useRef(0);
  const startTimeRef = useRef<number>();

  // Use the WebSocket hook
  const {
    isConnected,
    connectionState,
    error,
    emit,
    subscribe
  } = useWebSocket();

  // Test session management
  const [testSessionId, setTestSessionId] = useState<string>('');
  const [isRunningTest, setIsRunningTest] = useState(false);

  useEffect(() => {
    startTimeRef.current = Date.now();
    
    // Update connection stats
    setStats(prev => ({
      ...prev,
      isConnected,
      connectionState,
      errors: error ? [...prev.errors, error.message] : prev.errors
    }));

    // Subscribe to various events for testing
    const unsubscribers: (() => void)[] = [];

    // Connection status events
    const unsubConnection = subscribe('connection_status', (data: any) => {
      addMessage('connection_status', data);
      setTestResults(prev => ({ ...prev, connectionStatus: true }));
    });
    unsubscribers.push(unsubConnection);

    // Detection events for HIL testing
    const unsubDetection = subscribe('detection_event', (data: any) => {
      addMessage('detection_event', data);
      setTestResults(prev => ({ ...prev, detectionEvents: true }));
    });
    unsubscribers.push(unsubDetection);

    // HIL-specific updates
    const unsubHIL = subscribe('hil_update', (data: any) => {
      addMessage('hil_update', data);
      setTestResults(prev => ({ ...prev, hilUpdates: true }));
    });
    unsubscribers.push(unsubHIL);

    // Progress updates
    const unsubProgress = subscribe('progress_update', (data: any) => {
      addMessage('progress_update', data);
      setTestResults(prev => ({ ...prev, progressUpdates: true }));
    });
    unsubscribers.push(unsubProgress);

    // Test session updates
    const unsubSession = subscribe('test_session_update', (data: any) => {
      addMessage('test_session_update', data);
      setTestResults(prev => ({ ...prev, sessionUpdates: true }));
      
      // Check if session completed
      if (data.status === 'completed') {
        setIsRunningTest(false);
      }
    });
    unsubscribers.push(unsubSession);

    // Heartbeat events
    const unsubHeartbeat = subscribe('heartbeat_ping', (data: any) => {
      addMessage('heartbeat_ping', data);
      setTestResults(prev => ({ ...prev, heartbeat: true }));
      
      // Respond to heartbeat
      emit('heartbeat_pong', { timestamp: Date.now(), ...data });
    });
    unsubscribers.push(unsubHeartbeat);

    // System notifications
    const unsubNotifications = subscribe('system_notification', (data: any) => {
      addMessage('system_notification', data);
      setTestResults(prev => ({ ...prev, systemNotifications: true }));
    });
    unsubscribers.push(unsubNotifications);

    // Subscription confirmations
    const unsubConfirm = subscribe('subscription_confirmed', (data: any) => {
      addMessage('subscription_confirmed', data);
      setTestResults(prev => ({ ...prev, subscriptions: true }));
    });
    unsubscribers.push(unsubConfirm);

    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [isConnected, connectionState, error, subscribe, emit]);

  const addMessage = (event: string, data: any) => {
    const message: TestMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      event,
      data,
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => {
      const newMessages = [message, ...prev];
      // Keep only last 100 messages
      return newMessages.slice(0, 100);
    });
    
    messageCountRef.current += 1;
    setStats(prev => ({
      ...prev,
      totalMessages: messageCountRef.current,
      lastMessageTime: message.timestamp
    }));
  };

  const startHILTestSession = () => {
    if (!isConnected) {
      alert('WebSocket not connected. Please wait for connection.');
      return;
    }

    const sessionId = `hil_test_${Date.now()}`;
    setTestSessionId(sessionId);
    setIsRunningTest(true);
    
    // Subscribe to session-specific updates
    emit('subscribe_to_updates', {
      type: 'session',
      target_id: sessionId
    });

    // Start the test session
    emit('start_test_session', {
      session_id: sessionId,
      project_id: 'hil_test_project'
    });
    
    console.log(`🧪 Started HIL test session: ${sessionId}`);
  };

  const stopHILTestSession = () => {
    if (testSessionId) {
      emit('stop_test_session', {
        session_id: testSessionId
      });
      setIsRunningTest(false);
      console.log(`⏹️ Stopped HIL test session: ${testSessionId}`);
    }
  };

  const subscribeToUpdates = (type: string, targetId?: string) => {
    emit('subscribe_to_updates', {
      type,
      target_id: targetId
    });
    console.log(`📡 Subscribed to ${type} updates${targetId ? ` for ${targetId}` : ''}`);
  };

  const sendTestPing = () => {
    emit('ping', { timestamp: Date.now(), test: true });
    console.log('🏓 Sent test ping');
  };

  const clearMessages = () => {
    setMessages([]);
    messageCountRef.current = 0;
    setStats(prev => ({ ...prev, totalMessages: 0, lastMessageTime: undefined }));
  };

  const getTestScore = () => {
    const totalTests = Object.keys(testResults).length;
    const passedTests = Object.values(testResults).filter(Boolean).length;
    return totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0;
  };

  const getConnectionStatusColor = () => {
    if (isConnected) return 'text-green-600';
    if (connectionState === 'connecting') return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-4">
          🧪 HIL WebSocket Integration Test
        </h1>
        
        {/* Connection Status */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold text-gray-700 mb-2">Connection Status</h3>
            <div className={`text-lg font-bold ${getConnectionStatusColor()}`}>
              {isConnected ? '✅ Connected' : `❌ ${connectionState}`}
            </div>
            {error && (
              <div className="text-red-500 text-sm mt-1">
                Error: {error.message}
              </div>
            )}
          </div>
          
          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold text-gray-700 mb-2">Message Stats</h3>
            <div className="text-lg font-bold text-blue-600">
              {stats.totalMessages} messages
            </div>
            {stats.lastMessageTime && (
              <div className="text-sm text-gray-500">
                Last: {new Date(stats.lastMessageTime).toLocaleTimeString()}
              </div>
            )}
          </div>
          
          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold text-gray-700 mb-2">Test Score</h3>
            <div className="text-lg font-bold text-purple-600">
              {getTestScore()}% ({Object.values(testResults).filter(Boolean).length}/{Object.keys(testResults).length})
            </div>
          </div>
        </div>

        {/* Test Controls */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={startHILTestSession}
            disabled={!isConnected || isRunningTest}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
          >
            🚀 Start HIL Test Session
          </button>
          
          <button
            onClick={stopHILTestSession}
            disabled={!isConnected || !isRunningTest}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400"
          >
            ⏹️ Stop Test Session
          </button>
          
          <button
            onClick={() => subscribeToUpdates('general')}
            disabled={!isConnected}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
          >
            📡 Subscribe General
          </button>
          
          <button
            onClick={() => subscribeToUpdates('detections')}
            disabled={!isConnected}
            className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-gray-400"
          >
            🔍 Subscribe Detections
          </button>
          
          <button
            onClick={sendTestPing}
            disabled={!isConnected}
            className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:bg-gray-400"
          >
            🏓 Send Ping
          </button>
          
          <button
            onClick={clearMessages}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            🗑️ Clear Messages
          </button>
        </div>

        {/* Test Results */}
        <div className="mb-6">
          <h3 className="font-semibold text-gray-700 mb-2">Test Results</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(testResults).map(([test, passed]) => (
              <div
                key={test}
                className={`p-2 rounded text-sm ${
                  passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}
              >
                {passed ? '✅' : '❌'} {test}
              </div>
            ))}
          </div>
        </div>

        {/* Current Test Session */}
        {isRunningTest && (
          <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-6">
            <h3 className="font-semibold text-blue-800 mb-2">
              🔄 Running HIL Test Session
            </h3>
            <div className="text-blue-700">
              Session ID: <code className="bg-blue-100 px-2 py-1 rounded">{testSessionId}</code>
            </div>
          </div>
        )}

        {/* Error Log */}
        {stats.errors.length > 0 && (
          <div className="bg-red-50 border border-red-200 p-4 rounded-lg mb-6">
            <h3 className="font-semibold text-red-800 mb-2">❌ Errors</h3>
            {stats.errors.map((error, index) => (
              <div key={index} className="text-red-700 text-sm mb-1">
                {error}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Message Log */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">
          📨 Message Log ({messages.length})
        </h2>
        
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {messages.map((message) => (
            <div
              key={message.id}
              className="border border-gray-200 rounded p-3 hover:bg-gray-50"
            >
              <div className="flex justify-between items-start mb-2">
                <span className="font-semibold text-blue-600">
                  {message.event}
                </span>
                <span className="text-sm text-gray-500">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <pre className="text-sm text-gray-700 bg-gray-100 p-2 rounded overflow-x-auto">
                {JSON.stringify(message.data, null, 2)}
              </pre>
            </div>
          ))}
          
          {messages.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              No messages received yet. Start a test to see real-time updates.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HILWebSocketTest;