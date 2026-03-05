"""
Music Integration Module for AI Chat
===================================

Handles music recommendation, playlist creation, and integration with the music player.
Features:
- Context-aware song recommendations
- Playlist creation based on user preferences
- Sarcasm detection for playful song additions
- Music player integration
"""

import logging
import re
import random
import json
import asyncio
from typing import List, Optional, Dict, Any, Tuple
import discord
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MusicPreference:
    """Stores user's music preferences"""
    favorite_genres: List[str] = field(default_factory=list)
    favorite_artists: List[str] = field(default_factory=list)
    favorite_songs: List[str] = field(default_factory=list)
    preferred_moods: List[str] = field(default_factory=list)
    last_played_songs: List[str] = field(default_factory=list)


class MusicIntegration:
    """
    Handles music integration for the AI chat system.
    Manages music recommendations, playlist creation, and player interaction.
    """
    
    # Mood to genre/song mapping for recommendations
    MOOD_GENRE_MAPPING = {
        'happy': ['pop', 'dance', 'reggae', 'funk'],
        'sad': ['ballad', 'indie', 'folk', 'classical'],
        'energetic': ['rock', 'metal', 'electronic', 'hip hop'],
        'calm': ['ambient', 'jazz', 'classical', 'lo-fi'],
        'romantic': ['love songs', 'ballad', 'r&b', 'soul'],
        'party': ['dance', 'pop', 'hip hop', 'edm'],
        'focus': ['lo-fi', 'ambient', 'classical', 'jazz']
    }
    
    # Sarcastic/playful song suggestions (for roasting)
    SARCASM_SONGS = [
        "Never Gonna Give You Up - Rick Astley",
        "Despacito - Luis Fonsi",
        "Baby - Justin Bieber",
        "Friday - Rebecca Black",
        "Gangnam Style - PSY",
        "Macarena - Los Del Rio",
        "The Duck Song - Bryant Oden",
        "What Does the Fox Say? - Ylvis",
        "It's a Small World - Disney",
        "Crazy Frog - Axel F"
    ]
    
    # Popular songs by genre for quick recommendations
    POPULAR_SONGS = {
        'pop': ["Blinding Lights - The Weeknd", "Shape of You - Ed Sheeran", "Uptown Funk - Mark Ronson"],
        'rock': ["Bohemian Rhapsody - Queen", "Stairway to Heaven - Led Zeppelin", "Sweet Child O' Mine - Guns N' Roses"],
        'hip hop': ["Lose Yourself - Eminem", "Juice - Lizzo", "Sicko Mode - Travis Scott"],
        'electronic': ["One More Time - Daft Punk", "Levels - Avicii", "Sandstorm - Darude"],
        'classical': ["Für Elise - Beethoven", "Moonlight Sonata - Beethoven", "Canon in D - Pachelbel"]
    }
    
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.user_preferences: Dict[int, MusicPreference] = {}
        logger.info("MusicIntegration initialized")
    
    async def get_or_create_preference(self, user_id: int) -> MusicPreference:
        """Get or create music preferences for a user"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = MusicPreference()
        return self.user_preferences[user_id]
    
    async def update_preferences_from_conversation(self, user_id: int, message: str):
        """Update music preferences based on conversation content"""
        preference = await self.get_or_create_preference(user_id)
        
        # Helper function to extract keywords
        def extract_keywords(text: str) -> List[str]:
            """Extract relevant keywords from text"""
            stop_words = ['the', 'a', 'an', 'some', 'for', 'to', 'about']
            text = re.sub(r'[^\w\s]', '', text.lower())
            words = text.split()
            keywords = [word for word in words if word not in stop_words and len(word) > 2]
            return keywords
        
        # Extract genres
        genre_patterns = [
            r'(?:like|love|enjoy|listen to) (?:music from )?(.*?)(?: music| songs|$)',
            r'(?:favorite|preferred) (?:genre|genres) is (.*?)(?:\.|$)',
            r'(.*?) (?:music|songs) (?:are|is) my favorite'
        ]
        
        for pattern in genre_patterns:
            match = re.search(pattern, message.lower())
            if match:
                genres = extract_keywords(match.group(1))
                for genre in genres:
                    if genre not in preference.favorite_genres:
                        preference.favorite_genres.append(genre)
        
        # Extract artists
        artist_patterns = [
            r'(?:like|love|listen to) (.*?)(?:\'s music| songs|$)',
            r'(?:favorite|preferred) artist is (.*?)(?:\.|$)',
            r'(.*?) is (?:my )?favorite artist'
        ]
        
        for pattern in artist_patterns:
            match = re.search(pattern, message.lower())
            if match:
                artists = extract_keywords(match.group(1))
                for artist in artists:
                    if artist not in preference.favorite_artists:
                        preference.favorite_artists.append(artist)
        
        # Extract moods
        mood_patterns = [
            r'(?:feeling|in the mood for) (.*?)(?: music| songs|$)',
            r'(?:want to listen to )?(.*?) (?:music|songs)'
        ]
        
        for pattern in mood_patterns:
            match = re.search(pattern, message.lower())
            if match:
                moods = extract_keywords(match.group(1))
                for mood in moods:
                    if mood not in preference.preferred_moods:
                        preference.preferred_moods.append(mood)
    

    
    async def get_sarcastic_song(self) -> str:
        """Get a sarcastic/playful song for roasting"""
        return random.choice(self.SARCASM_SONGS)
    
    async def is_music_related(self, message: str) -> bool:
        """Check if message is music-related"""
        music_keywords = [
            'music', 'song', 'playlist', 'play', 'listen', 'artist', 'band',
            'genre', 'melody', 'rhythm', 'tune', 'track', 'album'
        ]
        
        message = message.lower()
        return any(keyword in message for keyword in music_keywords)
    

    def extract_songs_from_json(self, text: str) -> List[str]:
        """
        Extract song names from JSON format responses
        """
        songs = []
        
        # Try to find JSON blocks
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                
                # Check for different JSON formats
                if isinstance(data, dict):
                    # Type 1: songs array
                    if 'songs' in data and isinstance(data['songs'], list):
                        songs.extend(data['songs'])
                    # Type 2: song field
                    if 'song' in data:
                        songs.append(data['song'])
                    # Type 3: query field (for play)
                    if 'query' in data:
                        query = data['query']
                        if query.startswith('>>'):
                            songs.append(query[2:].strip())
                    # Type 4: play_all field
                    if 'play_all' in data:
                        play_all = data['play_all']
                        if play_all.startswith('>>'):
                            songs.append(play_all[2:].strip())
            except json.JSONDecodeError:
                continue
        
        return songs
    
    def extract_songs_from_text(self, text: str) -> List[str]:
        """
        Extract song names from text (both >> format and JSON)
        """
        songs = []
        
        # First try JSON format
        json_songs = self.extract_songs_from_json(text)
        if json_songs:
            return json_songs
        
        # Then try >> format
        song_pattern = r'>>\s*(.+?)(?:\n|$)'
        matches = re.findall(song_pattern, text)
        songs.extend([s.strip() for s in matches])
        
        return songs
    

    async def search_and_play(self, message: discord.Message, query: str):
        """
        Search for a song and add to queue using Music cog completely
        Features:
        - Full player management
        - Pre-extraction for instant playback
        - Playlist support
        - Complete queue handling
        """
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False, "Music player not available"
        
        try:
            # Step 1: Get or create player
            player = music_cog.player_manager.get_player(message.guild)
            player.text_channel = message.channel
            
            # Step 2: Connect to voice channel if not actually connected
            if not player.voice_client or not player.voice_client.is_connected():
                if not message.author.voice:
                    return False, "You're not in a voice channel!"
                
                success = await player.connect(message.author.voice.channel)
                if not success:
                    return False, "Failed to join voice channel! Please try again in a moment."
            
            # Step 3: Search using music cog's search manager
            tracks, platform, is_playlist = await music_cog.search_manager.search(
                query, 
                limit=50,  # Get more results
                extract_audio=False  # Fast mode
            )
            
            if not tracks:
                return False, "No matching song found!"
            
            # Step 4: Handle playlist vs single track using music cog's handlers
            if is_playlist and len(tracks) > 1:
                # Use music cog's playlist handler
                await music_cog._handle_playlist(message, tracks, platform, player)
                return True, f"Added {len(tracks)} tracks from playlist!"
            else:
                # Use music cog's single track handler with pre-extraction
                await music_cog._handle_single_track(message, tracks[0], player, pre_extract=True)
                return True, f"Added '{tracks[0]['title']}' to queue!"
                
        except Exception as e:
            logger.error(f"Error playing song: {e}")
            return False, f"Error playing song: {e}"
    
    async def pause_music(self, guild: discord.Guild) -> bool:
        """Pause current playback"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        if player.is_playing:
            await player.pause()
            return True
        return False
    
    async def resume_music(self, guild: discord.Guild) -> bool:
        """Resume playback"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        if player.is_paused:
            await player.resume()
            return True
        return False
    
    async def skip_song(self, guild: discord.Guild) -> bool:
        """Skip current song"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        if player.is_playing:
            await player.skip()
            return True
        return False
    
    async def stop_music(self, guild: discord.Guild) -> bool:
        """Stop playback and clear queue"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        await player.stop()
        return True
    
    async def get_current_song(self, guild: discord.Guild) -> Optional[dict]:
        """Get currently playing song info"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return None
        
        player = music_cog.player_manager.get_player(guild)
        if player.current:
            return {
                'title': player.current.title,
                'url': player.current.url,
                'duration': player.current.duration,
                'thumbnail': player.current.thumbnail,
                'position': player.current.position
            }
        return None
    
    async def get_queue(self, guild: discord.Guild, limit: int = 10) -> List[dict]:
        """Get upcoming songs in queue"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return []
        
        player = music_cog.player_manager.get_player(guild)
        queue_songs = []
        
        for idx, song in enumerate(player.queue[:limit], 1):
            queue_songs.append({
                'position': idx,
                'title': song.title,
                'url': song.url,
                'duration': song.duration,
                'requester': song.requester.name if song.requester else 'Unknown'
            })
        
        return queue_songs
    
    async def set_volume(self, guild: discord.Guild, volume: int) -> bool:
        """Set player volume (0-100)"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        volume = max(0, min(100, volume))  # Clamp between 0-100
        await player.set_volume(volume)
        return True
    
    async def disconnect_player(self, guild: discord.Guild) -> bool:
        """Disconnect from voice channel"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        await music_cog.player_manager.disconnect(guild)
        return True
    
    def is_music_playing(self, guild: discord.Guild) -> bool:
        """Check if music is currently playing"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False
        
        player = music_cog.player_manager.get_player(guild)
        return player.is_playing
    
    # ==================== MOOD-BASED AUTO-PLAYLIST SYSTEM ====================
    
    async def detect_mood_from_message(self, message: str) -> Optional[str]:
        """
        Detect mood/emotion from user message - STRICT MODE
        English + Hindi (Hinglish) support
        Returns mood string or None
        """
        message_lower = message.lower()
        
        # Direct mood phrases - strongest indicators (English + Hindi/Hinglish)
        direct_mood_phrases = {
            'happy': [
                # English
                r'\bhappy\b', r'\bfeeling\s+great\b', r'\bgood\s+mood\b', 
                r'\bfeeling\s+good\b', r'\bfeeling\s+awesome\b',
                # Hindi/Hinglish
                r'\bkhush\b', r'\baccha\s+mood\b', r'\bacchi\s+mood\b', 
                r'\bmast\b', r'\bbadhiya\b', r'\bshandar\b'
            ],
            'sad': [
                # English
                r'\bsad\b', r'\bfeeling\s+sad\b', r'\bdepressed\b', r'\bdown\b', r'\bunhappy\b',
                # Hindi/Hinglish
                r'\budaas\b', r'\bdikhta\s+nahi\b', r'\bniraash\b', r'\buzaar\s+hoon\b'
            ],
            'energetic': [
                # English
                r'\benergetic\b', r'\bhyped\b', r'\bpumped\s+up\b', r'\bfired\s+up\b', 
                r'\bhave\s+energy\b',
                # Hindi/Hinglish
                r'\bcharhi\b', r'\benergy\s+full\b'
            ],
            'calm': [
                # English
                r'\bcalm\b', r'\brelaxed\b', r'\bneeding\s+calm\b', r'\bneed\s+peace\b', 
                r'\bchill\s+out\b',
                # Hindi/Hinglish
                r'\bshaant\b', r'\bshanti\b', r'\bchila\b'
            ],
            'romantic': [
                # English
                r'\bromantic\b', r'\bin\s+love\b', r'\blove\s+song\b', r'\bdate\s+night\b',
                # Hindi/Hinglish
                r'\bpremi\s+mood\b', r'\blove\s+mode\b', r'\brumanch\b'
            ],
            'party': [
                # English
                r'\bparty\b', r'\bparty\s+mode\b', r'\bdance\b', r'\bcelebrate\b', 
                r'\bcelebrating\b',
                # Hindi/Hinglish
                r'\bmauj\b', r'\bjalsa\b', r'\bpaarty\b'
            ],
            'focus': [
                # English
                r'\bfocus\b', r'\bfocusing\b', r'\bconcentrate\b', r'\bworking\b', 
                r'\bstudy.*music\b',
                # Hindi/Hinglish
                r'\bpadhai\b', r'\bkaam\s+mode\b', r'\bfocus\s+mode\b'
            ]
        }
        
        import re
        
        # Check for direct mood phrases first (strongest signal)
        for mood, patterns in direct_mood_phrases.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.info(f"🎵 Detected mood (direct): {mood}")
                    return mood
        
        return None
    
    async def suggest_songs_by_mood(self, mood: str, count: int = 5) -> List[str]:
        """
        Generate song suggestions based on detected mood
        Returns list of song search queries
        """
        if mood not in self.MOOD_GENRE_MAPPING:
            return []
        
        suggestions = []
        genres = self.MOOD_GENRE_MAPPING[mood]
        
        # Mood-specific song suggestions
        mood_songs = {
            'happy': [
                "Levitating - Dua Lipa",
                "Walking on Sunshine - Katrina & The Waves",
                "Good As Hell - Lizzo",
                "Don't Stop Me Now - Queen",
                "Walking in the Sun - Vampire Weekend"
            ],
            'sad': [
                "Someone Like You - Adele",
                "Hurt - Johnny Cash",
                "The Night We Met - Lord Huron",
                "Skinny Love - Bon Iver",
                "Creep - Radiohead"
            ],
            'energetic': [
                "Kick It - NCT 127",
                "Blinding Lights - The Weeknd",
                "Thunder - Imagine Dragons",
                "Pump It - The Black Eyed Peas",
                "Eye of the Tiger - Survivor"
            ],
            'calm': [
                "Weightless - Marconi Union",
                "Clair de Lune - Debussy",
                "Lo-Fi Hip Hop - Various Artists",
                "Peaceful Piano - Spotify Playlist",
                "Brian Eno - Music for Airports"
            ],
            'romantic': [
                "Perfect - Ed Sheeran",
                "All of Me - John Legend",
                "Thinking Out Loud - Ed Sheeran",
                "Kiss Me - Sixpence None The Richer",
                "Best Day of My Life - American Authors"
            ],
            'party': [
                "Uptown Funk - Mark Ronson ft. Bruno Mars",
                "Shut Up and Dance - Walk the Moon",
                "Don't You Worry Child - Swedish House Mafia",
                "Mr. Brightside - The Killers",
                "Crazy in Love - Beyoncé"
            ],
            'focus': [
                "Lo-Fi Hip Hop Study Beats - Chilled Cow",
                "Deep Focus - Spotify",
                "Work from Home - Productivity Playlist",
                "Peaceful Study Music - Ambient",
                "Focus Beats - Electronic"
            ]
        }
        
        if mood in mood_songs:
            suggestions = mood_songs[mood][:count]
        
        logger.info(f"💡 Suggested {len(suggestions)} songs for mood: {mood}")
        return suggestions
    
    async def search_songs_parallel(self, message: discord.Message, song_queries: List[str], timeout: int = 5) -> List[dict]:
        """
        Search for multiple songs in PARALLEL using asyncio.gather
        Critical optimization: all searches happen simultaneously
        
        Args:
            message: Discord message context
            song_queries: List of song search queries
            timeout: Max seconds to wait for all searches
            
        Returns:
            List of track info dicts
        """
        if not song_queries:
            return []
        
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            logger.error("Music cog not available")
            return []
        
        logger.info(f"🔍 Starting PARALLEL search for {len(song_queries)} songs...")
        start_time = asyncio.get_event_loop().time()
        
        # Create search tasks for all songs simultaneously
        search_tasks = []
        for query in song_queries:
            task = music_cog.search_manager.search(
                query,
                limit=1,
                extract_audio=False
            )
            search_tasks.append(task)
        
        try:
            # Wait for ALL searches to complete in parallel (not sequential!)
            results = await asyncio.wait_for(
                asyncio.gather(*search_tasks, return_exceptions=True),
                timeout=timeout
            )
            
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"⚡ Parallel search completed in {elapsed:.2f}s")
            
            # Process results
            found_tracks = []
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Search {idx+1} failed: {result}")
                    continue
                
                tracks, platform, is_playlist = result
                if tracks:
                    found_tracks.append({
                        'title': tracks[0]['title'],
                        'url': tracks[0]['url'],
                        'duration': tracks[0]['duration'],
                        'thumbnail': tracks[0]['thumbnail'],
                        'platform': platform
                    })
                else:
                    logger.warning(f"No results for query: {song_queries[idx]}")
            
            logger.info(f"✅ Found {len(found_tracks)}/{len(song_queries)} songs")
            return found_tracks
            
        except asyncio.TimeoutError:
            logger.error(f"Parallel search timed out after {timeout}s")
            return []
        except Exception as e:
            logger.error(f"Error in parallel search: {e}")
            return []
    
    async def auto_queue_mood_playlist(self, message: discord.Message, mood: str, mood_songs: List[dict]) -> Tuple[bool, str]:
        """
        Automatically queue multiple songs and start playback
        
        Args:
            message: Discord message context
            mood: Mood name
            mood_songs: List of found track dicts
            
        Returns:
            (success, response_message)
        """
        if not mood_songs:
            return False, "❌ No songs found for this mood"
        
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False, "🎵 Music player not available"
        
        try:
            # Import Song class from music cog
            from ...music.logic.player_manager import Song
            
            player = music_cog.player_manager.get_player(message.guild)
            player.text_channel = message.channel
            
            # Connect to voice if needed - check if actually connected
            if not player.voice_client or not player.voice_client.is_connected():
                if not message.author.voice:
                    return False, "❌ You're not in a voice channel!"
                
                success = await player.connect(message.author.voice.channel)
                if not success:
                    return False, "❌ Failed to join your voice channel! Please try again in a moment."
            
            # Check if currently playing
            is_playing = player.is_playing
            
            # Add all songs to queue
            for track in mood_songs:
                song = Song(
                    source="pending",
                    title=track['title'],
                    url=track['url'],
                    duration=track['duration'],
                    thumbnail=track['thumbnail'],
                    requester=message.author
                )
                await player.add_to_queue(song)
            
            # Auto-play if nothing is playing
            if not is_playing and player.queue:
                logger.info("▶️ Starting auto-playback...")
            
            mood_emoji = {
                'happy': '😊',
                'sad': '😢',
                'energetic': '⚡',
                'calm': '🧘',
                'romantic': '💕',
                'party': '🎉',
                'focus': '📚'
            }.get(mood, '🎵')
            
            response = f"{mood_emoji} Added **{len(mood_songs)} {mood} songs** to queue!\n"
            response += f"🎵 Now queueing..."
            
            return True, response
            
        except Exception as e:
            logger.error(f"Error queuing mood playlist: {e}")
            return False, f"❌ Error: {str(e)[:50]}"
    
    async def play_mood_playlist(self, message: discord.Message, ai_context: str = "") -> Tuple[bool, str]:
        """
        Complete flow: Detect mood → Suggest songs → Search → Queue → Play
        All in 1-2 seconds!
        
        Args:
            message: Discord message
            ai_context: Optional AI analysis context
            
        Returns:
            (success, response_message)
        """
        start_time = asyncio.get_event_loop().time()
        
        # Step 1: Detect mood from message
        mood = await self.detect_mood_from_message(message.content)
        if not ai_context:
            ai_context = message.content
        
        if not mood:
            return False, "🤔 Couldn't detect a mood. Try: 'I'm happy', 'I'm sad', 'I need to focus', etc."
        
        logger.info(f"📊 Mood detected: {mood}")
        
        # Step 2: Generate song suggestions
        suggestions = await self.suggest_songs_by_mood(mood, count=5)
        if not suggestions:
            return False, f"❌ No suggestions available for {mood} mood"
        
        logger.info(f"💡 Generated {len(suggestions)} suggestions")
        
        # Step 3: PARALLEL search all songs
        found_tracks = await self.search_songs_parallel(message, suggestions, timeout=5)
        if not found_tracks:
            return False, "❌ Could not find songs. Try again later."
        
        # Step 4: Queue all songs
        success, queue_response = await self.auto_queue_mood_playlist(message, mood, found_tracks)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"⏱️  Complete mood playlist flow took {elapsed:.2f}s")
        
        if success:
            return True, queue_response + f"\n⏱️ Setup in {elapsed:.2f}s"
        else:
            return success, queue_response
