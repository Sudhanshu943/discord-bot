"""
Stream Preloader - Background Song Extraction & Metadata Loading
✅ Preloads next song while current plays
✅ Extracts audio URLs in background
✅ Never blocks playback
✅ Error recovery built-in
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
import yt_dlp

logger = logging.getLogger('discord.music.preloader')

# ==================== STREAM PRELOADER ====================
class StreamPreloader:
    """
    Handles background extraction and preloading of songs
    - Extracts audio URLs while playback continues
    - Detects failures early
    - Caches results for fast replay
    """
    
    def __init__(
        self,
        ydl_opts: Optional[Dict[str, Any]] = None,
        extration_timeout: float = 10.0,
        cache_size: int = 50
    ):
        self.ydl_opts = ydl_opts or {}
        self.extraction_timeout = extration_timeout
        
        # Extraction cache: url -> audio_url
        self.cache: Dict[str, Optional[str]] = {}
        self.cache_size = cache_size
        
        # Active extraction tasks: url -> Task
        self.extraction_tasks: Dict[str, asyncio.Task] = {}
        
        # Error tracking: url -> error_count
        self.error_counts: Dict[str, int] = {}
        self.max_retries = 3
    
    async def preload_song(
        self,
        song_url: str,
        loop: asyncio.AbstractEventLoop
    ) -> Optional[str]:
        """
        Preload song audio URL
        Returns: audio_url or None
        """
        # Check cache first
        if song_url in self.cache:
            logger.debug(f"Cache hit for: {song_url[:50]}")
            return self.cache[song_url]
        
        # Check if already extracting
        if song_url in self.extraction_tasks:
            logger.debug(f"Already extracting: {song_url[:50]}")
            try:
                return await asyncio.wait_for(
                    self.extraction_tasks[song_url],
                    timeout=self.extraction_timeout + 5  # Additional time for ongoing task
                )
            except asyncio.TimeoutError:
                logger.warning(f"Extraction task timeout: {song_url[:50]}")
                return None
        
        # Start new extraction
        return await self._extract_audio_url(song_url, loop)
    
    async def _extract_audio_url(
        self,
        song_url: str,
        loop: asyncio.AbstractEventLoop
    ) -> Optional[str]:
        """Extract audio URL with error handling and retry"""
        error_count = self.error_counts.get(song_url, 0)
        
        if error_count >= self.max_retries:
            logger.error(f"Max retries exceeded for: {song_url[:50]}")
            self.cache[song_url] = None
            return None
        
        try:
            logger.info(f"Extracting audio URL: {song_url[:50]}")
            
            # Create extraction task
            task = asyncio.create_task(
                loop.run_in_executor(
                    None,
                    self._extract_sync,
                    song_url
                )
            )
            self.extraction_tasks[song_url] = task
            
            # Wait with timeout
            audio_url = await asyncio.wait_for(
                task,
                timeout=self.extraction_timeout
            )
            
            # Cache result
            self.cache[song_url] = audio_url
            self.error_counts[song_url] = 0  # Reset error count
            
            if audio_url:
                logger.info(f"✅ Extracted: {song_url[:50]}")
            else:
                logger.warning(f"No audio URL found: {song_url[:50]}")
            
            return audio_url
            
        except asyncio.TimeoutError:
            logger.warning(f"Extraction timeout: {song_url[:50]}")
            self.error_counts[song_url] = error_count + 1
            
            # Final attempt might still complete in background
            self.extraction_tasks[song_url].cancel()
            return None
            
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            self.error_counts[song_url] = error_count + 1
            self.extraction_tasks.pop(song_url, None)
            return None
        finally:
            self.extraction_tasks.pop(song_url, None)
    
    def _extract_sync(self, song_url: str) -> Optional[str]:
        """Synchronous extraction (runs in executor)"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(song_url, download=False)
                
                # Handle search results
                if info.get('_type') == 'playlist' and info.get('entries'):
                    info = info['entries'][0]
                
                # Extract audio URL
                audio_url = self._get_best_audio(info)
                return audio_url
        except Exception as e:
            logger.error(f"Sync extraction failed: {e}")
            return None
    
    def _get_best_audio(self, info: Dict[str, Any]) -> Optional[str]:
        """Get best audio URL from info"""
        # Direct URL
        if info.get('url') and isinstance(info['url'], str):
            url = str(info['url']).strip()
            if url.startswith('http'):
                return url
        
        # Check formats
        if info.get('formats'):
            # Prefer audio-only
            for fmt in info['formats']:
                if (fmt.get('acodec') and fmt.get('acodec') != 'none' and
                    (not fmt.get('vcodec') or fmt.get('vcodec') == 'none') and
                    fmt.get('url')):
                    return fmt['url']
            
            # Any audio format
            for fmt in info['formats']:
                if fmt.get('acodec') and fmt.get('acodec') != 'none' and fmt.get('url'):
                    return fmt['url']
        
        return None
    
    def get_cached(self, song_url: str) -> Optional[str]:
        """Get cached URL without extraction"""
        return self.cache.get(song_url)
    
    def clear_cache(self) -> None:
        """Clear extraction cache"""
        self.cache.clear()
        self.error_counts.clear()
        logger.info("Extraction cache cleared")
    
    async def cancel_all_extractions(self) -> None:
        """Cancel all pending extraction tasks"""
        for task in self.extraction_tasks.values():
            if not task.done():
                task.cancel()
        
        # Wait for cancellations
        await asyncio.gather(*self.extraction_tasks.values(), return_exceptions=True)
        self.extraction_tasks.clear()
        logger.info("All extraction tasks cancelled")


