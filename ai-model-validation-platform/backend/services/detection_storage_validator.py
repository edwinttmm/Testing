"""
Detection Storage Configuration Validator

Ensures only dedicated_labjack_monitor stores detection events to prevent duplicates.

This validator enforces the single source of truth principle for detection event storage,
preventing multiple services from creating duplicate database records.

Allowed Storage Services:
- dedicated_labjack_monitor: Primary storage service with video timing enrichment

Blocked Services:
- labjack_detection_service: Should use store_in_db=False
- raw_labjack_integration: Should use store_in_db=False
- All other services: Should use store_in_db=False

Usage:
    from services.detection_storage_validator import DetectionStorageValidator

    # In service initialization:
    DetectionStorageValidator.validate_config('my_service', store_in_db)

    # In monitoring/logging:
    DetectionStorageValidator.log_storage_config('my_service', store_in_db)
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DetectionStorageValidator:
    """
    Validates detection storage configuration at runtime.

    This class enforces the rule that only dedicated_labjack_monitor
    may store detection events to the database. All other services
    must use store_in_db=False and rely on the dedicated monitor
    for enriched storage with video timing metadata.
    """

    # Services allowed to have store_in_db=True
    ALLOWED_STORAGE_SERVICES: List[str] = [
        'dedicated_labjack_monitor'
    ]

    # Services that should NEVER store directly
    BLOCKED_STORAGE_SERVICES: List[str] = [
        'labjack_detection_service',
        'raw_labjack_integration',
        'labjack_hardware_service',
        'windows_labjack_bridge'
    ]

    # Track validation calls for auditing
    _validation_log: List[dict] = []
    _max_log_entries: int = 1000

    @classmethod
    def validate_config(
        cls,
        service_name: str,
        store_in_db: bool,
        raise_on_error: bool = True
    ) -> bool:
        """
        Validate that only allowed services have store_in_db=True.

        Args:
            service_name: Name of the service attempting storage
            store_in_db: Requested storage configuration
            raise_on_error: If True, raise RuntimeError on invalid config

        Returns:
            True if configuration is valid, False otherwise

        Raises:
            RuntimeError: If invalid configuration detected and raise_on_error=True
        """

        # Log validation attempt
        cls._log_validation(service_name, store_in_db, 'validate')

        # Case 1: Service explicitly blocked from storage
        if service_name in cls.BLOCKED_STORAGE_SERVICES and store_in_db:
            error_msg = (
                f"❌ CONFIGURATION ERROR: Service '{service_name}' "
                f"is explicitly BLOCKED from storing detection events. "
                f"This service must use store_in_db=False. "
                f"Detection storage is handled by dedicated_labjack_monitor."
            )
            logger.error(error_msg)

            if raise_on_error:
                raise RuntimeError(error_msg)
            return False

        # Case 2: Service not in allowed list attempting storage
        if store_in_db and service_name not in cls.ALLOWED_STORAGE_SERVICES:
            error_msg = (
                f"❌ CONFIGURATION ERROR: Service '{service_name}' "
                f"attempted to enable store_in_db=True. "
                f"Only {cls.ALLOWED_STORAGE_SERVICES} may store detection events. "
                f"Set store_in_db=False to use dedicated monitor for enriched storage."
            )
            logger.error(error_msg)

            if raise_on_error:
                raise RuntimeError(error_msg)
            return False

        # Case 3: Allowed service with storage enabled
        if store_in_db and service_name in cls.ALLOWED_STORAGE_SERVICES:
            logger.info(
                f"✅ Storage validation passed: {service_name} "
                f"(store_in_db=True) - Authorized storage service"
            )
            return True

        # Case 4: Any service with storage disabled (always valid)
        logger.debug(
            f"✅ Storage validation passed: {service_name} "
            f"(store_in_db=False) - Using dedicated monitor"
        )
        return True

    @classmethod
    def log_storage_config(
        cls,
        service_name: str,
        store_in_db: bool,
        additional_context: Optional[dict] = None
    ):
        """
        Log storage configuration for auditing and monitoring.

        Args:
            service_name: Name of the service
            store_in_db: Storage configuration
            additional_context: Optional additional context to log
        """

        # Log validation attempt
        cls._log_validation(service_name, store_in_db, 'log', additional_context)

        if store_in_db:
            if service_name in cls.ALLOWED_STORAGE_SERVICES:
                logger.info(
                    f"📝 STORAGE ENABLED: {service_name} (store_in_db=True) - "
                    f"Authorized storage service"
                )
            else:
                logger.warning(
                    f"⚠️ STORAGE ENABLED: {service_name} (store_in_db=True) - "
                    f"WARNING: This may create duplicate detection events. "
                    f"Consider using store_in_db=False"
                )
        else:
            logger.info(
                f"📝 Storage disabled: {service_name} (store_in_db=False) - "
                f"Dedicated monitor will handle storage"
            )

        # Log additional context if provided
        if additional_context:
            logger.debug(f"   Context: {additional_context}")

    @classmethod
    def get_allowed_services(cls) -> List[str]:
        """Get list of services allowed to store detection events."""
        return cls.ALLOWED_STORAGE_SERVICES.copy()

    @classmethod
    def get_blocked_services(cls) -> List[str]:
        """Get list of services explicitly blocked from storage."""
        return cls.BLOCKED_STORAGE_SERVICES.copy()

    @classmethod
    def is_storage_allowed(cls, service_name: str) -> bool:
        """
        Check if service is allowed to store detection events.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is allowed to store, False otherwise
        """
        return service_name in cls.ALLOWED_STORAGE_SERVICES

    @classmethod
    def is_storage_blocked(cls, service_name: str) -> bool:
        """
        Check if service is explicitly blocked from storage.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is blocked from storage, False otherwise
        """
        return service_name in cls.BLOCKED_STORAGE_SERVICES

    @classmethod
    def _log_validation(
        cls,
        service_name: str,
        store_in_db: bool,
        operation: str,
        context: Optional[dict] = None
    ):
        """
        Internal method to log validation attempts for auditing.

        Args:
            service_name: Name of the service
            store_in_db: Storage configuration
            operation: Type of operation ('validate' or 'log')
            context: Optional additional context
        """
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service_name': service_name,
            'store_in_db': store_in_db,
            'operation': operation,
            'context': context
        }

        # Add to validation log
        cls._validation_log.append(entry)

        # Trim log if too large
        if len(cls._validation_log) > cls._max_log_entries:
            cls._validation_log = cls._validation_log[-cls._max_log_entries:]

    @classmethod
    def get_validation_log(
        cls,
        service_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get validation log entries for auditing.

        Args:
            service_name: Optional filter by service name
            limit: Optional limit number of entries returned

        Returns:
            List of validation log entries
        """
        log_entries = cls._validation_log

        # Filter by service name if provided
        if service_name:
            log_entries = [
                entry for entry in log_entries
                if entry['service_name'] == service_name
            ]

        # Limit entries if requested
        if limit:
            log_entries = log_entries[-limit:]

        return log_entries

    @classmethod
    def get_storage_statistics(cls) -> dict:
        """
        Get statistics about storage configuration validation.

        Returns:
            Dictionary with validation statistics
        """
        total_validations = len(cls._validation_log)

        # Count by service
        service_counts = {}
        storage_enabled_count = 0
        storage_disabled_count = 0

        for entry in cls._validation_log:
            service = entry['service_name']
            service_counts[service] = service_counts.get(service, 0) + 1

            if entry['store_in_db']:
                storage_enabled_count += 1
            else:
                storage_disabled_count += 1

        return {
            'total_validations': total_validations,
            'storage_enabled_count': storage_enabled_count,
            'storage_disabled_count': storage_disabled_count,
            'service_counts': service_counts,
            'allowed_services': cls.ALLOWED_STORAGE_SERVICES,
            'blocked_services': cls.BLOCKED_STORAGE_SERVICES
        }

    @classmethod
    def clear_validation_log(cls):
        """Clear validation log (useful for testing)."""
        cls._validation_log.clear()
        logger.info("Validation log cleared")


# Convenience functions for common operations

def validate_storage_config(service_name: str, store_in_db: bool) -> bool:
    """
    Convenience function to validate storage configuration.

    Raises RuntimeError if configuration is invalid.
    """
    return DetectionStorageValidator.validate_config(
        service_name,
        store_in_db,
        raise_on_error=True
    )


def log_storage_config(service_name: str, store_in_db: bool, context: Optional[dict] = None):
    """Convenience function to log storage configuration."""
    DetectionStorageValidator.log_storage_config(service_name, store_in_db, context)


def is_storage_allowed(service_name: str) -> bool:
    """Convenience function to check if service is allowed to store."""
    return DetectionStorageValidator.is_storage_allowed(service_name)


# Export key classes and functions
__all__ = [
    'DetectionStorageValidator',
    'validate_storage_config',
    'log_storage_config',
    'is_storage_allowed'
]
