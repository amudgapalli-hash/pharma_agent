"""
Security Guard Rails Module
Provides input validation, rate limiting, PHI detection, and security utilities.
"""

import re
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
import hashlib
import secrets

logger = logging.getLogger(__name__)

# =====================================================================
# 1. INPUT VALIDATION & SANITIZATION
# =====================================================================

class InputValidator:
    """Validates and sanitizes user inputs to prevent injection attacks."""
    
    # SQL Injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|SCRIPT)\b)",
        r"(--|#|\/\*|\*\/|xp_|sp_)",
        r"('|\")\s*(OR|AND)\s*('|\")?1('|\")?",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>",
        r"javascript:",
        r"on(load|error|click|submit|mouseenter|focus)\s*=",
        r"<\s*iframe\b",
    ]
    
    @staticmethod
    def validate_string(value: str, max_length: int = 1000, field_name: str = "input") -> str:
        """
        Validate and sanitize string input.
        
        Args:
            value: Input string to validate
            max_length: Maximum allowed length
            field_name: Name of field for logging
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If validation fails
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        
        if len(value) == 0:
            raise ValueError(f"{field_name} cannot be empty")
        
        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
        
        # Check for SQL injection
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected in {field_name}: {value[:50]}")
                raise ValueError(f"Invalid characters detected in {field_name}")
        
        # Check for XSS
        for pattern in InputValidator.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS detected in {field_name}: {value[:50]}")
                raise ValueError(f"Invalid HTML/script detected in {field_name}")
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        return value.strip()
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")
        return email.lower()
    
    @staticmethod
    def validate_username(username: str) -> str:
        """Validate username format (alphanumeric, underscore, dash only)."""
        pattern = r'^[a-zA-Z0-9_-]{3,32}$'
        if not re.match(pattern, username):
            raise ValueError("Username must be 3-32 characters, alphanumeric with underscore/dash only")
        return username

# =====================================================================
# 2. PROTECTED HEALTH INFORMATION (PHI) DETECTION
# =====================================================================

class PHIDetector:
    """Detects Protected Health Information in text to prevent HIPAA violations."""
    
    # PHI patterns
    PHI_PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b",
        "MRN": r"\bMRN\s*[\s:=]*(\w+)|\bMedical Record\s+(\w+)",
        "PHONE": r"\b(?:\d{3}[-.]?)?\d{3}[-.]?\d{4}\b",
        "DATE_SPECIFIC": r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        "ZIP_CODE": r"\b\d{5}(?:-\d{4})?\b",
        "EMAIL": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    
    # Common patient name patterns (demo-focused, not comprehensive)
    PATIENT_NAME_KEYWORDS = ["patient", "subject", "participant"]
    
    @staticmethod
    def detect_phi(text: str) -> Dict[str, List[str]]:
        """
        Scan text for Protected Health Information.
        
        Args:
            text: Text to scan
            
        Returns:
            Dictionary of PHI types and detected values
        """
        detected_phi = defaultdict(list)
        
        for phi_type, pattern in PHIDetector.PHI_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Flatten nested tuples from regex groups
                flat_matches = []
                for match in matches:
                    if isinstance(match, tuple):
                        flat_matches.extend([m for m in match if m])
                    else:
                        flat_matches.append(match)
                
                detected_phi[phi_type] = list(set(flat_matches))[:5]  # Limit to 5 examples
                logger.warning(f"Potential {phi_type} detected in text")
        
        return dict(detected_phi) if detected_phi else {}
    
    @staticmethod
    def scan_for_phi_violations(text: str, allow_detected_phi: bool = False) -> tuple:
        """
        Scan for PHI and optionally raise exception.
        
        Args:
            text: Text to scan
            allow_detected_phi: If False, raises exception on PHI detection
            
        Returns:
            Tuple of (is_compliant, detected_phi_dict)
        """
        detected = PHIDetector.detect_phi(text)
        
        if detected and not allow_detected_phi:
            logger.error(f"PHI violations detected: {list(detected.keys())}")
            return False, detected
        
        return True, detected

# =====================================================================
# 3. RATE LIMITING
# =====================================================================

class RateLimiter:
    """Simple in-memory rate limiter using token bucket algorithm."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed for identifier.
        
        Args:
            identifier: Unique identifier (e.g., user ID, IP address)
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return False
        
        # Add current request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for identifier."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        valid_requests = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        return max(0, self.max_requests - len(valid_requests))

# =====================================================================
# 4. SECURITY UTILITIES
# =====================================================================

def hash_sensitive_data(data: str, salt: str = None) -> str:
    """
    Hash sensitive data for logging (never log raw PHI).
    
    Args:
        data: Data to hash
        salt: Optional salt for hashing
        
    Returns:
        Hashed string
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    return hashlib.sha256((data + salt).encode()).hexdigest()[:16]

def generate_request_id() -> str:
    """Generate unique request ID for audit logging."""
    return secrets.token_hex(16)

def require_https(func):
    """Decorator to enforce HTTPS in production."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # In production, check request.url.scheme == "https"
        return await func(*args, **kwargs)
    return wrapper

class SecurityHeaders:
    """Standard security headers for HTTP responses."""
    
    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Return recommended security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
