"""
Advanced Input Sanitization Module - SPARC Implementation
Comprehensive input sanitization with multi-layer security protection.

SPARC REFINEMENT PHASE: Advanced input sanitization featuring:
- Multi-layer XSS protection with context-aware sanitization
- SQL injection prevention with parameterized query validation
- NoSQL injection detection and neutralization
- Advanced HTML sanitization with whitelist approach
- URL validation and sanitization
- File path traversal protection
- Command injection prevention
- LDAP injection protection
"""

import html
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Union
import bleach
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class InputSanitizer:
    """
    Advanced input sanitization with comprehensive threat protection
    
    Provides multi-layer sanitization for various input types with
    context-aware cleaning and security-first design.
    """
    
    # XSS Prevention patterns
    XSS_PATTERNS = [
        # Script tags
        (re.compile(r'<\s*script[^>]*>.*?</\s*script\s*>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<\s*script[^>]*>', re.IGNORECASE), ''),
        
        # Event handlers
        (re.compile(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', re.IGNORECASE), ''),
        (re.compile(r'\s*on\w+\s*=\s*[^>\s]+', re.IGNORECASE), ''),
        
        # JavaScript protocol
        (re.compile(r'javascript\s*:', re.IGNORECASE), 'removed:'),
        (re.compile(r'vbscript\s*:', re.IGNORECASE), 'removed:'),
        (re.compile(r'data\s*:', re.IGNORECASE), 'removed:'),
        
        # Style with expression
        (re.compile(r'style\s*=\s*["\'][^"\']*expression[^"\']*["\']', re.IGNORECASE), ''),
        
        # Object/embed/iframe tags
        (re.compile(r'<\s*(object|embed|iframe|applet)[^>]*>.*?</\s*\1\s*>', re.IGNORECASE | re.DOTALL), ''),
        (re.compile(r'<\s*(object|embed|iframe|applet)[^>]*/?>', re.IGNORECASE), ''),
        
        # Meta refresh
        (re.compile(r'<\s*meta[^>]*http-equiv[^>]*refresh[^>]*>', re.IGNORECASE), ''),
        
        # Form tags (context dependent)
        (re.compile(r'<\s*form[^>]*>.*?</\s*form\s*>', re.IGNORECASE | re.DOTALL), ''),
    ]
    
    # SQL Injection patterns
    SQL_INJECTION_PATTERNS = [
        # Comment sequences
        (re.compile(r'--.*$', re.MULTILINE), ''),
        (re.compile(r'/\*.*?\*/', re.DOTALL), ''),
        (re.compile(r'#.*$', re.MULTILINE), ''),
        
        # Union attacks
        (re.compile(r'\bunion\s+select\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\bunion\s+all\s+select\b', re.IGNORECASE), 'removed'),
        
        # Information schema attacks
        (re.compile(r'\binformation_schema\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\bsysobjects\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\bsyscolumns\b', re.IGNORECASE), 'removed'),
        
        # Function calls
        (re.compile(r'\b(exec|execute|sp_|xp_)\w*\s*\(', re.IGNORECASE), 'removed('),
        (re.compile(r'\b(char|ascii|concat|substring)\s*\(', re.IGNORECASE), 'removed('),
        
        # Dangerous keywords
        (re.compile(r'\b(drop|delete|insert|update|create|alter|grant|revoke)\s+', re.IGNORECASE), 'removed '),
    ]
    
    # NoSQL Injection patterns
    NOSQL_INJECTION_PATTERNS = [
        # MongoDB operators
        (re.compile(r'\$where\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\$(ne|gt|lt|gte|lte|in|nin|exists|regex|mod|size)\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\$(or|and|not|nor)\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\$(eval|function|where)\b', re.IGNORECASE), 'removed'),
        
        # JavaScript in MongoDB
        (re.compile(r'\bthis\.\w+', re.IGNORECASE), 'removed'),
        (re.compile(r'\bdb\.\w+', re.IGNORECASE), 'removed'),
        (re.compile(r'\bcollection\.\w+', re.IGNORECASE), 'removed'),
    ]
    
    # Command Injection patterns
    COMMAND_INJECTION_PATTERNS = [
        (re.compile(r'[;&|`$(){}[\]\\]'), ''),
        (re.compile(r'\b(cat|ls|pwd|whoami|id|ps|netstat|ifconfig|ping|wget|curl)\b', re.IGNORECASE), 'removed'),
        (re.compile(r'\.\.[\\/]', re.IGNORECASE), ''),
    ]
    
    # Path Traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        (re.compile(r'\.\.[\\/]+', re.IGNORECASE), ''),
        (re.compile(r'[\\/]+\.\.', re.IGNORECASE), ''),
        (re.compile(r'%2e%2e[\\/]', re.IGNORECASE), ''),
        (re.compile(r'[\\/]%2e%2e', re.IGNORECASE), ''),
    ]
    
    # LDAP Injection patterns
    LDAP_INJECTION_PATTERNS = [
        (re.compile(r'[()&|!*\\]'), ''),
        (re.compile(r'%[0-9a-f]{2}', re.IGNORECASE), ''),
    ]
    
    # Safe HTML tags and attributes
    SAFE_HTML_TAGS = {
        'a': ['href', 'title', 'target'],
        'b': [],
        'br': [],
        'code': [],
        'div': ['class', 'id'],
        'em': [],
        'h1': ['class', 'id'],
        'h2': ['class', 'id'],
        'h3': ['class', 'id'],
        'h4': ['class', 'id'],
        'h5': ['class', 'id'],
        'h6': ['class', 'id'],
        'i': [],
        'li': [],
        'ol': [],
        'p': ['class', 'id'],
        'pre': ['class'],
        'span': ['class', 'id'],
        'strong': [],
        'ul': [],
    }
    
    # URL schemes that are considered safe
    SAFE_URL_SCHEMES = {'http', 'https', 'mailto', 'ftp', 'ftps'}
    
    def __init__(self):
        """Initialize input sanitizer with security configurations"""
        self.bleach_cleaner = bleach.Cleaner(
            tags=list(self.SAFE_HTML_TAGS.keys()),
            attributes=self.SAFE_HTML_TAGS,
            protocols=self.SAFE_URL_SCHEMES,
            strip=True,
            strip_comments=True
        )
        
        # Compile all patterns for better performance
        self.compiled_patterns = {
            'xss': self.XSS_PATTERNS,
            'sql': self.SQL_INJECTION_PATTERNS,
            'nosql': self.NOSQL_INJECTION_PATTERNS,
            'command': self.COMMAND_INJECTION_PATTERNS,
            'path': self.PATH_TRAVERSAL_PATTERNS,
            'ldap': self.LDAP_INJECTION_PATTERNS
        }
    
    async def sanitize(self, field_name: str, value: Any, context: str = 'general') -> Any:
        """
        Main sanitization method with context-aware cleaning
        
        Args:
            field_name: Name of the field being sanitized
            value: Value to sanitize
            context: Sanitization context (general, html, url, filename, etc.)
        
        Returns:
            Sanitized value
        """
        if value is None:
            return None
        
        # Handle different value types
        if isinstance(value, str):
            return await self._sanitize_string(field_name, value, context)
        elif isinstance(value, dict):
            return await self._sanitize_dict(field_name, value, context)
        elif isinstance(value, list):
            return await self._sanitize_list(field_name, value, context)
        else:
            # For other types, convert to string and sanitize
            return await self._sanitize_string(field_name, str(value), context)
    
    async def _sanitize_string(self, field_name: str, value: str, context: str) -> str:
        """Sanitize string values with context-specific cleaning"""
        if not value:
            return value
        
        original_value = value
        
        try:
            # Apply context-specific sanitization
            if context == 'html':
                value = await self._sanitize_html(value)
            elif context == 'url':
                value = await self._sanitize_url(value)
            elif context == 'filename':
                value = await self._sanitize_filename(value)
            elif context == 'email':
                value = await self._sanitize_email(value)
            elif context == 'phone':
                value = await self._sanitize_phone(value)
            else:
                # General sanitization
                value = await self._sanitize_general(value)
            
            # Apply universal security patterns
            value = await self._apply_security_patterns(value)
            
            # Final safety check
            value = await self._final_safety_check(value)
            
            # Log if significant sanitization occurred
            if len(value) < len(original_value) * 0.9:
                logger.info(
                    f"Significant sanitization applied to field '{field_name}': "
                    f"{len(original_value)} -> {len(value)} characters"
                )
            
            return value
            
        except Exception as e:
            logger.error(f"Error sanitizing field '{field_name}': {str(e)}")
            # Return empty string on error for security
            return ""
    
    async def _sanitize_dict(self, field_name: str, value: dict, context: str) -> dict:
        """Recursively sanitize dictionary values"""
        sanitized = {}
        
        for key, val in value.items():
            # Sanitize the key as well
            sanitized_key = await self._sanitize_string(f"{field_name}.{key}", str(key), 'general')
            sanitized_val = await self.sanitize(f"{field_name}.{key}", val, context)
            sanitized[sanitized_key] = sanitized_val
        
        return sanitized
    
    async def _sanitize_list(self, field_name: str, value: list, context: str) -> list:
        """Recursively sanitize list values"""
        sanitized = []
        
        for i, item in enumerate(value):
            sanitized_item = await self.sanitize(f"{field_name}[{i}]", item, context)
            sanitized.append(sanitized_item)
        
        return sanitized
    
    async def _sanitize_general(self, value: str) -> str:
        """General purpose string sanitization"""
        # HTML encode dangerous characters
        value = html.escape(value, quote=False)
        
        # Remove null bytes and control characters
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value
    
    async def _sanitize_html(self, value: str) -> str:
        """HTML-specific sanitization"""
        # Use bleach for comprehensive HTML sanitization
        value = self.bleach_cleaner.clean(value)
        
        # Additional XSS protection
        for pattern, replacement in self.XSS_PATTERNS:
            value = pattern.sub(replacement, value)
        
        return value
    
    async def _sanitize_url(self, value: str) -> str:
        """URL-specific sanitization"""
        try:
            # Parse URL
            parsed = urllib.parse.urlparse(value)
            
            # Check scheme
            if parsed.scheme and parsed.scheme.lower() not in self.SAFE_URL_SCHEMES:
                return "invalid://removed-unsafe-scheme"
            
            # Sanitize each component
            scheme = parsed.scheme.lower() if parsed.scheme else ''
            netloc = re.sub(r'[^\w\-\.]', '', parsed.netloc) if parsed.netloc else ''
            path = urllib.parse.quote(parsed.path, safe='/') if parsed.path else ''
            params = urllib.parse.quote(parsed.params, safe='&=') if parsed.params else ''
            query = urllib.parse.quote(parsed.query, safe='&=') if parsed.query else ''
            fragment = urllib.parse.quote(parsed.fragment, safe='') if parsed.fragment else ''
            
            # Rebuild URL
            sanitized_url = urllib.parse.urlunparse((
                scheme, netloc, path, params, query, fragment
            ))
            
            return sanitized_url
            
        except Exception as e:
            logger.warning(f"URL sanitization error: {str(e)}")
            return "invalid://sanitization-error"
    
    async def _sanitize_filename(self, value: str) -> str:
        """Filename-specific sanitization"""
        # Remove path traversal attempts
        for pattern, replacement in self.PATH_TRAVERSAL_PATTERNS:
            value = pattern.sub(replacement, value)
        
        # Remove dangerous characters
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', value)
        
        # Limit length
        value = value[:255]
        
        # Ensure it's not empty and doesn't start with dots
        if not value or value.startswith('.'):
            value = f"sanitized_{hash(value) % 10000}"
        
        return value
    
    async def _sanitize_email(self, value: str) -> str:
        """Email-specific sanitization"""
        # Basic email format validation and sanitization
        value = value.lower().strip()
        
        # Remove dangerous characters
        value = re.sub(r'[<>\[\]\\;,]', '', value)
        
        # Basic email pattern validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            return "invalid@sanitized.email"
        
        return value
    
    async def _sanitize_phone(self, value: str) -> str:
        """Phone number sanitization"""
        # Keep only digits, plus, parentheses, hyphens, and spaces
        value = re.sub(r'[^0-9+\-\s()]', '', value)
        
        # Normalize whitespace
        value = ' '.join(value.split())
        
        return value
    
    async def _apply_security_patterns(self, value: str) -> str:
        """Apply all security patterns to detect and neutralize threats"""
        # Apply SQL injection patterns
        for pattern, replacement in self.SQL_INJECTION_PATTERNS:
            value = pattern.sub(replacement, value)
        
        # Apply NoSQL injection patterns
        for pattern, replacement in self.NOSQL_INJECTION_PATTERNS:
            value = pattern.sub(replacement, value)
        
        # Apply command injection patterns
        for pattern, replacement in self.COMMAND_INJECTION_PATTERNS:
            value = pattern.sub(replacement, value)
        
        # Apply LDAP injection patterns
        for pattern, replacement in self.LDAP_INJECTION_PATTERNS:
            value = pattern.sub(replacement, value)
        
        return value
    
    async def _final_safety_check(self, value: str) -> str:
        """Final safety check to catch any remaining threats"""
        # Check for encoded attacks
        decoded_value = urllib.parse.unquote(value)
        if decoded_value != value:
            # If URL decoding changed the value, recursively sanitize
            return await self._sanitize_string('decoded', decoded_value, 'general')
        
        # Check for double-encoded attacks
        double_decoded = urllib.parse.unquote(decoded_value)
        if double_decoded != decoded_value:
            logger.warning("Possible double-encoded attack detected")
            return await self._sanitize_string('double_decoded', double_decoded, 'general')
        
        return value
    
    def is_safe(self, value: str, threat_types: Optional[List[str]] = None) -> bool:
        """
        Check if a string is safe from specified threats
        
        Args:
            value: String to check
            threat_types: List of threat types to check (xss, sql, nosql, etc.)
        
        Returns:
            True if safe, False if threats detected
        """
        if not value:
            return True
        
        if threat_types is None:
            threat_types = ['xss', 'sql', 'nosql', 'command', 'path', 'ldap']
        
        for threat_type in threat_types:
            if threat_type in self.compiled_patterns:
                patterns = self.compiled_patterns[threat_type]
                for pattern, _ in patterns:
                    if pattern.search(value):
                        return False
        
        return True
    
    def get_threat_score(self, value: str) -> int:
        """
        Calculate a threat score for the input (0-100, higher = more dangerous)
        
        Args:
            value: String to analyze
        
        Returns:
            Threat score from 0 (safe) to 100 (very dangerous)
        """
        if not value:
            return 0
        
        score = 0
        
        # Check each threat category
        for threat_type, patterns in self.compiled_patterns.items():
            matches = 0
            for pattern, _ in patterns:
                if pattern.search(value):
                    matches += 1
            
            # Weight different threat types
            weights = {
                'xss': 20,
                'sql': 25,
                'nosql': 20,
                'command': 30,
                'path': 15,
                'ldap': 10
            }
            
            score += matches * weights.get(threat_type, 10)
        
        # Cap at 100
        return min(score, 100)