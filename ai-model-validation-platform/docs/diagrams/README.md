# AI Model Validation Platform - Architecture Diagrams

This folder contains PlantUML diagrams for the AI Model Validation Platform stakeholder presentation.

## How to View/Render Diagrams

### Option 1: PlantUML Online Server (Easiest)
1. Go to http://www.plantuml.com/plantuml/uml/
2. Copy and paste the content of any `.puml` file
3. Click "Submit" to see the diagram
4. Right-click to save as PNG/SVG

### Option 2: VS Code Extension
1. Install "PlantUML" extension in VS Code
2. Open any `.puml` file
3. Press `Alt+D` to preview
4. Right-click → Export to PNG/SVG

### Option 3: Command Line
```bash
# Install PlantUML
sudo apt-get install plantuml

# Render a single diagram
plantuml 01_overall_system_architecture.puml

# Render all diagrams
plantuml *.puml
```

### Option 4: PlantText (Online)
1. Go to https://www.planttext.com/
2. Paste the PlantUML code
3. Download as PNG/SVG

---

## Diagram Index

### For Non-Technical Stakeholders (Simple Overview)

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 14 | `14_component_overview_simple.puml` | **START HERE** - Simple system overview | Executives, Non-technical stakeholders |
| 17 | `17_user_journey.puml` | Complete user workflow | Product managers, Business analysts |
| 15 | `15_metrics_calculation.puml` | How test results are calculated | QA managers, Test leads |

### For Technical Overview

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 01 | `01_overall_system_architecture.puml` | Complete system architecture | Architects, Tech leads |
| 10 | `10_data_flow.puml` | How data flows through the system | Integration engineers |
| 16 | `16_deployment_architecture.puml` | Docker deployment structure | DevOps, Infrastructure |

### For Frontend Team

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 02 | `02_frontend_architecture.puml` | React component architecture | Frontend developers |
| 11 | `11_sequence_test_execution.puml` | Test execution sequence | Frontend developers |

### For Backend Team

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 03 | `03_backend_architecture.puml` | FastAPI service architecture | Backend developers |
| 09 | `09_api_structure.puml` | API endpoint overview | API developers |
| 12 | `12_sequence_labjack_detection.puml` | LabJack detection sequence | Hardware integration team |

### For Database/Data Team

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 04 | `04_database_schema_simplified.puml` | Simplified DB schema | Business analysts, QA |
| 05 | `05_database_schema_detailed.puml` | Complete DB schema | DBAs, Backend developers |

### For Testing/QA Team

| # | Diagram | Purpose | Best For |
|---|---------|---------|----------|
| 06 | `06_hil_test_workflow.puml` | HIL test workflow | Test engineers, QA |
| 07 | `07_labjack_detection_flow.puml` | Detection pipeline logic | Test engineers |
| 08 | `08_ground_truth_correlation_algorithm.puml` | Correlation algorithm details | Algorithm specialists |
| 13 | `13_timing_synchronization.puml` | Timing synchronization model | Precision timing experts |

---

## Recommended Presentation Order

### Executive Summary (5 minutes)
1. **14_component_overview_simple** - What the system does
2. **17_user_journey** - How users interact with it
3. **15_metrics_calculation** - What results look like

### Technical Deep Dive (15-20 minutes)
1. **01_overall_system_architecture** - Full architecture
2. **10_data_flow** - Data movement
3. **06_hil_test_workflow** - Test process
4. **08_ground_truth_correlation_algorithm** - Core algorithm

### Developer Onboarding (30 minutes)
1. All diagrams in numerical order
2. Use detailed database schema (05)
3. Focus on sequence diagrams (11, 12, 13)

---

## Diagram Descriptions

### 01. Overall System Architecture
Shows all major system components: Frontend (React), Backend (FastAPI), Database, Hardware (LabJack), and ML Engine (YOLO). Illustrates how they connect and communicate.

### 02. Frontend Architecture
React application structure showing pages, components, services, hooks, and state management. Highlights video players, detection panels, and timeline components.

### 03. Backend Architecture
FastAPI application structure with routers, services, and data access layer. Shows Ground Truth, LabJack, Timing, and Report services.

### 04. Database Schema (Simplified)
Core tables for stakeholder understanding: Project, Video, TestSession, DetectionEvent, GroundTruthObject, TestResult.

### 05. Database Schema (Detailed)
Complete entity relationships with all columns, foreign keys, and indexes. For technical reference.

### 06. HIL Test Workflow
Complete Hardware-in-the-Loop test process from setup to results. Shows decision points and parallel operations.

### 07. LabJack Detection Flow
Detailed detection pipeline: voltage streaming, threshold checking, debounce filtering, event creation, batch commits.

### 08. Ground Truth Correlation Algorithm
Algorithm selection logic (Hungarian vs Many-to-One vs Greedy), matching process, and classification (TP/FP/FN).

### 09. API Structure
All REST endpoints organized by domain: Auth, Projects, Videos, Test Sessions, HIL, Reports, Dashboard.

### 10. Data Flow
How data moves through the system from user input through hardware to database and reports.

### 11. Test Execution Sequence
Sequence diagram showing interaction between Frontend, Backend, LabJack Monitor, and Database during a test.

### 12. LabJack Detection Sequence
Detailed sequence for hardware monitoring: initialization, detection loop, session management.

### 13. Timing Synchronization
How video timing and hardware timing are synchronized, including drift compensation.

### 14. Component Overview (Simple)
Simplified view for non-technical stakeholders showing main system capabilities.

### 15. Metrics Calculation
How accuracy (Precision, Recall, F1) and latency metrics are calculated from test data.

### 16. Deployment Architecture
Docker container setup with vru_frontend, vru_backend, vru_redis, and database.

### 17. User Journey
Complete workflow from login through test execution to report generation.

---

## Key Concepts Explained

### True Positive (TP)
A detection event that correctly matches a ground truth object within the tolerance window.

### False Positive (FP)
A detection event without a matching ground truth object (system detected something that wasn't there).

### False Negative (FN)
A ground truth object without a matching detection event (system missed a detection).

### Latency
Time difference between ground truth timestamp and detection timestamp. Lower is better.

### Many-to-One Matching
Algorithm used when detection rate is lower than ground truth rate (constant voltage scenarios). One detection can cover multiple ground truth frames.

### Hungarian Algorithm
Optimal matching algorithm that minimizes total cost (latency) across all matches. Used for standard test scenarios.

---

## Questions?

Contact the development team for clarification on any diagram or concept.
