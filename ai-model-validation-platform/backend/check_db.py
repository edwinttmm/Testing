#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('dev_database.db')
cursor = conn.cursor()

# Check the schema of detection_events table
cursor.execute('PRAGMA table_info(detection_events)')
columns = cursor.fetchall()
print('Detection Events table schema:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

print()

# Check recent detection events
cursor.execute('''
SELECT de.id, de.test_session_id, de.timestamp, de.confidence, de.class_label, de.labjack_voltage, de.created_at
FROM detection_events de
ORDER BY de.created_at DESC
LIMIT 5
''')

print('Recent Detection Events:')
events = cursor.fetchall()
for event in events:
    session_id = event[1] if event[1] else 'None'
    session_short = session_id[:8] + '...' if session_id != 'None' else 'None'
    voltage = event[5] or event[3] or 'N/A'
    print(f'  Event: {event[0][:8]}... | Session: {session_short} | Voltage: {voltage} | Time: {event[6]}')

# Find the session with the most recent events
cursor.execute('''
SELECT de.test_session_id, COUNT(*) as event_count, MAX(de.created_at) as latest_event
FROM detection_events de
WHERE de.test_session_id IS NOT NULL
GROUP BY de.test_session_id
ORDER BY latest_event DESC
LIMIT 3
''')

print()
print('Sessions with most recent events:')
recent_sessions = cursor.fetchall()
for session in recent_sessions:
    print(f'  Session: {session[0][:8]}... | Events: {session[1]} | Latest: {session[2]}')

conn.close()