"""
Match Validation Utilities

Provides validation functions to ensure ground truth matching integrity:
- No duplicate detection matches
- No duplicate ground truth matches
- One-to-one matching constraints
- Cross-video boundary validation
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of match validation"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    statistics: Dict[str, any]


def validate_matches(
    matches: List[any],
    strict: bool = True
) -> ValidationResult:
    """
    Verify no detection or ground truth matched multiple times.

    This is the CRITICAL validation function that ensures the matching
    algorithm produces one-to-one matches without duplicates.

    Args:
        matches: List of MatchResult objects or DetectionComparison records
        strict: If True, raise exception on validation failure

    Returns:
        ValidationResult with errors if any violations found

    Raises:
        AssertionError: If strict=True and violations found
    """
    errors = []
    warnings = []
    statistics = {}

    # Extract IDs from matches
    detection_ids = []
    gt_ids = []

    for match in matches:
        if hasattr(match, 'detection_event_id'):
            det_id = match.detection_event_id
        elif hasattr(match, 'detection_id'):
            det_id = match.detection_id
        else:
            det_id = None

        if hasattr(match, 'ground_truth_id'):
            gt_id = match.ground_truth_id
        else:
            gt_id = None

        # Only include non-None IDs
        if det_id is not None:
            detection_ids.append(det_id)
        if gt_id is not None:
            gt_ids.append(gt_id)

    # Check for duplicate detection matches
    duplicate_detections = _find_duplicates(detection_ids)
    if duplicate_detections:
        error_msg = (
            f"CRITICAL: {len(duplicate_detections)} detection(s) matched multiple times! "
            f"This indicates the double-matching bug is NOT fixed. "
            f"Duplicate IDs: {list(duplicate_detections)[:5]}"
        )
        errors.append(error_msg)
        logger.error(error_msg)

    # Check for duplicate ground truth matches
    duplicate_gts = _find_duplicates(gt_ids)
    if duplicate_gts:
        error_msg = (
            f"CRITICAL: {len(duplicate_gts)} ground truth object(s) matched multiple times! "
            f"This indicates a matching algorithm bug. "
            f"Duplicate IDs: {list(duplicate_gts)[:5]}"
        )
        errors.append(error_msg)
        logger.error(error_msg)

    # Statistics
    statistics = {
        'total_matches': len(matches),
        'unique_detections': len(set(detection_ids)),
        'unique_ground_truths': len(set(gt_ids)),
        'detection_duplicates': len(duplicate_detections),
        'gt_duplicates': len(duplicate_gts),
        'detection_match_count': len(detection_ids),
        'gt_match_count': len(gt_ids)
    }

    # Log statistics
    logger.info(
        f"Match validation statistics: "
        f"{statistics['total_matches']} total matches, "
        f"{statistics['unique_detections']} unique detections, "
        f"{statistics['unique_ground_truths']} unique GTs"
    )

    if errors:
        logger.error(f"Validation FAILED with {len(errors)} error(s)")
    else:
        logger.info("✅ Validation PASSED: No duplicate matches found")

    # Create result
    result = ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        statistics=statistics
    )

    # Strict mode assertions
    if strict and not result.valid:
        error_summary = "\n".join(errors)
        raise AssertionError(
            f"Match validation failed:\n{error_summary}\n"
            f"Statistics: {statistics}"
        )

    return result


def validate_video_boundary_protection(
    matches: List[any],
    multi_video_session: bool = True
) -> ValidationResult:
    """
    Verify no cross-video matches in multi-video sequences.

    Args:
        matches: List of MatchResult objects
        multi_video_session: Whether this is a multi-video sequence

    Returns:
        ValidationResult with cross-video violation errors
    """
    errors = []
    warnings = []
    statistics = {}

    if not multi_video_session:
        logger.debug("Single video session - skipping video boundary validation")
        return ValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            statistics={'session_type': 'single_video'}
        )

    cross_video_violations = []

    for match in matches:
        # Extract video IDs
        det_video_id = getattr(match, 'detection_video_id', None)
        gt_video_id = getattr(match, 'ground_truth_video_id', None)

        # Check if both video IDs exist and differ
        if det_video_id and gt_video_id and det_video_id != gt_video_id:
            cross_video_violations.append({
                'detection_video': det_video_id,
                'gt_video': gt_video_id,
                'match_type': getattr(match, 'match_type', 'unknown')
            })

    if cross_video_violations:
        error_msg = (
            f"CRITICAL: {len(cross_video_violations)} cross-video match(es) detected! "
            f"This indicates video boundary protection is NOT working. "
            f"Violations: {cross_video_violations[:3]}"
        )
        errors.append(error_msg)
        logger.error(error_msg)

    statistics = {
        'multi_video_session': multi_video_session,
        'cross_video_violations': len(cross_video_violations),
        'total_matches_checked': len(matches)
    }

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        statistics=statistics
    )


def validate_temporal_consistency(
    matches: List[any],
    tolerance_ms: float
) -> ValidationResult:
    """
    Verify all matches are within temporal tolerance.

    Args:
        matches: List of MatchResult objects
        tolerance_ms: Maximum allowed temporal offset in milliseconds

    Returns:
        ValidationResult with temporal violation errors
    """
    errors = []
    warnings = []
    out_of_tolerance = []

    for match in matches:
        match_type = getattr(match, 'match_type', None)

        # Only check TP matches
        if match_type != 'TP':
            continue

        # Get temporal offset
        temporal_offset = getattr(match, 'temporal_offset', None)
        if temporal_offset is None:
            temporal_offset = getattr(match, 'latency_ms', None)

        if temporal_offset is None:
            warnings.append(f"Match missing temporal_offset/latency_ms field")
            continue

        # Check tolerance
        if abs(temporal_offset) > tolerance_ms:
            out_of_tolerance.append({
                'offset_ms': temporal_offset,
                'tolerance_ms': tolerance_ms,
                'detection_id': getattr(match, 'detection_event_id', None),
                'gt_id': getattr(match, 'ground_truth_id', None)
            })

    if out_of_tolerance:
        error_msg = (
            f"WARNING: {len(out_of_tolerance)} match(es) exceed tolerance of {tolerance_ms}ms. "
            f"This may indicate timing calculation errors. "
            f"Examples: {out_of_tolerance[:3]}"
        )
        warnings.append(error_msg)
        logger.warning(error_msg)

    statistics = {
        'total_tp_matches': sum(1 for m in matches if getattr(m, 'match_type', None) == 'TP'),
        'out_of_tolerance_count': len(out_of_tolerance),
        'tolerance_ms': tolerance_ms
    }

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        statistics=statistics
    )


def _find_duplicates(items: List[any]) -> Set[any]:
    """
    Find duplicate items in a list.

    Args:
        items: List of items to check

    Returns:
        Set of items that appear more than once
    """
    seen = set()
    duplicates = set()

    for item in items:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)

    return duplicates


def generate_validation_report(
    validation_results: List[ValidationResult]
) -> str:
    """
    Generate a human-readable validation report.

    Args:
        validation_results: List of ValidationResult objects

    Returns:
        Formatted report string
    """
    report_lines = [
        "=" * 80,
        "GROUND TRUTH MATCHING VALIDATION REPORT",
        "=" * 80,
        ""
    ]

    total_errors = sum(len(vr.errors) for vr in validation_results)
    total_warnings = sum(len(vr.warnings) for vr in validation_results)

    # Summary
    if total_errors == 0 and total_warnings == 0:
        report_lines.append("✅ ALL VALIDATIONS PASSED")
    elif total_errors == 0:
        report_lines.append(f"⚠️  PASSED WITH {total_warnings} WARNING(S)")
    else:
        report_lines.append(f"❌ FAILED WITH {total_errors} ERROR(S)")

    report_lines.append("")

    # Detailed results
    for i, vr in enumerate(validation_results, 1):
        report_lines.append(f"Validation {i}:")
        report_lines.append(f"  Status: {'✅ PASS' if vr.valid else '❌ FAIL'}")

        if vr.errors:
            report_lines.append(f"  Errors: {len(vr.errors)}")
            for error in vr.errors:
                report_lines.append(f"    - {error}")

        if vr.warnings:
            report_lines.append(f"  Warnings: {len(vr.warnings)}")
            for warning in vr.warnings:
                report_lines.append(f"    - {warning}")

        if vr.statistics:
            report_lines.append(f"  Statistics: {vr.statistics}")

        report_lines.append("")

    report_lines.append("=" * 80)

    return "\n".join(report_lines)


if __name__ == "__main__":
    # Example usage
    from services.ground_truth_matching_service import MatchResult

    # Create test matches
    matches = [
        MatchResult(
            ground_truth_id="gt-1",
            detection_event_id="det-1",
            match_type='TP',
            temporal_offset=25.0,
            confidence=0.95,
            iou_score=0.9,
            latency_ms=25.0
        ),
        MatchResult(
            ground_truth_id="gt-2",
            detection_event_id=None,
            match_type='FN',
            temporal_offset=0.0,
            confidence=None,
            iou_score=0.0,
            latency_ms=None
        )
    ]

    # Validate
    result = validate_matches(matches, strict=False)
    print(generate_validation_report([result]))
