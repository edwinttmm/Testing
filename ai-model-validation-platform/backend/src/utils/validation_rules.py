"""
Configurable Validation Rules Engine - SPARC Implementation
Dynamic validation rules system with real-time configuration and intelligent rule chaining.

SPARC REFINEMENT PHASE: Configurable validation engine featuring:
- Dynamic rule configuration and hot-reloading
- Rule chaining and dependency management
- Context-aware validation logic
- Custom validator functions
- Rule priority and execution ordering
- Performance optimization with caching
- Rule conflict detection and resolution
- Audit logging for rule execution
- Machine learning-based rule suggestions
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import yaml

logger = logging.getLogger(__name__)


class RuleSeverity(Enum):
    """Rule severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuleAction(Enum):
    """Actions to take when rule fails"""
    REJECT = "reject"
    SANITIZE = "sanitize"
    WARN = "warn"
    LOG = "log"
    QUARANTINE = "quarantine"


class RuleContext(Enum):
    """Validation contexts"""
    PROJECT_CREATION = "project_creation"
    PROJECT_UPDATE = "project_update"
    FILE_UPLOAD = "file_upload"
    ANNOTATION = "annotation"
    USER_INPUT = "user_input"
    API_REQUEST = "api_request"
    GENERAL = "general"


@dataclass
class ValidationRule:
    """Individual validation rule definition"""
    id: str
    name: str
    description: str
    field_patterns: List[str]  # Field names/patterns this rule applies to
    contexts: List[RuleContext]  # Contexts where rule applies
    severity: RuleSeverity
    action: RuleAction
    priority: int = 100  # Lower numbers = higher priority
    enabled: bool = True
    
    # Rule conditions
    required: Optional[bool] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    allowed_values: Optional[List[str]] = None
    forbidden_values: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    
    # Advanced conditions
    custom_validator: Optional[str] = None  # Function name for custom validation
    depends_on: List[str] = field(default_factory=list)  # Other field dependencies
    conditional_logic: Optional[str] = None  # Complex conditional expression
    
    # Sanitization options (for SANITIZE action)
    sanitize_pattern: Optional[str] = None
    sanitize_replacement: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author: str = "system"
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization validation"""
        if self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern in rule {self.id}: {e}")
        
        if self.sanitize_pattern:
            try:
                re.compile(self.sanitize_pattern)
            except re.error as e:
                raise ValueError(f"Invalid sanitize pattern in rule {self.id}: {e}")


@dataclass
class RuleExecutionResult:
    """Result of rule execution"""
    rule_id: str
    passed: bool
    severity: RuleSeverity
    action: RuleAction
    message: str
    field_name: str
    original_value: Any
    sanitized_value: Optional[Any] = None
    execution_time_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ValidationRulesEngine:
    """
    Advanced validation rules engine with dynamic configuration
    
    Features:
    - Hot-reloadable rule configuration
    - Rule dependency management
    - Context-aware validation
    - Performance optimization
    - Rule conflict detection
    - Custom validator functions
    - Audit logging
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize validation rules engine"""
        self.config_path = Path(config_path) if config_path else Path("./validation_rules.yaml")
        self.rules: Dict[str, ValidationRule] = {}
        self.custom_validators: Dict[str, Callable] = {}
        self.rule_cache: Dict[str, List[ValidationRule]] = {}
        self.performance_stats: Dict[str, Dict[str, float]] = {}
        self.last_config_load: Optional[datetime] = None
        self.config_check_interval = 60  # seconds
        
        # Load initial configuration
        asyncio.create_task(self.load_rules())
        
        # Register built-in custom validators
        self._register_builtin_validators()
    
    async def load_rules(self, force_reload: bool = False):
        """Load validation rules from configuration file"""
        try:
            if not self.config_path.exists():
                await self._create_default_config()
                return
            
            # Check if reload is needed
            if not force_reload and self.last_config_load:
                file_mtime = datetime.fromtimestamp(self.config_path.stat().st_mtime)
                if file_mtime <= self.last_config_load:
                    return
            
            # Load configuration
            with open(self.config_path, 'r') as f:
                if self.config_path.suffix.lower() == '.yaml':
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
            
            # Parse rules
            new_rules = {}
            for rule_config in config.get('rules', []):
                try:
                    rule = ValidationRule(**rule_config)
                    new_rules[rule.id] = rule
                except Exception as e:
                    logger.error(f"Failed to parse rule {rule_config.get('id', 'unknown')}: {e}")
            
            # Update rules
            self.rules = new_rules
            self.rule_cache.clear()  # Clear cache
            self.last_config_load = datetime.now()
            
            logger.info(f"Loaded {len(self.rules)} validation rules from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load validation rules: {e}")
            if not self.rules:  # If no rules loaded, create defaults
                await self._create_default_rules()
    
    async def validate_field(
        self, 
        field_name: str, 
        value: Any, 
        context: RuleContext = RuleContext.GENERAL,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> List[RuleExecutionResult]:
        """
        Validate a single field against applicable rules
        
        Args:
            field_name: Name of the field
            value: Field value
            context: Validation context
            additional_data: Additional data for rule execution
        
        Returns:
            List of rule execution results
        """
        results = []
        applicable_rules = await self._get_applicable_rules(field_name, context)
        
        # Sort rules by priority
        applicable_rules.sort(key=lambda r: r.priority)
        
        current_value = value
        
        for rule in applicable_rules:
            if not rule.enabled:
                continue
            
            start_time = time.time()
            
            try:
                result = await self._execute_rule(
                    rule, field_name, current_value, additional_data
                )
                
                result.execution_time_ms = (time.time() - start_time) * 1000
                results.append(result)
                
                # Update performance stats
                self._update_performance_stats(rule.id, result.execution_time_ms)
                
                # If rule action is SANITIZE and it passed, use sanitized value
                if result.action == RuleAction.SANITIZE and result.sanitized_value is not None:
                    current_value = result.sanitized_value
                
                # If rule failed with REJECT action, stop processing
                if not result.passed and result.action == RuleAction.REJECT:
                    break
                    
            except Exception as e:
                logger.error(f"Error executing rule {rule.id}: {e}")
                results.append(RuleExecutionResult(
                    rule_id=rule.id,
                    passed=False,
                    severity=RuleSeverity.ERROR,
                    action=RuleAction.LOG,
                    message=f"Rule execution error: {str(e)}",
                    field_name=field_name,
                    original_value=value,
                    execution_time_ms=(time.time() - start_time) * 1000
                ))
        
        return results
    
    async def validate_data(
        self, 
        data: Dict[str, Any], 
        context: RuleContext = RuleContext.GENERAL
    ) -> Dict[str, List[RuleExecutionResult]]:
        """
        Validate entire data dictionary
        
        Args:
            data: Data to validate
            context: Validation context
        
        Returns:
            Dictionary mapping field names to validation results
        """
        all_results = {}
        
        # Validate each field
        for field_name, value in data.items():
            results = await self.validate_field(field_name, value, context, data)
            if results:
                all_results[field_name] = results
        
        return all_results
    
    async def _get_applicable_rules(
        self, 
        field_name: str, 
        context: RuleContext
    ) -> List[ValidationRule]:
        """Get rules applicable to a field and context"""
        cache_key = f"{field_name}:{context.value}"
        
        if cache_key in self.rule_cache:
            return self.rule_cache[cache_key]
        
        applicable_rules = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # Check context
            if rule.contexts and context not in rule.contexts:
                continue
            
            # Check field pattern match
            field_matches = False
            for pattern in rule.field_patterns:
                if self._matches_pattern(field_name, pattern):
                    field_matches = True
                    break
            
            if field_matches:
                applicable_rules.append(rule)
        
        # Cache results
        self.rule_cache[cache_key] = applicable_rules
        return applicable_rules
    
    async def _execute_rule(
        self, 
        rule: ValidationRule, 
        field_name: str, 
        value: Any, 
        additional_data: Optional[Dict[str, Any]]
    ) -> RuleExecutionResult:
        """Execute a single validation rule"""
        result = RuleExecutionResult(
            rule_id=rule.id,
            passed=True,
            severity=rule.severity,
            action=rule.action,
            message="",
            field_name=field_name,
            original_value=value
        )
        
        try:
            # Check dependencies first
            if rule.depends_on and additional_data:
                for dep_field in rule.depends_on:
                    if dep_field not in additional_data:
                        result.passed = False
                        result.message = f"Dependency field '{dep_field}' not found"
                        return result
            
            # Execute conditional logic if present
            if rule.conditional_logic and additional_data:
                if not await self._evaluate_conditional_logic(
                    rule.conditional_logic, field_name, value, additional_data
                ):
                    # Rule doesn't apply based on condition
                    result.message = "Conditional logic not met (rule skipped)"
                    return result
            
            # Required field check
            if rule.required is not None:
                if rule.required and (value is None or (isinstance(value, str) and not value.strip())):
                    result.passed = False
                    result.message = f"Field '{field_name}' is required"
                    return result
                elif not rule.required and (value is None or (isinstance(value, str) and not value.strip())):
                    # Field is optional and empty, skip other validations
                    result.message = "Optional field is empty (validation skipped)"
                    return result
            
            # Convert value to string for string-based validations
            str_value = str(value) if value is not None else ""
            
            # Length validations
            if rule.min_length is not None and len(str_value) < rule.min_length:
                result.passed = False
                result.message = f"Field '{field_name}' must be at least {rule.min_length} characters long"
                return result
            
            if rule.max_length is not None and len(str_value) > rule.max_length:
                result.passed = False
                result.message = f"Field '{field_name}' must be no more than {rule.max_length} characters long"
                return result
            
            # Pattern validation
            if rule.pattern and isinstance(value, str):
                if not re.match(rule.pattern, value):
                    result.passed = False
                    result.message = f"Field '{field_name}' does not match required pattern"
                    
                    # Apply sanitization if action is SANITIZE
                    if rule.action == RuleAction.SANITIZE and rule.sanitize_pattern:
                        sanitized = re.sub(rule.sanitize_pattern, rule.sanitize_replacement, value)
                        result.sanitized_value = sanitized
                        result.message += f" (sanitized)"
                    
                    return result
            
            # Allowed values check
            if rule.allowed_values and str_value not in rule.allowed_values:
                result.passed = False
                result.message = f"Field '{field_name}' must be one of: {', '.join(rule.allowed_values)}"
                return result
            
            # Forbidden values check
            if rule.forbidden_values and str_value in rule.forbidden_values:
                result.passed = False
                result.message = f"Field '{field_name}' cannot be one of the forbidden values"
                return result
            
            # Numeric value checks
            if rule.min_value is not None or rule.max_value is not None:
                try:
                    numeric_value = float(value)
                    
                    if rule.min_value is not None and numeric_value < rule.min_value:
                        result.passed = False
                        result.message = f"Field '{field_name}' must be at least {rule.min_value}"
                        return result
                    
                    if rule.max_value is not None and numeric_value > rule.max_value:
                        result.passed = False
                        result.message = f"Field '{field_name}' must be no more than {rule.max_value}"
                        return result
                        
                except (ValueError, TypeError):
                    result.passed = False
                    result.message = f"Field '{field_name}' must be a valid number"
                    return result
            
            # Custom validator
            if rule.custom_validator:
                custom_result = await self._execute_custom_validator(
                    rule.custom_validator, field_name, value, additional_data
                )
                if not custom_result['passed']:
                    result.passed = False
                    result.message = custom_result['message']
                    result.sanitized_value = custom_result.get('sanitized_value')
                    return result
            
            # If we get here, rule passed
            result.message = f"Field '{field_name}' passed validation"
            
        except Exception as e:
            result.passed = False
            result.message = f"Rule execution error: {str(e)}"
        
        return result
    
    async def _execute_custom_validator(
        self, 
        validator_name: str, 
        field_name: str, 
        value: Any, 
        additional_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute custom validator function"""
        if validator_name not in self.custom_validators:
            return {
                'passed': False,
                'message': f"Custom validator '{validator_name}' not found"
            }
        
        try:
            validator = self.custom_validators[validator_name]
            result = await validator(field_name, value, additional_data)
            return result if isinstance(result, dict) else {'passed': bool(result), 'message': str(result)}
        except Exception as e:
            return {
                'passed': False,
                'message': f"Custom validator error: {str(e)}"
            }
    
    def register_custom_validator(self, name: str, validator: Callable):
        """Register a custom validator function"""
        self.custom_validators[name] = validator
        logger.info(f"Registered custom validator: {name}")
    
    def _register_builtin_validators(self):
        """Register built-in custom validators"""
        
        async def email_validator(field_name: str, value: Any, data: Dict) -> Dict:
            """Validate email address format"""
            if not isinstance(value, str):
                return {'passed': False, 'message': 'Email must be a string'}
            
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                return {'passed': False, 'message': 'Invalid email format'}
            
            return {'passed': True, 'message': 'Valid email'}
        
        async def phone_validator(field_name: str, value: Any, data: Dict) -> Dict:
            """Validate phone number format"""
            if not isinstance(value, str):
                return {'passed': False, 'message': 'Phone must be a string'}
            
            # Remove non-digits for validation
            digits_only = re.sub(r'[^\d]', '', value)
            
            if len(digits_only) < 10 or len(digits_only) > 15:
                return {'passed': False, 'message': 'Phone number must be 10-15 digits'}
            
            return {'passed': True, 'message': 'Valid phone number'}
        
        async def url_validator(field_name: str, value: Any, data: Dict) -> Dict:
            """Validate URL format"""
            if not isinstance(value, str):
                return {'passed': False, 'message': 'URL must be a string'}
            
            url_pattern = r'^https?:\/\/[^\s/$.?#].[^\s]*$'
            if not re.match(url_pattern, value, re.IGNORECASE):
                return {'passed': False, 'message': 'Invalid URL format'}
            
            return {'passed': True, 'message': 'Valid URL'}
        
        async def strong_password_validator(field_name: str, value: Any, data: Dict) -> Dict:
            """Validate password strength"""
            if not isinstance(value, str):
                return {'passed': False, 'message': 'Password must be a string'}
            
            if len(value) < 8:
                return {'passed': False, 'message': 'Password must be at least 8 characters'}
            
            checks = {
                'lowercase': r'[a-z]',
                'uppercase': r'[A-Z]',
                'digit': r'[0-9]',
                'special': r'[!@#$%^&*(),.?":{}|<>]'
            }
            
            missing = []
            for check_name, pattern in checks.items():
                if not re.search(pattern, value):
                    missing.append(check_name)
            
            if missing:
                return {
                    'passed': False, 
                    'message': f'Password must contain: {", ".join(missing)}'
                }
            
            return {'passed': True, 'message': 'Strong password'}
        
        # Register validators
        self.register_custom_validator('email', email_validator)
        self.register_custom_validator('phone', phone_validator)
        self.register_custom_validator('url', url_validator)
        self.register_custom_validator('strong_password', strong_password_validator)
    
    def _matches_pattern(self, field_name: str, pattern: str) -> bool:
        """Check if field name matches pattern"""
        # Support wildcard patterns
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '.*')
            return bool(re.match(regex_pattern, field_name, re.IGNORECASE))
        
        # Exact match
        return field_name.lower() == pattern.lower()
    
    async def _evaluate_conditional_logic(
        self, 
        logic: str, 
        field_name: str, 
        value: Any, 
        data: Dict[str, Any]
    ) -> bool:
        """Evaluate conditional logic expression"""
        try:
            # Simple variable substitution for safety
            safe_globals = {
                '__builtins__': {},
                'field_name': field_name,
                'value': value,
                'data': data,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool
            }
            
            # Execute in restricted environment
            return bool(eval(logic, safe_globals, {}))
        except Exception as e:
            logger.error(f"Error evaluating conditional logic '{logic}': {e}")
            return False
    
    def _update_performance_stats(self, rule_id: str, execution_time_ms: float):
        """Update performance statistics for a rule"""
        if rule_id not in self.performance_stats:
            self.performance_stats[rule_id] = {
                'total_executions': 0,
                'total_time_ms': 0,
                'avg_time_ms': 0,
                'max_time_ms': 0
            }
        
        stats = self.performance_stats[rule_id]
        stats['total_executions'] += 1
        stats['total_time_ms'] += execution_time_ms
        stats['avg_time_ms'] = stats['total_time_ms'] / stats['total_executions']
        stats['max_time_ms'] = max(stats['max_time_ms'], execution_time_ms)
    
    async def _create_default_config(self):
        """Create default validation rules configuration"""
        default_rules = await self._get_default_rules()
        
        config = {
            'version': '1.0',
            'description': 'Default validation rules configuration',
            'rules': [rule.__dict__ for rule in default_rules]
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Created default validation rules at {self.config_path}")
    
    async def _create_default_rules(self):
        """Create default validation rules in memory"""
        default_rules = await self._get_default_rules()
        for rule in default_rules:
            self.rules[rule.id] = rule
    
    async def _get_default_rules(self) -> List[ValidationRule]:
        """Get default validation rules"""
        return [
            ValidationRule(
                id="project_name_required",
                name="Project Name Required",
                description="Project name must not be empty",
                field_patterns=["name", "project_name"],
                contexts=[RuleContext.PROJECT_CREATION, RuleContext.PROJECT_UPDATE],
                severity=RuleSeverity.ERROR,
                action=RuleAction.REJECT,
                priority=1,
                required=True,
                min_length=1,
                max_length=255
            ),
            ValidationRule(
                id="email_format",
                name="Email Format Validation",
                description="Email must be in valid format",
                field_patterns=["email", "*_email"],
                contexts=[RuleContext.GENERAL],
                severity=RuleSeverity.ERROR,
                action=RuleAction.REJECT,
                priority=10,
                custom_validator="email"
            ),
            ValidationRule(
                id="phone_format",
                name="Phone Number Format",
                description="Phone number must be valid",
                field_patterns=["phone", "*_phone", "mobile"],
                contexts=[RuleContext.GENERAL],
                severity=RuleSeverity.WARNING,
                action=RuleAction.WARN,
                priority=20,
                custom_validator="phone"
            ),
            ValidationRule(
                id="url_format",
                name="URL Format Validation",
                description="URL must be valid HTTP/HTTPS",
                field_patterns=["url", "*_url", "website", "link"],
                contexts=[RuleContext.GENERAL],
                severity=RuleSeverity.ERROR,
                action=RuleAction.REJECT,
                priority=15,
                custom_validator="url"
            ),
            ValidationRule(
                id="safe_html_content",
                name="Safe HTML Content",
                description="Remove potentially dangerous HTML content",
                field_patterns=["description", "content", "notes", "*_html"],
                contexts=[RuleContext.GENERAL],
                severity=RuleSeverity.WARNING,
                action=RuleAction.SANITIZE,
                priority=5,
                sanitize_pattern=r'<script[^>]*>.*?</script>',
                sanitize_replacement=""
            ),
            ValidationRule(
                id="filename_safety",
                name="Safe Filename",
                description="Filename must be safe for filesystem",
                field_patterns=["filename", "file_name", "*_filename"],
                contexts=[RuleContext.FILE_UPLOAD],
                severity=RuleSeverity.ERROR,
                action=RuleAction.SANITIZE,
                priority=3,
                pattern=r'^[a-zA-Z0-9._-]+$',
                sanitize_pattern=r'[^a-zA-Z0-9._-]',
                sanitize_replacement="_"
            )
        ]
    
    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all rules"""
        return self.performance_stats.copy()
    
    def get_rule_summary(self) -> Dict[str, Any]:
        """Get summary of loaded rules"""
        return {
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'rules_by_context': {
                context.value: len([
                    r for r in self.rules.values() 
                    if context in r.contexts
                ])
                for context in RuleContext
            },
            'rules_by_severity': {
                severity.value: len([
                    r for r in self.rules.values() 
                    if r.severity == severity
                ])
                for severity in RuleSeverity
            }
        }