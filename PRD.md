Product Requirements Document: ADAS Camera Hardware-in-the-Loop (HIL) Testing Platform
Version: 1.0

Date: August 29, 2025

Author: Gemini

Status: Draft

1. Introduction
The current process for validating ADAS AI camera performance relies on manual, frame-by-frame review of driving footage. This method is exceptionally time-consuming, prone to human error, lacks repeatability, and is not scalable.

This document outlines the requirements for an automated, hardware-in-the-loop (HIL) testing platform designed to solve this problem. The system will leverage a library of real-world driving data to provide a controlled, repeatable, and data-driven environment for rigorously testing camera detection accuracy and latency.

2. Goals & Objectives
Efficiency: Reduce the time required for a complete test cycle by at least 90% compared to manual methods.

Accuracy: Establish a pixel-perfect, validated "ground truth" for every test scenario to eliminate ambiguity in test results.

Repeatability: Ensure that any test can be re-run under identical conditions to reliably benchmark performance improvements or regressions.

Insight: Provide clear, actionable reports that allow engineers to quickly identify and analyze failures (missed detections, high latency).

3. User Personas
ADAS Test Engineer: Responsible for configuring tests, executing them on physical hardware, and analyzing the performance reports. Their primary need is for a simple, reliable, and fast testing workflow.

Data Annotation Specialist: Responsible for ensuring the quality and accuracy of the ground truth data. Their primary need is for an efficient and precise interface to review and correct AI-generated annotations.

4. Features & Requirements
The platform is divided into four core modules that represent the end-to-end user workflow.

Module 1: Data Management & Ground Truth Preparation
This module focuses on ingesting raw video data and preparing it for testing.

1.1. Video Ingestion

Description: Users can upload raw driving footage into the system.

Requirements:

Users must be able to upload standard video file formats (e.g., .MP4, .MOV, .AVI).

The system shall process uploaded videos and add them to a central library with a "Pending Annotation" status.

1.2. Automated Annotation

Description: The system uses an AI model to perform an initial annotation pass on uploaded videos.

Requirements:

The system must automatically identify and draw bounding boxes around all detected Vulnerable Road Users (VRUs).

Each unique VRU must be assigned a persistent ID that tracks it throughout the video.

Videos that have been processed shall be moved to a "Pending Validation" status.

1.3. Annotation Validation & Editing Interface

Description: An intuitive, all-in-one interface for users to manually review, edit, and perfect the AI-generated annotations to create the "ground truth."

Requirements:

UI Layout: The interface must feature a large central video viewport, an interactive timeline below it, and panels for tools and a list of all detected objects.

Direct Manipulation: Users must be able to directly click, resize, and move bounding boxes in the main viewport.

Object Management: Users must be able to correct mislabeled objects (e.g., change "pedestrian" to "cyclist"), create new annotations for missed detections, and delete false positives.

ID Management: Users must be able to merge multiple object IDs that refer to the same VRU or split a single ID that incorrectly tracks multiple VRUs.

Timeline Control: The timeline must display markers for each annotation event, and users must be able to scrub through the video frame-by-frame for precise editing.

Validation: Once satisfied, the user must be able to mark the video's annotations as "Validated," locking them and making the video available for testing projects.

1.4. Video Library

Description: A central repository for all processed videos.

Requirements:

Users must be able to view a list of all videos and their current status (e.g., Pending Validation, Validated).

Users must be able to filter and search the library by filename or status.

From the library, users must be able to open a video to view its playback with annotations overlaid and examine snapshots of key detection events.

Module 2: Test Configuration
2.1. Project-Based Workflow

Description: A system for grouping validated videos into specific test suites.

Requirements:

Users must be able to create, name, and delete "Projects" (e.g., "Front-Facing Camera v2.1 Regression Test").

Users must be able to add or remove any number of "Validated" videos from a project.

Module 3: Test Execution
3.1. HIL Test Environment

Description: The main interface for executing a hardware test run.

Requirements:

The user must select a Project to load the corresponding playlist of videos.

The interface must clearly indicate the connection status of the LabJack DAQ device (e.g., "Connected" or "Not Detected"). The test cannot start if the connection is not active.

Before starting, the user must be prompted to enter a maximum acceptable latency value in milliseconds (ms).

Upon starting the test, the system must immediately switch the first video in the playlist to a full-screen display.

3.2. Precision Time & Signal Logging

Description: The core logic for capturing and comparing ground truth and hardware events.

Requirements:

The system must capture a high-precision Test_Start_Time at the exact moment the video playback begins. This is the "Time 0" reference.

The system must calculate the Expected_Event_Time for every annotated event in the video, relative to Test_Start_Time.

The system must continuously monitor the LabJack input and log a high-precision Signal_Received_Time the instant a high signal (detection) is received from the camera.

Module 4: Analysis & Reporting
4.1. Automated Performance Analysis

Description: The system automatically compares the ground truth log with the hardware signal log to determine the outcome of each event.

Requirements:

Pass: A hardware signal is received, and the calculated latency (Signal_Received_Time - Expected_Event_Time) is within the user-defined threshold.

Fail (High Latency): A signal is received, but the latency is greater than the threshold.

Fail (Missed Detection): No signal is received within a reasonable window of an expected event.

4.2. Report Generation

Description: The system generates a clear, concise report summarizing the test results.

Requirements:

The report must provide a top-level summary of pass/fail rates and average latency.

Crucially, the report must include a video snapshot for every single failure (both High Latency and Missed Detection), timestamped to the moment the event occurred.

The report must summarize all successful passes in a simple text format (e.g., "217/230 detections passed"), without requiring visual review of passed events.

5. Technical & Non-Functional Requirements
Timing Precision: All timestamp logging must have sub-millisecond precision. A monotonic clock should be used to prevent issues from system time changes.

Hardware Integration: The system must interface with a LabJack DAQ device to read a digital high/low (TTL) signal.

Performance: Video playback must be smooth and free of dropped frames to ensure timing integrity.

Data Storage: A robust solution is required for storing large video files and associated annotation metadata (e.g., local network-attached storage, cloud storage).

6. Out of Scope (for Version 1.0)
Support for DAQ devices other than LabJack.

Real-time cloud-based testing and analysis.

Advanced scenario generation or video manipulation.

Support for annotation types other than bounding boxes (e.g., semantic segmentation, polygons).
