"""
Rate Limiting System for Chat Module
====================================

Implements rate limiting and cooldown mechanisms for the chatbot.
"""

import time
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional
import logging

from .exceptions import RateLimitException

logger = logging.getLogger(__name__)


@dataclass
class UserRateInfo:
    """Rate limit information for a single user."""
    last_request_time: float = 0.0
    request_count: int = 0
    warning_count: int = 0


@dataclass
class GlobalRateInfo:
    """Global rate limit tracking."""
    request_times: list = field(default_factory=list)
    total_requests: int = 0
    total_blocked: int = 0


class RateLimiter:
    """
    Rate limiter for the chat module.
    
    Implements both per-user cooldowns and global rate limiting.
    Thread-safe using asyncio locks.
    """
    
    def __init__(
        self,
        user_cooldown: float = 3.0,
        global_requests_per_minute: int = 30,
        cleanup_interval: int = 60
    ):
        """
        Initialize the rate limiter.
        
        Args:
            user_cooldown: Cooldown between requests per user (seconds)
            global_requests_per_minute: Maximum global requests per minute
            cleanup_interval: Interval for cleaning up old entries (seconds)
        """
        self.user_cooldown = user_cooldown
        self.global_requests_per_minute = global_requests_per_minute
        self.cleanup_interval = cleanup_interval
        
        # User tracking
        self._user_info: Dict[int, UserRateInfo] = defaultdict(UserRateInfo)
        
        # Global tracking
        self._global_info = GlobalRateInfo()
        
        # Async locks for thread safety
        self._user_lock = asyncio.Lock()
        self._global_lock = asyncio.Lock()
        
        # Last cleanup time
        self._last_cleanup = time.time()
        
        logger.info(
            f"RateLimiter initialized: user_cooldown={user_cooldown}s, "
            f"global_limit={global_requests_per_minute}/min"
        )
    
    async def check_user_rate_limit(self, user_id: int) -> Optional[float]:
        """
        Check if a user is rate limited.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            None if allowed, or retry_after seconds if rate limited
        """
        async with self._user_lock:
            current_time = time.time()
            user_info = self._user_info[user_id]
            
            # Calculate time since last request
            time_since_last = current_time - user_info.last_request_time
            
            if time_since_last < self.user_cooldown:
                retry_after = self.user_cooldown - time_since_last
                user_info.warning_count += 1
                logger.debug(
                    f"User {user_id} rate limited. "
                    f"Retry after: {retry_after:.1f}s "
                    f"(warning #{user_info.warning_count})"
                )
                return retry_after
            
            # Update user info
            user_info.last_request_time = current_time
            user_info.request_count += 1
            
            return None
    
    async def check_global_rate_limit(self) -> Optional[float]:
        """
        Check if global rate limit is exceeded.
        
        Returns:
            None if allowed, or retry_after seconds if rate limited
        """
        async with self._global_lock:
            current_time = time.time()
            
            # Clean up old requests (older than 1 minute)
            minute_ago = current_time - 60
            self._global_info.request_times = [
                t for t in self._global_info.request_times if t > minute_ago
            ]
            
            # Check if limit exceeded
            if len(self._global_info.request_times) >= self.global_requests_per_minute:
                oldest_in_window = min(self._global_info.request_times)
                retry_after = oldest_in_window + 60 - current_time
                self._global_info.total_blocked += 1
                logger.warning(
                    f"Global rate limit exceeded. "
                    f"Retry after: {retry_after:.1f}s"
                )
                return max(0, retry_after)
            
            # Record this request
            self._global_info.request_times.append(current_time)
            self._global_info.total_requests += 1
            
            return None
    
    async def acquire(self, user_id: int) -> None:
        """
        Acquire permission to make a request.
        
        Checks both user and global rate limits.
        
        Args:
            user_id: Discord user ID
            
        Raises:
            RateLimitException: If rate limited
        """
        # Check user rate limit first
        retry_after = await self.check_user_rate_limit(user_id)
        if retry_after:
            raise RateLimitException(retry_after, "User rate limit exceeded")
        
        # Check global rate limit
        retry_after = await self.check_global_rate_limit()
        if retry_after:
            raise RateLimitException(retry_after, "Global rate limit exceeded")
        
        # Periodic cleanup
        await self._maybe_cleanup()
    
    async def _maybe_cleanup(self) -> None:
        """Perform periodic cleanup of old entries."""
        current_time = time.time()
        
        if current_time - self._last_cleanup > self.cleanup_interval:
            await self._cleanup()
            self._last_cleanup = current_time
    
    async def _cleanup(self) -> None:
        """Clean up old entries to prevent memory leaks."""
        async with self._user_lock:
            # Remove users who haven't made requests in the last hour
            hour_ago = time.time() - 3600
            users_to_remove = [
                user_id for user_id, info in self._user_info.items()
                if info.last_request_time < hour_ago
            ]
            
            for user_id in users_to_remove:
                del self._user_info[user_id]
            
            if users_to_remove:
                logger.debug(f"Cleaned up {len(users_to_remove)} inactive user entries")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get rate limit statistics for a user."""
        info = self._user_info.get(user_id)
        if not info:
            return {
                "request_count": 0,
                "warning_count": 0,
                "last_request_time": None
            }
        
        return {
            "request_count": info.request_count,
            "warning_count": info.warning_count,
            "last_request_time": info.last_request_time
        }
    
    def get_global_stats(self) -> Dict:
        """Get global rate limit statistics."""
        return {
            "requests_last_minute": len(self._global_info.request_times),
            "total_requests": self._global_info.total_requests,
            "total_blocked": self._global_info.total_blocked,
            "limit_per_minute": self.global_requests_per_minute
        }
    
    def reset_user(self, user_id: int) -> bool:
        """Reset rate limit for a specific user."""
        if user_id in self._user_info:
            del self._user_info[user_id]
            logger.info(f"Reset rate limit for user {user_id}")
            return True
        return False
    
    def reset_all(self) -> None:
        """Reset all rate limits."""
        self._user_info.clear()
        self._global_info = GlobalRateInfo()
        logger.info("All rate limits reset")
    
    def update_config(self, user_cooldown: float = None, global_requests_per_minute: int = None) -> None:
        """Update rate limiter configuration."""
        if user_cooldown is not None:
            self.user_cooldown = user_cooldown
        if global_requests_per_minute is not None:
            self.global_requests_per_minute = global_requests_per_minute
        
        logger.info(
            f"RateLimiter config updated: "
            f"user_cooldown={self.user_cooldown}s, "
            f"global_limit={self.global_requests_per_minute}/min"
        )
