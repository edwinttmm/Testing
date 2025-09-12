#!/usr/bin/env python3
"""
CVAT PostgreSQL Database Diagnostic Tool
Identifies and resolves auth_user table access issues
"""

import subprocess
import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

class CVATDatabaseDiagnostic:
    def __init__(self):
        self.cvat_container = "ai_validation_cvat"
        self.db_container = "ai_validation_cvat_db"
        self.db_name = "cvat"
        self.db_user = "root"
        self.db_password = "cvat_password"
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "recommendations": [],
            "status": "unknown"
        }

    def run_command(self, command: List[str], capture_output: bool = True) -> Dict[str, Any]:
        """Run a command and return result with error handling"""
        try:
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }

    def check_containers_running(self) -> bool:
        """Check if required containers are running"""
        print("🔍 Checking container status...")
        
        # Check CVAT container
        result = self.run_command(["docker", "ps", "--filter", f"name={self.cvat_container}", "--format", "{{.Status}}"])
        if not result["success"] or not result["stdout"].strip():
            self.report["issues"].append("CVAT container is not running")
            return False
        
        # Check CVAT database container
        result = self.run_command(["docker", "ps", "--filter", f"name={self.db_container}", "--format", "{{.Status}}"])
        if not result["success"] or not result["stdout"].strip():
            self.report["issues"].append("CVAT database container is not running")
            return False
        
        print("✅ Both containers are running")
        return True

    def check_database_connection(self) -> bool:
        """Test PostgreSQL database connection"""
        print("🔍 Testing database connection...")
        
        result = self.run_command([
            "docker", "exec", self.db_container,
            "pg_isready", "-U", self.db_user, "-d", self.db_name
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Database connection failed: {result['stderr']}")
            return False
        
        print("✅ Database connection successful")
        return True

    def check_auth_user_table(self) -> Dict[str, Any]:
        """Check auth_user table existence and structure"""
        print("🔍 Checking auth_user table...")
        
        # Check if table exists
        result = self.run_command([
            "docker", "exec", self.db_container,
            "psql", "-U", self.db_user, "-d", self.db_name, "-t", "-c",
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'auth_user';"
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Could not query table information: {result['stderr']}")
            return {"exists": False, "structure": None}
        
        table_exists = result["stdout"].strip() == "1"
        
        if not table_exists:
            self.report["issues"].append("auth_user table does not exist")
            self.report["recommendations"].append("Run Django migrations to create auth_user table")
            return {"exists": False, "structure": None}
        
        # Get table structure
        result = self.run_command([
            "docker", "exec", self.db_container,
            "psql", "-U", self.db_user, "-d", self.db_name, "-c",
            "\\d auth_user"
        ])
        
        structure_info = result["stdout"] if result["success"] else "Could not retrieve structure"
        
        print("✅ auth_user table exists")
        return {"exists": True, "structure": structure_info}

    def check_table_permissions(self) -> bool:
        """Check table permissions and ownership"""
        print("🔍 Checking table permissions...")
        
        # Check table ownership
        result = self.run_command([
            "docker", "exec", self.db_container,
            "psql", "-U", self.db_user, "-d", self.db_name, "-t", "-c",
            "SELECT tableowner FROM pg_tables WHERE tablename = 'auth_user';"
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Could not check table ownership: {result['stderr']}")
            return False
        
        owner = result["stdout"].strip()
        print(f"📝 auth_user table owner: {owner}")
        
        # Test a simple SELECT to verify permissions
        result = self.run_command([
            "docker", "exec", self.db_container,
            "psql", "-U", self.db_user, "-d", self.db_name, "-t", "-c",
            "SELECT COUNT(*) FROM auth_user LIMIT 1;"
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Cannot query auth_user table: {result['stderr']}")
            self.report["recommendations"].append("Check table permissions and user access rights")
            return False
        
        print("✅ Table permissions are correct")
        return True

    def check_django_connection(self) -> bool:
        """Test Django database connection from CVAT container"""
        print("🔍 Testing Django database connection...")
        
        # Test Django shell connection
        result = self.run_command([
            "docker", "exec", self.cvat_container, "bash", "-c",
            'cd /home/django && python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute(\'SELECT 1\'); print(\'Django DB connection: OK\')"'
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Django database connection failed: {result['stderr']}")
            return False
        
        print("✅ Django database connection successful")
        return True

    def test_auth_user_query(self) -> bool:
        """Test the specific query that's failing"""
        print("🔍 Testing problematic auth_user query...")
        
        # Run the exact query from the error log
        query = '''SELECT "auth_user"."id", "auth_user"."password", "auth_user"."last_login", "auth_user"."is_superuser", "auth_user"."username", "auth_user"."first_name", "auth_user"."last_name", "auth_user"."email", "auth_user"."is_staff", "auth_user"."is_active", "auth_user"."date_joined" FROM "auth_user" ORDER BY "auth_user"."id" ASC LIMIT 1'''
        
        result = self.run_command([
            "docker", "exec", self.db_container,
            "psql", "-U", self.db_user, "-d", self.db_name, "-c", query
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Specific auth_user query failed: {result['stderr']}")
            return False
        
        print("✅ Problematic query executed successfully")
        return True

    def check_django_migrations(self) -> bool:
        """Check Django migration status"""
        print("🔍 Checking Django migrations...")
        
        result = self.run_command([
            "docker", "exec", self.cvat_container, "bash", "-c",
            "cd /home/django && python manage.py showmigrations --plan"
        ])
        
        if not result["success"]:
            self.report["issues"].append(f"Could not check Django migrations: {result['stderr']}")
            return False
        
        # Check for unapplied migrations
        if "[ ]" in result["stdout"]:
            self.report["issues"].append("Unapplied Django migrations found")
            self.report["recommendations"].append("Run 'python manage.py migrate' to apply pending migrations")
        
        print("✅ Django migrations check completed")
        return True

    def fix_auth_user_issues(self) -> bool:
        """Apply fixes for auth_user issues"""
        print("🔧 Applying fixes...")
        
        fixes_applied = []
        
        # Fix 1: Ensure Django migrations are up to date
        print("🔧 Running Django migrations...")
        result = self.run_command([
            "docker", "exec", self.cvat_container, "bash", "-c",
            "cd /home/django && python manage.py migrate"
        ])
        
        if result["success"]:
            fixes_applied.append("Django migrations updated")
        else:
            print(f"❌ Migration failed: {result['stderr']}")
        
        # Fix 2: Create superuser if none exists
        print("🔧 Ensuring superuser exists...")
        result = self.run_command([
            "docker", "exec", self.cvat_container, "bash", "-c",
            '''cd /home/django && python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@cvat.local', 'cvat123')
    print('Superuser created')
else:
    print('Superuser exists')
"'''
        ])
        
        if result["success"]:
            fixes_applied.append("Superuser verified/created")
        
        # Fix 3: Restart CVAT container to clear any cached connections
        print("🔧 Restarting CVAT container...")
        restart_result = self.run_command(["docker", "restart", self.cvat_container])
        
        if restart_result["success"]:
            fixes_applied.append("CVAT container restarted")
            print("⏳ Waiting for container to be ready...")
            import time
            time.sleep(10)
        
        self.report["fixes_applied"] = fixes_applied
        return len(fixes_applied) > 0

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report"""
        print("\n📊 Generating diagnostic report...")
        
        # Determine overall status
        if not self.report["issues"]:
            self.report["status"] = "healthy"
        elif len(self.report["issues"]) <= 2:
            self.report["status"] = "warning"
        else:
            self.report["status"] = "critical"
        
        return self.report

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run complete diagnostic workflow"""
        print("🏥 CVAT Database Diagnostic Tool Starting...\n")
        
        # Step 1: Check containers
        if not self.check_containers_running():
            self.report["status"] = "critical"
            return self.generate_report()
        
        # Step 2: Check database connection
        if not self.check_database_connection():
            self.report["status"] = "critical"
            return self.generate_report()
        
        # Step 3: Check auth_user table
        table_info = self.check_auth_user_table()
        if not table_info["exists"]:
            self.report["status"] = "critical"
            return self.generate_report()
        
        # Step 4: Check permissions
        self.check_table_permissions()
        
        # Step 5: Check Django connection
        self.check_django_connection()
        
        # Step 6: Test specific query
        self.test_auth_user_query()
        
        # Step 7: Check migrations
        self.check_django_migrations()
        
        return self.generate_report()

    def run_repair(self) -> Dict[str, Any]:
        """Run repair workflow"""
        print("🔧 CVAT Database Repair Tool Starting...\n")
        
        # Run diagnostic first
        self.run_full_diagnostic()
        
        # Apply fixes if issues found
        if self.report["issues"]:
            print(f"\n🔧 Found {len(self.report['issues'])} issues. Applying fixes...")
            self.fix_auth_user_issues()
            
            # Re-run diagnostic
            print("\n🔄 Re-running diagnostic after fixes...")
            self.report["issues"] = []  # Clear previous issues
            self.run_full_diagnostic()
        
        return self.generate_report()


def main():
    diagnostic = CVATDatabaseDiagnostic()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "--repair":
            report = diagnostic.run_repair()
        elif mode == "--check":
            report = diagnostic.run_full_diagnostic()
        else:
            print("Usage: cvat_diagnostic.py [--check|--repair]")
            sys.exit(1)
    else:
        report = diagnostic.run_full_diagnostic()
    
    # Print summary
    print("\n" + "="*60)
    print(f"🏥 DIAGNOSTIC SUMMARY - Status: {report['status'].upper()}")
    print("="*60)
    
    if report.get("issues"):
        print("❌ ISSUES FOUND:")
        for issue in report["issues"]:
            print(f"  • {issue}")
    
    if report.get("recommendations"):
        print("\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"  • {rec}")
    
    if report.get("fixes_applied"):
        print("\n🔧 FIXES APPLIED:")
        for fix in report["fixes_applied"]:
            print(f"  • {fix}")
    
    if not report["issues"]:
        print("✅ No issues found - CVAT database is healthy!")
    
    # Save detailed report
    report_file = f"/tmp/cvat_diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed report saved to: {report_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save report: {e}")
    
    # Exit with appropriate code
    sys.exit(0 if report["status"] in ["healthy", "warning"] else 1)


if __name__ == "__main__":
    main()