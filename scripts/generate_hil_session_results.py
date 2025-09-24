#!/usr/bin/env python3
"""
Generate consolidated HIL test session results.

Features:
- Runs ground-truth vs detection matching for a given session
- Computes TP/FP/FN, latency stats, and pass/fail against threshold
- Outputs JSON, CSV, and a lightweight HTML report
- Includes links to saved screenshots (if present on detection events)

Usage:
  python scripts/generate_hil_session_results.py --session-id <SESSION_ID> \
      [--tolerance-ms 100] [--latency-threshold-ms 100] [--out-dir hil-reports]

This script reuses backend services and models from ai-model-validation-platform/backend.
"""

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys


def _prepare_backend_env():
    """Add backend to sys.path and set a sane DB URL if not provided."""
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "ai-model-validation-platform" / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # If no DB URL is provided, try to select an existing local SQLite file
    if not os.getenv("VRU_DATABASE_URL") and not os.getenv("DATABASE_URL") and not os.getenv("AIVALIDATION_DATABASE_URL"):
        # Prefer dev_database.db in backend dir, else ai_model_validation.db, else app.db
        candidates = [
            backend_dir / "dev_database.db",
            backend_dir / "ai_model_validation.db",
            backend_dir / "app.db",
        ]
        for c in candidates:
            if c.exists():
                os.environ["VRU_DATABASE_URL"] = f"sqlite:///{c}"
                break


_prepare_backend_env()

