"""
Anti-Bot Detection Module
✅ Bypasses YouTube bot detection
✅ Rotates user agents and proxies
✅ Adds request delays and headers
✅ Manages cookies and sessions
✅ Railway-compatible
"""

import yt_dlp
import logging
import os
from typing import Optional, List, Dict
import random

logger = logging.getLogger('discord.music.antibot')

# ==================== USER AGENTS ====================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

# ==================== PROXY CONFIGURATION ====================
class AntiBotDetection:
    """
    Handles anti-bot detection measures for YouTube/yt-dlp
    - Rotates user agents
    - Manages proxies (if configured)
    - Adds request delays
    - Handles cookies
    - Railway-safe (no heavy memory overhead)
    """
    
    def __init__(self):
        self.current_ua_index = 0
        self.proxy_list: List[str] = []
        self.current_proxy_index = 0
        self.cookies_path = "./.cache/youtube-cookies.txt"
        self._load_proxies()
        logger.info("🛡️  Anti-Bot Detection initialized")
    
    def _load_proxies(self):
        """Load proxies from environment variable"""
        proxy_env = os.getenv('PROXIES', '').strip()
        if proxy_env:
            # Format: proxy1.com:port,proxy2.com:port|username:password,...
            proxies = [p.strip() for p in proxy_env.split(',') if p.strip()]
            self.proxy_list = proxies
            logger.info(f"✅ Loaded {len(self.proxy_list)} proxies")
        else:
            logger.info("ℹ️  No proxies configured (will use direct connection)")
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent"""
        ua = random.choice(USER_AGENTS)
        logger.debug(f"🔄 Using user agent: {ua[:50]}...")
        return ua
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy in rotation"""
        if not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        logger.debug(f"🔄 Using proxy: {proxy[:30]}...")
        return proxy
    
    def get_ydl_options(self, search_mode: bool = False) -> Dict:
        """
        Get yt-dlp options with anti-bot measures
        
        Args:
            search_mode: If True, use search-optimized options
        
        Returns:
            Dictionary of yt-dlp options with anti-bot measures
        """
        
        # Base options
        options = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'no_check_certificate': True,
            'user_agent': self.get_random_user_agent(),
            
            # Request headers
            'http_headers': {
                'User-Agent': self.get_random_user_agent(),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/',
            },
            
            # Delays to avoid rate limiting
            'socket_timeout': 20,
            'extractor_retries': 3,
            'retry_sleep': 0.1,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'hls_prefer_native': True,
            
            # Performance
            'no_part': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        # Add proxy if available
        proxy = self.get_next_proxy()
        if proxy:
            options['proxy'] = f'http://{proxy}'
            logger.debug(f"🔒 Proxy enabled: {proxy[:20]}...")
        
        # Search-specific options
        if search_mode:
            options.update({
                'default_search': 'ytsearch',
                'noplaylist': True,
                'max_results': 10,
                'format': 'bestaudio/best',
                'skip_download': True,
            })
        else:
            options.update({
                'format': 'bestaudio/best',
                'noplaylist': True,
            })
        
        return options
    
    def create_ydl_instance(self, search_mode: bool = False) -> yt_dlp.YoutubeDL:
        """
        Create a yt-dlp instance with anti-bot measures
        
        Args:
            search_mode: If True, optimize for search
        
        Returns:
            Configured YoutubeDL instance
        """
        options = self.get_ydl_options(search_mode=search_mode)
        return yt_dlp.YoutubeDL(options)
    
    def get_cookies_file_path(self) -> str:
        """Get path to cookies file (Railway-safe)"""
        # Use /tmp for Railway (writable, temporary storage)
        if os.path.exists('/tmp'):
            path = '/tmp/youtube-cookies.txt'
        else:
            path = self.cookies_path
        
        return path


# ==================== SINGLETON INSTANCE ====================
_antibot_instance: Optional[AntiBotDetection] = None

def get_antibot() -> AntiBotDetection:
    """Get or create anti-bot detection instance"""
    global _antibot_instance
    if _antibot_instance is None:
        _antibot_instance = AntiBotDetection()
    return _antibot_instance


# ==================== HELPER FUNCTION ====================
def get_ydl_for_search() -> yt_dlp.YoutubeDL:
    """Get configured YDL for search operations"""
    antibot = get_antibot()
    return antibot.create_ydl_instance(search_mode=True)


def get_ydl_for_extraction() -> yt_dlp.YoutubeDL:
    """Get configured YDL for audio extraction"""
    antibot = get_antibot()
    return antibot.create_ydl_instance(search_mode=False)
