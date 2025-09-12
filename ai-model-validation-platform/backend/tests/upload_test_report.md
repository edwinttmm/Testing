# Video Upload Workflow Testing Report\nGenerated: 2025-08-29T14:58:55.678863\nTotal Duration: 19.04s\n\n## Executive Summary\n- **Total Test Suites**: 6\n- **Successful**: 0\n- **Failed**: 6\n- **Success Rate**: 0.0%\n\n## Detailed Results\n### ❌ health_check\n- **File**: `N/A`\n- **Duration**: 0.00s\n- **Status**: FAIL\n\n**Error Details:**\n```\nINFO:health_check:🏥 Starting comprehensive unified health check...
INFO:src.config.service_discovery:🔍 Discovering service: postgres (database)
INFO:src.config.service_discovery:🔍 Discovering service: redis (redis)
INFO:src.config.service_discovery:🔍 Discovering service: postgres (database)
INFO:src.config.service_discovery:🔍 Discovering service: postgres (database)
INFO:src.config.service_discovery:✅ Service redis discovered: redis://127.0.0.1:6379 (status: unavailable)
INFO:src.config.service_discovery:✅ Service postgres discovered: postgresql://127.0.0.1:5432 (status: unavailable)
INFO:src.config.service_discovery:✅ Service postgres discovered: postgresql://127.0.0.1:5432 (status: unavailable)
INFO:src.config.service_discovery:✅ Service postgres discovered: postgresql://127.0.0.1:5432 (status: unavailable)
INFO:health_check:✅ Health check completed: unhealthy (3/8 healthy)
Traceback (most recent call last):
  File "<string>", line 14, in <module>
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "<string>", line 10, in main
KeyError: 'components'
\n```\n\n### ❌ endpoint_availability\n- **File**: `N/A`\n- **Duration**: 0.00s\n- **Status**: FAIL\n\n**Error Details:**\n```\n\n```\n\n### ❌ manual_upload\n- **File**: `N/A`\n- **Duration**: 0.00s\n- **Status**: FAIL\n\n**Error Details:**\n```\n\n```\n\n### ❌ Comprehensive Upload Functionality Tests\n- **File**: `test_video_upload_comprehensive.py`\n- **Duration**: 0.05s\n- **Status**: FAIL\n\n**Error Details:**\n```\n/usr/bin/python3: No module named pytest
\n```\n\n### ❌ Upload Error Handling and Recovery Tests\n- **File**: `test_upload_error_handling.py`\n- **Duration**: 0.05s\n- **Status**: FAIL\n\n**Error Details:**\n```\n/usr/bin/python3: No module named pytest
\n```\n\n### ❌ Upload Performance and Load Tests\n- **File**: `test_upload_performance.py`\n- **Duration**: 0.05s\n- **Status**: FAIL\n\n**Error Details:**\n```\n/usr/bin/python3: No module named pytest
\n```\n\n## Recommendations\n\n### Failed Tests\n- Review failed test outputs above\n- Check backend service availability\n- Verify database connectivity\n- Ensure all dependencies are installed\n\n### Upload System Status: NEEDS ATTENTION\n- Multiple test failures detected\n- Review system configuration\n- Check service dependencies\n- Consider system debugging before production deployment\n