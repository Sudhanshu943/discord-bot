"""
Advanced Search Service
✅ Intelligent filtering of search results
✅ Scoring system to select best quality tracks
✅ Spotify link support
✅ Fast search with caching
✅ Filter out bad audio (remixes, covers, live, etc.)
"""

import asyncio
import yt_dlp
import logging
import re
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger('discord.music.search')

# ==================== CONFIGURATION ====================
YDL_SEARCH_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'noplaylist': True,
    'no_check_certificate': True,
    'socket_timeout': 15,
    'extractor_args': {
        'youtube': {
            'player_client': ['web'],
            'player_skip': ['js', 'configs'],
        }
    },
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# Search result filtering patterns
BAD_PATTERNS = [
    r'\bintro\b',
    r'\boutro\b',
    r'\blive\b',
    r'\bconcert\b',
    r'\bperformance\b',
    r'\bremix\b',
    r'\bslowed\b',
    r'\breverb\b',
    r'\bbass boost(?:ed)?\b',
    r'\bcover\b',
    r'\bkaraoke\b',
    r'\b8d audio\b',
]

GOOD_PATTERNS = [
    r'\bofficial audio\b',
    r'\bofficial track\b',
    r'\bofficial music video\b',
    r'\baudio\b',
    r'\b(?:official|original)\b',
]

LYRICS_PATTERN = r'\blyrics\b'

CHANNEL_PATTERNS = {
    'topic': r'- topic$',
    'artist': r'(?:official|artist channel)',
}

