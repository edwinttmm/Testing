import os
import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import base64
from jinja2 import Template

class TestReportGenerator:
    """
    PRD Module 4.2 - Test Report Generator
    
    Generates comprehensive test reports in multiple formats:
    - HTML reports with embedded failure snapshots
    - PDF reports (via HTML to PDF conversion)
    - JSON reports for API consumption
    
    PRD Requirements:
    - Top-level summary of pass/fail rates and average latency
    - Failure snapshots for every HIGH_LATENCY and MISSED_DETECTION
    - Success summaries in text format
    """
    
    def __init__(self):
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)
        self.create_default_templates()
    
    def create_default_templates(self):
        """Create default HTML template for reports"""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADAS HIL Test Report - {{ test_session.name }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #2c3e50;
            margin: 0;
            font-size: 2.5em;
        }
        .header .subtitle {
            color: #7f8c8d;
            font-size: 1.2em;
            margin: 10px 0;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric-card {
            background: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 5px solid #3498db;
        }
        .metric-card.pass {
            border-left-color: #27ae60;
            background: #d5f4e6;
        }
        .metric-card.fail {
            border-left-color: #e74c3c;
            background: #fadbd8;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        .success-summary {
            background: #d5f4e6;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid #27ae60;
            margin: 30px 0;
        }
        .success-summary h3 {
            color: #27ae60;
            margin-top: 0;
        }
        .failures-section {
            margin: 30px 0;
        }
        .failure-event {
            background: #fadbd8;
            border: 1px solid #e74c3c;
            border-radius: 8px;
            margin: 20px 0;
            overflow: hidden;
        }
        .failure-header {
            background: #e74c3c;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
        }
        .failure-content {
            padding: 20px;
        }
        .failure-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .detail-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .detail-label {
            font-weight: bold;
            color: #2c3e50;
        }
        .failure-snapshot {
            text-align: center;
            margin: 20px 0;
        }
        .failure-snapshot img {
            max-width: 100%;
            border: 2px solid #e74c3c;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .latency-distribution {
            margin: 30px 0;
        }
        .distribution-bar {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }
        .bar-label {
            width: 100px;
            font-weight: bold;
        }
        .bar-visual {
            flex: 1;
            background: #ecf0f1;
            height: 25px;
            border-radius: 12px;
            overflow: hidden;
            margin: 0 10px;
        }
        .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #f39c12, #e74c3c);
            border-radius: 12px;
        }
        .bar-count {
            width: 60px;
            text-align: center;
            font-weight: bold;
        }
        .test-outcome {
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            font-size: 1.5em;
            font-weight: bold;
            margin: 30px 0;
        }
        .test-outcome.pass {
            background: #27ae60;
            color: white;
        }
        .test-outcome.fail {
            background: #e74c3c;
            color: white;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
        }
        @media print {
            body { background-color: white; }
            .container { box-shadow: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ADAS HIL Test Report</h1>
            <div class="subtitle">{{ test_session.name }}</div>
            <div class="subtitle">Project: {{ test_session.project_name }}</div>
            <div class="subtitle">Generated: {{ generated_at }}</div>
        </div>

        <!-- Test Outcome -->
        <div class="test-outcome {{ 'pass' if metrics.test_outcome == 'PASS' else 'fail' }}">
            TEST {{ metrics.test_outcome }}
        </div>

        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card pass">
                <div class="metric-value">{{ "%.1f"|format(metrics.pass_rate_percent) }}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ metrics.average_latency_ms }}ms</div>
                <div class="metric-label">Average Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ metrics.total_events }}</div>
                <div class="metric-label">Total Events</div>
            </div>
            <div class="metric-card pass">
                <div class="metric-value">{{ metrics.passed_events }}</div>
                <div class="metric-label">Passed Events</div>
            </div>
            <div class="metric-card fail">
                <div class="metric-value">{{ metrics.failed_events }}</div>
                <div class="metric-label">Failed Events</div>
            </div>
            <div class="metric-card fail">
                <div class="metric-value">{{ metrics.missed_detections }}</div>
                <div class="metric-label">Missed Detections</div>
            </div>
        </div>

        <!-- Success Summary -->
        {% if success_summary.passed_count > 0 %}
        <div class="success-summary">
            <h3>✅ Success Summary</h3>
            <p>{{ success_summary.summary_text }}</p>
            {% if success_summary.vru_breakdown %}
            <p><strong>VRU Breakdown:</strong> 
                {% for vru_type, count in success_summary.vru_breakdown.items() %}
                    {{ count }} {{ vru_type }}{{ "," if not loop.last }}
                {% endfor %}
            </p>
            {% endif %}
        </div>
        {% endif %}

        <!-- Latency Distribution -->
        {% if metrics.latency_distribution %}
        <div class="latency-distribution">
            <h3>Latency Distribution</h3>
            {% set max_count = metrics.latency_distribution.values() | max %}
            {% for bin_label, count in metrics.latency_distribution.items() %}
            <div class="distribution-bar">
                <div class="bar-label">{{ bin_label }}</div>
                <div class="bar-visual">
                    <div class="bar-fill" style="width: {{ (count / max_count * 100) if max_count > 0 else 0 }}%"></div>
                </div>
                <div class="bar-count">{{ count }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Failure Events -->
        {% if failure_events %}
        <div class="failures-section">
            <h2>❌ Failure Analysis</h2>
            <p>The following events failed to meet the latency threshold of {{ metrics.latency_threshold_ms }}ms:</p>
            
            {% for failure in failure_events %}
            <div class="failure-event">
                <div class="failure-header">
                    {{ failure.failure_type.replace('_', ' ').title() }} - Event {{ loop.index }}
                </div>
                <div class="failure-content">
                    <div class="failure-details">
                        <div class="detail-item">
                            <span class="detail-label">Timestamp:</span>
                            <span>{{ "%.3f"|format(failure.timestamp) }}s</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">VRU Type:</span>
                            <span>{{ failure.vru_type or 'Unknown' }}</span>
                        </div>
                        {% if failure.latency_ms %}
                        <div class="detail-item">
                            <span class="detail-label">Actual Latency:</span>
                            <span>{{ failure.latency_ms }}ms</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Threshold:</span>
                            <span>{{ failure.threshold_ms }}ms</span>
                        </div>
                        {% endif %}
                        <div class="detail-item">
                            <span class="detail-label">Frame Number:</span>
                            <span>{{ failure.frame_number or 'N/A' }}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Detection Channel:</span>
                            <span>{{ failure.detection_channel or 'N/A' }}</span>
                        </div>
                    </div>
                    
                    <!-- Failure Snapshot -->
                    {% set snapshot = failure_snapshots | selectattr('event_id', 'equalto', failure.event_id) | first %}
                    {% if snapshot and snapshot.snapshot_base64 %}
                    <div class="failure-snapshot">
                        <h4>Failure Snapshot</h4>
                        <p><strong>Video:</strong> {{ snapshot.video_filename }} | 
                           <strong>Frame:</strong> {{ snapshot.frame_number }} | 
                           <strong>Timestamp:</strong> {{ "%.3f"|format(snapshot.timestamp_ms / 1000) }}s</p>
                        <img src="{{ snapshot.snapshot_base64 }}" alt="Failure snapshot at {{ snapshot.timestamp_ms }}ms" />
                    </div>
                    {% elif snapshot and snapshot.error %}
                    <div class="failure-snapshot">
                        <p style="color: #e74c3c;"><strong>Snapshot Error:</strong> {{ snapshot.error }}</p>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Test Session Details -->
        <div style="margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px;">
            <h3>Test Session Details</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div class="detail-item">
                    <span class="detail-label">Session ID:</span>
                    <span>{{ test_session.id }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Started:</span>
                    <span>{{ test_session.started_at or 'N/A' }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Completed:</span>
                    <span>{{ test_session.completed_at or 'N/A' }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Status:</span>
                    <span>{{ test_session.status }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Videos Tested:</span>
                    <span>{{ videos_tested }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Latency Threshold:</span>
                    <span>{{ test_session.latency_threshold_ms }}ms</span>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>ADAS Camera Hardware-in-the-Loop Testing Platform</p>
            <p>Report ID: {{ report_id }}</p>
        </div>
    </div>
</body>
</html>
        """
        
        template_path = self.templates_dir / "test_report.html"
        with open(template_path, 'w') as f:
            f.write(html_template.strip())
    
    async def generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate HTML report with embedded failure snapshots
        
        PRD Requirement: Include video snapshot for every failure
        """
        try:
            template_path = self.templates_dir / "test_report.html"
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            template = Template(template_content)
            html_content = template.render(**report_data)
            
            return html_content
        
        except Exception as e:
            print(f"Error generating HTML report: {str(e)}")
            return self._generate_error_html(str(e))
    
    async def generate_pdf_report(self, report_data: Dict[str, Any]) -> bytes:
        """
        Generate PDF report from HTML content
        
        Note: This would typically use a library like WeasyPrint or Playwright
        For now, returns HTML content as bytes with PDF headers
        """
        try:
            # Generate HTML first
            html_content = await self.generate_html_report(report_data)
            
            # In a production environment, you would use a proper HTML-to-PDF converter
            # For example, using WeasyPrint:
            # from weasyprint import HTML, CSS
            # pdf_bytes = HTML(string=html_content).write_pdf()
            
            # For now, return HTML as bytes (browsers can print to PDF)
            return html_content.encode('utf-8')
        
        except Exception as e:
            print(f"Error generating PDF report: {str(e)}")
            error_html = self._generate_error_html(str(e))
            return error_html.encode('utf-8')
    
    def generate_json_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate JSON report for API consumption
        """
        try:
            # Clean up data for JSON serialization
            json_data = self._prepare_json_data(report_data)
            return json.dumps(json_data, indent=2, default=str)
        
        except Exception as e:
            print(f"Error generating JSON report: {str(e)}")
            return json.dumps({
                "error": f"Failed to generate JSON report: {str(e)}",
                "report_id": report_data.get("report_id", "unknown")
            })
    
    def _prepare_json_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare report data for JSON serialization
        Remove base64 image data to keep JSON manageable
        """
        json_data = report_data.copy()
        
        # Remove base64 snapshot data from JSON (too large)
        if "failure_snapshots" in json_data:
            for snapshot in json_data["failure_snapshots"]:
                if "snapshot_base64" in snapshot:
                    snapshot["snapshot_base64"] = "[Base64 data removed for JSON export]"
        
        return json_data
    
    def generate_csv_summary(self, report_data: Dict[str, Any]) -> str:
        """
        Generate CSV summary of test results
        """
        try:
            csv_lines = []
            csv_lines.append("Metric,Value,Unit")
            
            metrics = report_data.get("metrics", {})
            csv_lines.append(f"Total Events,{metrics.get('total_events', 0)},count")
            csv_lines.append(f"Passed Events,{metrics.get('passed_events', 0)},count")
            csv_lines.append(f"Failed Events,{metrics.get('failed_events', 0)},count")
            csv_lines.append(f"Pass Rate,{metrics.get('pass_rate_percent', 0)},percent")
            csv_lines.append(f"Average Latency,{metrics.get('average_latency_ms', 0)},milliseconds")
            csv_lines.append(f"Max Latency,{metrics.get('max_latency_ms', 0)},milliseconds")
            csv_lines.append(f"Min Latency,{metrics.get('min_latency_ms', 0)},milliseconds")
            csv_lines.append(f"High Latency Failures,{metrics.get('high_latency_failures', 0)},count")
            csv_lines.append(f"Missed Detections,{metrics.get('missed_detections', 0)},count")
            csv_lines.append(f"Test Outcome,{metrics.get('test_outcome', 'UNKNOWN')},status")
            
            return "\n".join(csv_lines)
        
        except Exception as e:
            print(f"Error generating CSV summary: {str(e)}")
            return f"Error,{str(e)},error"
    
    def _generate_error_html(self, error_message: str) -> str:
        """
        Generate error HTML when report generation fails
        """
        error_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Report Generation Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .error {{ color: #e74c3c; background: #fadbd8; padding: 20px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="error">
        <h2>Report Generation Failed</h2>
        <p>{error_message}</p>
        <p>Please check the system logs and try again.</p>
    </div>
</body>
</html>
        """
        return error_html.strip()
    
    def get_available_templates(self) -> List[str]:
        """
        Get list of available report templates
        """
        try:
            templates = []
            for template_file in self.templates_dir.glob("*.html"):
                templates.append(template_file.stem)
            return templates
        except Exception as e:
            print(f"Error listing templates: {str(e)}")
            return []
    
    def customize_template(self, template_name: str, custom_css: str = None, custom_header: str = None):
        """
        Allow customization of report templates
        """
        # This would allow users to customize report appearance
        # For now, just log the request
        print(f"Template customization requested for: {template_name}")
        if custom_css:
            print(f"Custom CSS provided: {len(custom_css)} characters")
        if custom_header:
            print(f"Custom header provided: {custom_header}")