# Backend imports (after preparing env and sys.path)
from database import SessionLocal
from models import (
    TestSession,
    DetectionEvent,
    GroundTruthObject,
    DetectionComparison,
    Video,
)
from services.ground_truth_matching_service import (
    get_session_matching_results,
    GroundTruthMatchingService,
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_if_exists(src: Optional[str], dst_dir: Path) -> Optional[str]:
    if not src:
        return None
    p = Path(src)
    if p.exists() and p.is_file():
        try:
            ensure_dir(dst_dir)
            target = dst_dir / p.name
            if str(p.resolve()) != str(target.resolve()):
                shutil.copy2(str(p), str(target))
            return str(target)
        except Exception:
            return str(p)
    return None


def generate_reports(
    session_id: str,
    tolerance_ms: int,
    latency_threshold_ms: int,
    out_dir: Path,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        # Validate session
        sess: Optional[TestSession] = (
            db.query(TestSession).filter(TestSession.id == session_id).first()
        )
        if not sess:
            raise SystemExit(f"Session not found: {session_id}")

        video: Optional[Video] = (
            db.query(Video).filter(Video.id == sess.video_id).first() if sess.video_id else None
        )

        # Run or reuse matching
        matcher = GroundTruthMatchingService(default_tolerance_ms=tolerance_ms)
        metrics = matcher.match_detections_to_ground_truth(
            session_id=session_id, tolerance_ms=tolerance_ms, force_rematch=False
        )

        # Load comparisons and detection events
        comparisons: List[DetectionComparison] = (
            db.query(DetectionComparison)
            .filter(DetectionComparison.test_session_id == session_id)
            .all()
        )
        det_events: List[DetectionEvent] = (
            db.query(DetectionEvent)
            .filter(DetectionEvent.test_session_id == session_id)
            .order_by(DetectionEvent.timestamp)
            .all()
        )
        det_by_id = {d.id: d for d in det_events}

        gt_by_id = {}
        if sess.video_id:
            gts: List[GroundTruthObject] = (
                db.query(GroundTruthObject)
                .filter(GroundTruthObject.video_id == sess.video_id)
                .order_by(GroundTruthObject.timestamp)
                .all()
            )
            gt_by_id = {g.id: g for g in gts}

        # Build event rows
        rows: List[Dict[str, Any]] = []
        screenshots_dir = out_dir / "screenshots"
        for comp in comparisons:
            det = det_by_id.get(comp.detection_event_id) if comp.detection_event_id else None
            gt = gt_by_id.get(comp.ground_truth_id) if comp.ground_truth_id else None

            latency_ms = None
            det_time = None
            gt_time = None
            if det is not None:
                det_time = float(det.video_relative_timestamp) if det.video_relative_timestamp is not None else float(det.timestamp)
            if gt is not None:
                gt_time = float(gt.timestamp)
            # Prefer comparison temporal_offset when provided
            if comp.temporal_offset is not None:
                latency_ms = float(comp.temporal_offset)
            elif det_time is not None and gt_time is not None:
                latency_ms = (det_time - gt_time) * 1000.0

            pass_latency = None
            if latency_ms is not None:
                pass_latency = (latency_ms >= 0) and (latency_ms <= latency_threshold_ms)

            # Copy screenshots next to report for portability
            screenshot_local = copy_if_exists(
                getattr(det, "screenshot_path", None) if det is not None else None, screenshots_dir
            )
            screenshot_zoom_local = copy_if_exists(
                getattr(det, "screenshot_zoom_path", None) if det is not None else None, screenshots_dir
            )

            rows.append(
                {
                    "match_type": comp.match_type,  # TP/FP/FN
                    "detection_event_id": comp.detection_event_id,
                    "ground_truth_id": comp.ground_truth_id,
                    "video_time": gt_time if gt_time is not None else (det_time if det_time is not None else None),
                    "detected_time": det_time,
                    "ground_truth_time": gt_time,
                    "latency_ms": latency_ms,
                    "pass_latency": pass_latency,
                    "iou_score": comp.iou_score,
                    "temporal_offset_ms": comp.temporal_offset,
                    "validation_result": getattr(det, "validation_result", None) if det is not None else None,
                    "video_frame_number": getattr(det, "video_frame_number", None) if det is not None else None,
                    "labjack_voltage": getattr(det, "labjack_voltage", None) if det is not None else None,
                    "detection_channel": getattr(det, "detection_channel", None) if det is not None else None,
                    "screenshot_path": screenshot_local,
                    "screenshot_zoom_path": screenshot_zoom_local,
                }
            )

        # Build summary
        tp = sum(1 for r in rows if r["match_type"] == "TP")
        fp = sum(1 for r in rows if r["match_type"] == "FP")
        fn = sum(1 for r in rows if r["match_type"] == "FN")

        latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None and r["match_type"] == "TP"]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            within_tol = sum(1 for l in latencies if l <= latency_threshold_ms)
            within_tol_pct = within_tol / len(latencies) * 100.0
        else:
            avg_latency = max_latency = min_latency = within_tol_pct = 0.0

        # Use service metrics when available
        metrics_dict: Dict[str, Any] = {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": getattr(metrics, "precision", 0.0) if metrics else 0.0,
            "recall": getattr(metrics, "recall", 0.0) if metrics else 0.0,
            "f1_score": getattr(metrics, "f1_score", 0.0) if metrics else 0.0,
            "mean_latency_ms": getattr(metrics, "mean_latency_ms", avg_latency) if metrics else avg_latency,
            "within_tolerance_percentage": getattr(metrics, "within_tolerance_percentage", within_tol_pct)
            if metrics
            else within_tol_pct,
        }

        report = {
            "session_id": session_id,
            "project_id": sess.project_id,
            "video": {
                "id": video.id if video else None,
                "filename": getattr(video, "filename", None) if video else None,
                "file_path": getattr(video, "file_path", None) if video else None,
                "fps": getattr(video, "fps", None) if video else None,
                "duration": getattr(video, "duration", None) if video else None,
            },
            "thresholds": {
                "tolerance_ms": tolerance_ms,
                "latency_threshold_ms": latency_threshold_ms,
            },
            "metrics": metrics_dict,
            "events": rows,
        }

        # Output files
        ensure_dir(out_dir)
        # JSON
        json_path = out_dir / "session_report.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)

        # CSV
        csv_path = out_dir / "session_report.csv"
        with open(csv_path, "w") as f:
            headers = [
                "match_type",
                "detection_event_id",
                "ground_truth_id",
                "video_time",
                "detected_time",
                "ground_truth_time",
                "latency_ms",
                "pass_latency",
                "iou_score",
                "temporal_offset_ms",
                "video_frame_number",
                "labjack_voltage",
                "detection_channel",
                "screenshot_path",
                "screenshot_zoom_path",
            ]
            f.write(",".join(headers) + "\n")
            for r in rows:
                vals = [r.get(h, "") for h in headers]
                # Simple CSV escaping
                vals = [str(v).replace("\n", " ").replace(",", ";") if v is not None else "" for v in vals]
                f.write(",".join(vals) + "\n")

        # HTML
        html_path = out_dir / "session_report.html"
        with open(html_path, "w") as f:
            f.write(_render_html(report))

        return {
            "json": str(json_path),
            "csv": str(csv_path),
            "html": str(html_path),
            "screenshots_dir": str(screenshots_dir),
        }
    finally:
        db.close()


def _render_html(report: Dict[str, Any]) -> str:
    s = report["session_id"]
    thresholds = report.get("thresholds", {})
    metrics = report.get("metrics", {})
    events = report.get("events", [])

    def img_tag(path: Optional[str]) -> str:
        if not path:
            return ""
        rel = Path(path).name
        return f'<div><img src="screenshots/{rel}" style="max-width: 420px; border-radius: 4px;"/></div>'

    # Split by type
    tps = [e for e in events if e.get("match_type") == "TP"]
    fps = [e for e in events if e.get("match_type") == "FP"]
    fns = [e for e in events if e.get("match_type") == "FN"]

    def render_event(e: Dict[str, Any]) -> str:
        color = {
            "TP": "#d5f4e6",
            "FP": "#fff4d6",
            "FN": "#fadbd8",
        }.get(e.get("match_type"), "#ecf0f1")
        border = {
            "TP": "#27ae60",
            "FP": "#f39c12",
            "FN": "#e74c3c",
        }.get(e.get("match_type"), "#95a5a6")
        pass_latency = e.get("pass_latency")
        pass_badge = (
            f'<span style="color:#fff;background:{'#27ae60' if pass_latency else '#e74c3c'};padding:2px 6px;border-radius:4px;">'
            + ("PASS" if pass_latency else "FAIL")
            + "</span>"
            if e.get("latency_ms") is not None and e.get("match_type") == "TP"
            else ""
        )
        img_html = img_tag(e.get("screenshot_path")) or img_tag(e.get("screenshot_zoom_path"))
        return f"""
        <div style=\"border-left: 6px solid {border}; background:{color}; padding:12px; margin:10px 0; border-radius:6px;\">
          <div style=\"display:flex; gap:16px; align-items:flex-start;\">
            <div style=\"flex:0 0 auto;\">{img_html}</div>
            <div style=\"flex:1;\">
              <div style=\"font-weight:bold;\">{e.get('match_type')} {pass_badge}</div>
              <div>Latency: {e.get('latency_ms') if e.get('latency_ms') is not None else 'N/A'} ms (threshold {thresholds.get('latency_threshold_ms')} ms)</div>
              <div>Video time: {e.get('detected_time') if e.get('detected_time') is not None else 'N/A'} s | GT time: {e.get('ground_truth_time') if e.get('ground_truth_time') is not None else 'N/A'} s</div>
              <div>Frame: {e.get('video_frame_number') or 'N/A'} | Channel: {e.get('detection_channel') or 'N/A'} | Voltage: {e.get('labjack_voltage') or 'N/A'}</div>
            </div>
          </div>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>HIL Session Report - {s}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 12px; }}
    .card {{ background:#ecf0f1; border-radius:8px; padding:14px; border-left:5px solid #3498db; }}
    .card.pass {{ background:#d5f4e6; border-left-color:#27ae60; }}
    .card.warn {{ background:#fff4d6; border-left-color:#f39c12; }}
    .card.fail {{ background:#fadbd8; border-left-color:#e74c3c; }}
    h2 {{ margin-top: 28px; }}
    img {{ max-height: 320px; object-fit: contain; }}
    .section {{ margin-top: 26px; }}
  </style>
  </head>
<body>
  <h1>HIL Session Report</h1>
  <div>Session: <strong>{s}</strong></div>
  <div>Tolerance: {thresholds.get('tolerance_ms')} ms | Latency threshold: {thresholds.get('latency_threshold_ms')} ms</div>

  <div class=\"grid\" style=\"margin-top:18px;\">
    <div class=\"card pass\"><div style=\"font-size:28px; font-weight:bold;\">{metrics.get('f1_score',0):.2f}</div>F1 Score</div>
    <div class=\"card\"><div style=\"font-size:28px; font-weight:bold;\">{metrics.get('precision',0):.2f}</div>Precision</div>
    <div class=\"card\"><div style=\"font-size:28px; font-weight:bold;\">{metrics.get('recall',0):.2f}</div>Recall</div>
    <div class=\"card\"><div style=\"font-size:28px; font-weight:bold;\">{metrics.get('mean_latency_ms',0):.1f} ms</div>Mean Latency</div>
    <div class=\"card\"><div style=\"font-size:28px; font-weight:bold;\">{metrics.get('within_tolerance_percentage',0):.1f}%</div>Within Tolerance</div>
    <div class=\"card\"><div style=\"font-size:28px; font-weight:bold;\">TP {len(tps)} | FP {len(fps)} | FN {len(fns)}</div>Counts</div>
  </div>

  <div class=\"section\">
    <h2>True Positives</h2>
    {''.join(render_event(e) for e in tps) if tps else '<div>No true positives.</div>'}
  </div>

  <div class=\"section\">
    <h2>False Positives</h2>
    {''.join(render_event(e) for e in fps) if fps else '<div>No false positives.</div>'}
  </div>

  <div class=\"section\">
    <h2>False Negatives (Missed GT)</h2>
    {''.join(render_event(e) for e in fns) if fns else '<div>No false negatives.</div>'}
  </div>

  <p style=\"color:#7f8c8d; margin-top: 28px;\">Screenshots shown when available from detection events. For missed GT, no screenshot is saved.</p>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HIL session results report")
    parser.add_argument("--session-id", required=True, help="Test session ID")
    parser.add_argument("--tolerance-ms", type=int, default=100, help="Matching tolerance in ms")
    parser.add_argument(
        "--latency-threshold-ms",
        type=int,
        default=100,
        help="Latency PASS threshold in ms for TP events",
    )
    parser.add_argument(
        "--out-dir",
        default="hil-reports",
        help="Output directory (base). A subfolder per session will be created",
    )

    args = parser.parse_args()
    base_out = Path(args.out_dir)
    out_dir = base_out / args.session_id

    results = generate_reports(
        session_id=args.session_id,
        tolerance_ms=args.tolerance_ms,
        latency_threshold_ms=args.latency_threshold_ms,
        out_dir=out_dir,
    )

    print("\nReport generated:")
    for k, v in results.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