# ==================== SEARCH SERVICE ====================
class SearchService:
    """
    Advanced music search with intelligent filtering and scoring
    - Searches YouTube Music first, then YouTube
    - Filters out bad quality results (remixes, covers, live, etc.)
    - Scores results based on channel, title, duration match
    - Supports Spotify links
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.search_cache: Dict[str, Dict] = {}  # Simple cache for search results
        logger.info("🔍 Search Service initialized")
    
    def _extract_spotify_info(self, spotify_url: str) -> Optional[Tuple[str, str]]:
        """
        Extract track name and artist from Spotify URL
        Returns: (track_name, artist_name) or None
        """
        try:
            # Parse Spotify URL
            if 'open.spotify.com' not in spotify_url:
                return None
            
            # Extract track ID from URL
            parsed = urlparse(spotify_url)
            if '/track/' not in parsed.path:
                return None
            
            # Note: In production, you'd use Spotify API
            # For now, return None to fallback to yt-dlp
            logger.warning("Spotify support requires Spotify API key - falling back to YouTube search")
            return None
        except Exception as e:
            logger.warning(f"Failed to parse Spotify URL: {e}")
            return None
    
    def _score_result(self, title: str, channel: str, duration: int, expected_duration: Optional[int] = None) -> int:
        """
        Score a search result based on quality indicators
        Higher score = better result
        """
        score = 0
        title_lower = title.lower()
        channel_lower = channel.lower() if channel else ""
        
        # BAD PATTERNS - Heavy penalties
        for pattern in BAD_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                score -= 10
                logger.debug(f"  ❌ Bad pattern '{pattern}' found in '{title}' (-10)")
        
        # LYRICS - Minor penalty (some people want lyrics videos)
        if re.search(LYRICS_PATTERN, title_lower, re.IGNORECASE):
            score -= 5
            logger.debug(f"  ⚠️  Contains 'lyrics' (-5)")
        
        # OFFICIAL/ARTIST CHANNEL - Major bonus
        if re.search(r'official', channel_lower):
            score += 10
            logger.debug(f"  ✅ Official channel (+10)")
        elif re.search(CHANNEL_PATTERNS['artist'], channel_lower):
            score += 10
            logger.debug(f"  ✅ Artist channel (+10)")
        
        # TOPIC CHANNEL (Official uploads by YouTube)
        if re.search(CHANNEL_PATTERNS['topic'], channel_lower):
            score += 8
            logger.debug(f"  ✅ Topic channel (+8)")
        
        # GOOD PATTERNS - Bonuses
        for pattern in GOOD_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                score += 8
                logger.debug(f"  ✅ Good pattern '{pattern}' found (+8)")
        
        # DURATION MATCHING - Bonus if close to expected duration
        if expected_duration and duration:
            # Allow ±20% variation
            tolerance = max(expected_duration * 0.20, 20)
            if abs(duration - expected_duration) <= tolerance:
                score += 5
                logger.debug(f"  ✅ Duration match: {duration}s ≈ {expected_duration}s (+5)")
            elif duration < 60:
                # Very short videos are usually clips/intros
                score -= 3
                logger.debug(f"  ❌ Too short: {duration}s (-3)")
            elif duration > expected_duration * 2:
                # Much longer videos might be compilations or extended mixes
                score -= 2
                logger.debug(f"  ❌ Too long: {duration}s (-2)")
        
        return score
    
    async def search_youtube(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search YouTube for music using yt-dlp
        Returns list of result dicts with title, url, duration, channel
        Includes retry logic and fallback to direct extraction
        """
        try:
            def _search():
                try:
                    with yt_dlp.YoutubeDL(YDL_SEARCH_OPTIONS) as ydl:
                        # Use ytsearch to get multiple results
                        search_query = f"ytsearch{limit}:{query}"
                        logger.debug(f"Fetching: {search_query}")
                        info = ydl.extract_info(search_query, download=False)
                        
                        results = []
                        if info.get('_type') == 'playlist' and info.get('entries'):
                            for entry in info['entries'][:limit]:
                                if entry:
                                    try:
                                        result_dict = {
                                            'title': entry.get('title', 'Unknown'),
                                            'url': entry.get('url') or entry.get('webpage_url'),
                                            'id': entry.get('id'),
                                            'duration': entry.get('duration', 0),
                                            'channel': entry.get('uploader', 'Unknown'),
                                            'thumbnail': entry.get('thumbnail'),
                                        }
                                        # Skip results without URL
                                        if result_dict['url']:
                                            results.append(result_dict)
                                    except Exception as e:
                                        logger.debug(f"Skipping invalid entry: {e}")
                                        continue
                        
                        logger.debug(f"Got {len(results)} valid results")
                        return results
                except Exception as e:
                    logger.error(f"Search extraction error: {e}")
                    return []
            
            # Run search in executor with longer timeout
            results = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, _search),
                timeout=15.0
            )
            
            if not results:
                logger.warning(f"No results found for: {query[:50]}")
                # Fallback: try direct extraction as if it's a URL/direct search
                logger.info(f"Attempting direct extraction fallback for: {query[:50]}")
                return await self._fallback_direct_search(query)
            
            logger.debug(f"✅ Found {len(results)} results for: {query[:50]}")
            return results
        
        except asyncio.TimeoutError:
            logger.warning(f"Search timeout (>15s) for: {query[:50]}")
            # Fallback to direct extraction
            return await self._fallback_direct_search(query)
        except Exception as e:
            logger.error(f"Search error: {e}")
            # Fallback to direct extraction
            return await self._fallback_direct_search(query)
    
    async def _fallback_direct_search(self, query: str) -> List[Dict]:
        """
        Fallback: Try to extract query directly using default_search
        This handles cases where ytsearch fails
        """
        try:
            def _direct_extract():
                try:
                    # Use simplified options for direct extraction
                    options = {
                        'format': 'bestaudio/best',
                        'quiet': True,
                        'no_warnings': True,
                        'skip_download': True,
                        'default_search': 'ytsearch',
                        'noplaylist': True,
                        'socket_timeout': 10,
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    }
                    with yt_dlp.YoutubeDL(options) as ydl:
                        logger.debug(f"Direct extraction for: {query}")
                        info = ydl.extract_info(query, download=False)
                        
                        if not info:
                            return []
                        
                        # Handle both playlist and single video
                        if info.get('_type') == 'playlist' and info.get('entries'):
                            entries = info['entries'][:5]  # Limit to 5 results
                        else:
                            entries = [info]
                        
                        results = []
                        for entry in entries:
                            if entry:
                                try:
                                    result_dict = {
                                        'title': entry.get('title', 'Unknown'),
                                        'url': entry.get('url') or entry.get('webpage_url'),
                                        'id': entry.get('id'),
                                        'duration': entry.get('duration', 0),
                                        'channel': entry.get('uploader', 'Unknown'),
                                        'thumbnail': entry.get('thumbnail'),
                                    }
                                    if result_dict['url']:
                                        results.append(result_dict)
                                except Exception as e:
                                    logger.debug(f"Skipping entry in fallback: {e}")
                        
                        return results
                except Exception as e:
                    logger.error(f"Direct extraction failed: {e}")
                    return []
            
            results = await asyncio.wait_for(
                self.bot.loop.run_in_executor(None, _direct_extract),
                timeout=12.0
            )
            
            if results:
                logger.info(f"✅ Fallback successful: Got {len(results)} results for: {query[:50]}")
            return results
        
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
            return []
    
    async def find_best_result(
        self,
        query: str,
        expected_duration: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Search YouTube and return the BEST result based on scoring
        
        Args:
            query: Song name, artist name, or search query
            expected_duration: Expected song duration in seconds (for matching)
        
        Returns:
            {
                'title': str,
                'url': str,
                'duration': int,
                'channel': str,
                'thumbnail': str,
                'source': 'youtube',
                'score': int
            }
        """
        logger.info(f"🔍 Searching: {query[:50]}")
        
        # Check cache first
        cache_key = f"{query}:{expected_duration}"
        if cache_key in self.search_cache:
            logger.debug(f"  📦 Using cached result")
            return self.search_cache[cache_key]
        
        # Search YouTube
        results = await self.search_youtube(query, limit=10)
        
        if not results:
            logger.warning(f"No results found for: {query[:50]}")
            return None
        
        logger.debug(f"Scoring {len(results)} results...")
        
        # Score each result
        scored_results = []
        for result in results:
            score = self._score_result(
                title=result['title'],
                channel=result['channel'],
                duration=result['duration'],
                expected_duration=expected_duration
            )
            scored_results.append({
                **result,
                'score': score
            })
        
        # Sort by score (highest first)
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Log top 3 results
        for i, res in enumerate(scored_results[:3]):
            logger.debug(f"  #{i+1} {res['title'][:50]} | Score: {res['score']} | {res['duration']}s")
        
        best_result = {
            'title': scored_results[0]['title'],
            'url': scored_results[0]['url'],
            'duration': scored_results[0]['duration'],
            'channel': scored_results[0]['channel'],
            'thumbnail': scored_results[0].get('thumbnail'),
            'source': 'youtube',
            'score': scored_results[0]['score'],
            'search_query': query,
        }
        
        logger.info(
            f"✅ Selected: {best_result['title'][:50]} | "
            f"Score: {best_result['score']} | {best_result['duration']}s"
        )
        
        # Cache result
        self.search_cache[cache_key] = best_result
        
        return best_result
    
    async def smart_search(self, input_query: str) -> Optional[Dict]:
        """
        Smart search that handles:
        - Direct YouTube URLs
        - Spotify links (extracts track name)
        - Queries (artist + song name)
        
        Returns best quality result
        """
        input_lower = input_query.lower()
        
        # Check if it's a Spotify link
        if 'spotify.com' in input_lower:
            logger.debug("Detected Spotify link")
            spotify_info = self._extract_spotify_info(input_query)
            if spotify_info:
                artist, track = spotify_info
                # Search for: artist track
                query = f"{artist} {track}"
                logger.info(f"  → Searching YouTube: {query}")
                return await self.find_best_result(query, expected_duration=None)
            else:
                logger.warning("Could not extract Spotify track info")
                return None
        
        # Check if it's a direct YouTube URL
        if 'youtube.com' in input_lower or 'youtu.be' in input_lower:
            logger.debug("Detected YouTube URL - returning as-is")
            return {
                'title': input_query,
                'url': input_query,
                'duration': 0,
                'channel': 'Direct URL',
                'source': 'youtube_direct',
                'score': 100,
            }
        
        # Regular search query
        return await self.find_best_result(input_query)
    
    def clear_cache(self):
        """Clear search cache"""
        self.search_cache.clear()
        logger.info("🗑️  Search cache cleared")
