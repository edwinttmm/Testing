#!/bin/bash

echo "🔧 Fixing PostgreSQL enum validation errors..."
echo "================================================"

# Method 1: Run the Python fix script in the backend container
echo "Method 1: Running Python fix script in backend container..."
docker-compose exec backend python -c "
import psycopg2
import sys
import os

# Database configuration
db_config = {
    'host': 'postgres',
    'port': 5432,
    'database': 'vru_validation',
    'user': 'postgres',
    'password': os.getenv('POSTGRES_PASSWORD', 'secure_postgres_password')
}

try:
    # Connect to PostgreSQL
    print('📞 Connecting to PostgreSQL...')
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    # Check current invalid values
    print('🔍 Checking for invalid enum values...')
    cur.execute(\"SELECT id, name, camera_view, signal_type FROM projects WHERE camera_view = 'Mixed' OR signal_type = 'Mixed'\")
    invalid_records = cur.fetchall()
    
    if not invalid_records:
        print('✅ No invalid enum values found!')
        sys.exit(0)
    
    print(f'❌ Found {len(invalid_records)} records with invalid enum values')
    for record in invalid_records:
        print(f'   - ID: {record[0]}, Name: {record[1]}, camera_view: {record[2]}, signal_type: {record[3]}')
    
    # Fix the enum values
    print('🛠️ Fixing enum values...')
    
    # Update camera_view
    cur.execute(\"UPDATE projects SET camera_view = 'Multi-angle' WHERE camera_view = 'Mixed'\")
    camera_updates = cur.rowcount
    print(f'📹 Updated {camera_updates} camera_view values: Mixed → Multi-angle')
    
    # Update signal_type  
    cur.execute(\"UPDATE projects SET signal_type = 'Network Packet' WHERE signal_type = 'Mixed'\")
    signal_updates = cur.rowcount
    print(f'📡 Updated {signal_updates} signal_type values: Mixed → Network Packet')
    
    # Commit changes
    conn.commit()
    print('💾 Changes committed successfully')
    
    # Verify the fix
    print('🔍 Verifying fix...')
    cur.execute(\"SELECT COUNT(*) FROM projects WHERE camera_view = 'Mixed' OR signal_type = 'Mixed'\")
    remaining_invalid = cur.fetchone()[0]
    
    if remaining_invalid == 0:
        print('✅ All enum values fixed successfully!')
        print('🎉 /api/projects endpoint should now work!')
    else:
        print(f'⚠️ Warning: {remaining_invalid} records still have invalid values')
    
    cur.close()
    conn.close()
    print('🔌 Database connection closed')
    
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

echo ""
echo "🧪 Testing /api/projects endpoint..."
curl -s http://155.138.239.131:8000/api/projects | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if 'detail' in data and 'status_code' in data:
        print('❌ API still returning error:', data['detail'])
        sys.exit(1)
    else:
        projects = data.get('projects', data)
        if isinstance(projects, list):
            print(f'✅ API working! Found {len(projects)} projects')
            for project in projects:
                print(f'   - {project.get(\"name\", \"Unknown\")}: camera_view={project.get(\"camera_view\", \"N/A\")}, signal_type={project.get(\"signal_type\", \"N/A\")}')
        else:
            print('✅ API returned data:', data)
except json.JSONDecodeError:
    print('❌ Invalid JSON response from API')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error testing API: {e}')
    sys.exit(1)
"

echo ""
echo "================================================"
echo "✅ Enum fix complete! Projects page should now work."
echo "🌐 Try accessing: http://155.138.239.131:3000/projects"