"""
Custom Exceptions for Chat Module
=================================

Defines custom exception classes for the chatbot system.
"""


class ChatException(Exception):
    """Base exception for chat module."""
    
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)
    
    def __str__(self):
        if self.original_error:
            return f"{self.message} (Caused by: {self.original_error})"
        return self.message


class ProviderException(ChatException):
    """Exception raised when an LLM provider fails."""
    
    def __init__(self, provider_name: str, message: str, original_error: Exception = None):
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] {message}", original_error)


class RateLimitException(ChatException):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(self, retry_after: float = None, message: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        super().__init__(message)
    
    def __str__(self):
        if self.retry_after:
            return f"{self.message}. Try again in {self.retry_after:.1f} seconds."
        return self.message


class ConfigurationException(ChatException):
    """Exception raised for configuration errors."""
    
    def __init__(self, config_key: str, message: str = None):
        self.config_key = config_key
        msg = message or f"Configuration error for key: {config_key}"
        super().__init__(msg)


class ContextException(ChatException):
    """Exception raised for conversation context errors."""
    
    def __init__(self, user_id: int, message: str):
        self.user_id = user_id
        super().__init__(f"[User {user_id}] {message}")


class TimeoutException(ChatException):
    """Exception raised when API request times out."""
    
    def __init__(self, provider_name: str, timeout: float):
        self.provider_name = provider_name
        self.timeout = timeout
        super().__init__(f"[{provider_name}] Request timed out after {timeout} seconds")


class AuthenticationException(ChatException):
    """Exception raised for API authentication failures."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] Authentication failed. Check API key.")
