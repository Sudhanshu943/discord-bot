"""Safety filter for prompt injection and secret detection."""

import re
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)


class SafetyFilter:
    """Detects and prevents prompt injection, secrets leakage, and validates message sizes."""
    
    # Patterns for prompt injection detection
    INJECTION_PATTERNS = [
        r"(?i)(ignore[\s\w]*prompt|ignore[\s\w]*instruction|new[\s\w]*prompt|act[\s\w]*as|system[\s\w]*prompt|admin[\s\w]*(mode|prompt)|jailbreak)",
        r"(?i)(do[\s\w]*not[\s\w]*(respond|mention)|you[\s\w]*are[\s\w]*a|from[\s\w]*now[\s\w]*on)",
        r"(?i)(disregard|override|bypass|circumvent|ignore[\s\w]*previous|forget)",
    ]
    
    # Patterns for secret detection
    SECRET_PATTERNS = {
        "api_key": r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([a-z0-9]+)['\"]?",
        "discord_token": r"([a-zA-Z0-9_-]{24}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27})",
        "webhook": r"(?i)(webhook|hook)['\"]?\s*[:=]\s*['\"]?([a-z0-9:/\-._]+)['\"]?",
        "password": r"(?i)(password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([a-z0-9!@#$%^&*]+)['\"]?",
        "database_url": r"(?i)(database[_-]?url|db[_-]?url)['\"]?\s*[:=]\s*['\"]?([a-z0-9:/\-._@]+)['\"]?",
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "private_key": r"(?i)(private[_-]?key|rsa[_-]?key)['\"]?\s*[:=]",
    }
    
    def __init__(self, max_message_length: int = 2000, max_context_length: int = 8000):
        """
        Initialize safety filter.
        
        Args:
            max_message_length: Maximum length of individual message (Discord limit)
            max_context_length: Maximum length of accumulated context for LLM
        """
        self.max_message_length = max_message_length
        self.max_context_length = max_context_length
        self.compile_patterns()
    
    def compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.injection_regexes = [re.compile(pattern) for pattern in self.INJECTION_PATTERNS]
        self.secret_regexes = {
            name: re.compile(pattern) for name, pattern in self.SECRET_PATTERNS.items()
        }
    
    def detect_prompt_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect potential prompt injection attempts.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        for i, regex in enumerate(self.injection_regexes):
            if regex.search(text):
                reason = f"Potential prompt injection pattern detected (pattern {i})"
                logger.warning(f"Prompt injection detected: {reason}")
                return True, reason
        
        return False, None
    
    def scan_for_secrets(self, text: str) -> Tuple[bool, List[str]]:
        """
        Scan text for secrets like API keys, tokens, passwords.
        
        Args:
            text: Text to scan
            
        Returns:
            Tuple of (has_secrets, list_of_secret_types)
        """
        found_secrets = []
        
        for secret_type, regex in self.secret_regexes.items():
            if regex.search(text):
                found_secrets.append(secret_type)
                logger.warning(f"Potential secret detected: {secret_type}")
        
        return len(found_secrets) > 0, found_secrets
    
    def redact_secrets(self, text: str) -> str:
        """
        Redact secrets from text.
        
        Args:
            text: Text to redact
            
        Returns:
            Text with secrets replaced by [REDACTED_*]
        """
        redacted = text
        
        for secret_type, regex in self.secret_regexes.items():
            redacted = regex.sub(f"[REDACTED_{secret_type.upper()}]", redacted)
        
        return redacted
    
    def validate_message_length(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate message fits within Discord's limit.
        
        Args:
            message: Message to validate
            
        Returns:
            Tuple of (is_valid, error_reason)
        """
        if len(message) > self.max_message_length:
            reason = f"Message exceeds Discord limit ({len(message)} > {self.max_message_length})"
            return False, reason
        
        return True, None
    
    def validate_context_length(self, context: str) -> Tuple[bool, Optional[str]]:
        """
        Validate accumulated context doesn't exceed limits.
        
        Args:
            context: Context string to validate
            
        Returns:
            Tuple of (is_valid, error_reason)
        """
        if len(context) > self.max_context_length:
            reason = f"Context exceeds limit ({len(context)} > {self.max_context_length})"
            return False, reason
        
        return True, None
    
    async def validate_user_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of user input.
        
        Args:
            text: User input to validate
            
        Returns:
            Tuple of (is_valid, error_reason)
        """
        # Check message length
        valid, error = self.validate_message_length(text)
        if not valid:
            return valid, error
        
        # Check for prompt injection
        suspicious, reason = self.detect_prompt_injection(text)
        if suspicious:
            return False, f"⚠️ Request blocked: {reason}"
        
        # Check for secrets (warn but allow)
        has_secrets, secret_types = self.scan_for_secrets(text)
        if has_secrets:
            logger.warning(f"User input contains secrets: {secret_types}")
        
        return True, None
    
    async def validate_ai_output(self, text: str) -> Tuple[str, List[str]]:
        """
        Validate and redact AI output.
        
        Args:
            text: AI-generated output
            
        Returns:
            Tuple of (redacted_text, detected_secrets)
        """
        has_secrets, secret_types = self.scan_for_secrets(text)
        redacted = self.redact_secrets(text)
        
        return redacted, secret_types