# ==================== BACKGROUND LOADER ====================
class BackgroundLoader:
    """
    Loads next songs in background while playback continues
    - Monitors queue depth
    - Loads chunks on demand
    - Handles errors gracefully
    """
    
    def __init__(
        self,
        queue_manager,
        preloader: StreamPreloader,
        check_interval: float = 5.0
    ):
        self.queue_manager = queue_manager
        self.preloader = preloader
        self.check_interval = check_interval
        
        # Active loader tasks: guild_id -> Task
        self.loader_tasks: Dict[int, asyncio.Task] = {}
    
    async def start_background_loading(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop
    ) -> None:
        """Start background loader for guild"""
        if guild_id in self.loader_tasks:
            return  # Already running
        
        task = asyncio.create_task(
            self._loader_loop(guild_id, loop)
        )
        self.loader_tasks[guild_id] = task
        logger.info(f"Started background loader for guild {guild_id}")
    
    async def stop_background_loading(self, guild_id: int) -> None:
        """Stop background loader"""
        if guild_id in self.loader_tasks:
            task = self.loader_tasks[guild_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.loader_tasks[guild_id]
            logger.info(f"Stopped background loader for guild {guild_id}")
    
    async def _loader_loop(
        self,
        guild_id: int,
        loop: asyncio.AbstractEventLoop
    ) -> None:
        """Main background loader loop"""
        try:
            while True:
                await asyncio.sleep(self.check_interval)
                
                queue = self.queue_manager.get_queue(guild_id)
                
                # Load next chunk if queue is low
                if queue.is_playing and len(queue.lazy_queue) > 0:
                    if len(queue.queue) <= queue.queue.maxlen // 2:
                        await self.queue_manager.load_next_chunk(guild_id, loop)
                
                # Preload next song's audio URL
                next_song = self.queue_manager.get_next(guild_id)
                if next_song and not next_song.is_extracted and next_song.url:
                    logger.debug(f"Preloading next song: {next_song.title}")
                    audio_url = await self.preloader.preload_song(next_song.url, loop)
                    if audio_url:
                        next_song.audio_url = audio_url
                        next_song.is_extracted = True
        
        except asyncio.CancelledError:
            logger.debug(f"Background loader cancelled for guild {guild_id}")
        except Exception as e:
            logger.error(f"Background loader error: {e}")
