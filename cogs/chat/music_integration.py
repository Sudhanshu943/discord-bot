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
from typing import List, Optional, Dict, Any
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
    
    def __init__(self, bot):
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
        
        # Extract genres
        genre_patterns = [
            r'(?:like|love|enjoy|listen to) (?:music from )?(.*?)(?: music| songs|$)',
            r'(?:favorite|preferred) (?:genre|genres) is (.*?)(?:\.|$)',
            r'(.*?) (?:music|songs) (?:are|is) my favorite'
        ]
        
        for pattern in genre_patterns:
            match = re.search(pattern, message.lower())
            if match:
                genres = self._extract_keywords(match.group(1))
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
                artists = self._extract_keywords(match.group(1))
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
                moods = self._extract_keywords(match.group(1))
                for mood in moods:
                    if mood not in preference.preferred_moods:
                        preference.preferred_moods.append(mood)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        # Remove common stop words and punctuation
        stop_words = ['the', 'a', 'an', 'some', 'for', 'to', 'about']
        text = re.sub(r'[^\w\s]', '', text.lower())
        words = text.split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords
    
    async def recommend_songs(self, user_id: int, context: str = "", mood: str = None) -> List[str]:
        """
        Recommend songs based on user preferences and context
        Returns list of song search queries
        """
        preference = await self.get_or_create_preference(user_id)
        recommendations = []
        
        # Get genre recommendations based on mood or user preferences
        target_mood = mood
        if not target_mood:
            # Try to detect mood from context
            target_mood = await self._detect_mood(context)
        
        # Get genres for mood
        if target_mood and target_mood in self.MOOD_GENRE_MAPPING:
            mood_genres = self.MOOD_GENRE_MAPPING[target_mood]
            # Find intersection with user's favorite genres
            preferred_genres = set(preference.favorite_genres) & set(mood_genres)
            if preferred_genres:
                # Recommend popular songs from preferred genres
                for genre in preferred_genres:
                    if genre in self.POPULAR_SONGS:
                        recommendations.extend(self.POPULAR_SONGS[genre])
        
        # If no mood-based recommendations, use favorite artists
        if not recommendations and preference.favorite_artists:
            for artist in preference.favorite_artists[:3]:  # Limit to top 3
                # Recommend popular songs by artist (or just artist name for search)
                recommendations.append(f"{artist} songs")
        
        # Fallback to random popular songs if no preferences
        if not recommendations:
            all_songs = []
            for genre_songs in self.POPULAR_SONGS.values():
                all_songs.extend(genre_songs)
            recommendations = random.sample(all_songs, min(3, len(all_songs)))
        
        return recommendations
    
    async def _detect_mood(self, text: str) -> Optional[str]:
        """Detect mood from text using keywords"""
        mood_keywords = {
            'happy': ['happy', 'joyful', 'excited', 'cheerful', 'upbeat'],
            'sad': ['sad', 'depressed', 'melancholy', 'blue', 'heartbroken'],
            'energetic': ['energetic', 'hyped', 'pumped', 'excited', 'active'],
            'calm': ['calm', 'relaxed', 'peaceful', 'mellow', 'chill'],
            'romantic': ['romantic', 'love', 'loving', 'affectionate'],
            'party': ['party', 'dance', 'celebrate', 'festive']
        }
        
        text = text.lower()
        for mood, keywords in mood_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return mood
        return None
    
    async def create_playlist(self, user_id: int, theme: str, num_songs: int = 5) -> List[str]:
        """Create a playlist based on a theme"""
        # First, try to recommend songs based on theme
        theme_recommendations = await self.recommend_songs(user_id, context=theme)
        
        # If not enough recommendations, add theme-specific songs
        if len(theme_recommendations) < num_songs:
            # Add theme-based search queries
            additional_songs = [
                f"{theme} music",
                f"{theme} songs",
                f"best {theme} songs",
                f"top {theme} music"
            ]
            theme_recommendations.extend(additional_songs)
        
        return theme_recommendations[:num_songs]
    
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
    
    async def get_music_player(self, guild: discord.Guild):
        """Get the music player from the music cog"""
        music_cog = self.bot.get_cog('Music')
        if music_cog:
            return music_cog.player_manager.get_player(guild)
        return None
    
    async def search_and_play(self, ctx, query: str):
        """Search for a song and add to queue"""
        music_cog = self.bot.get_cog('Music')
        if not music_cog:
            return False, "Music player not available"
        
        try:
            # Get player
            player = music_cog.player_manager.get_player(ctx.guild)
            
            # Connect to voice channel if not connected
            if not player.voice_client:
                if not ctx.author.voice:
                    return False, "You're not in a voice channel!"
                
                success = await player.connect(ctx.author.voice.channel)
                if not success:
                    return False, "Failed to join voice channel!"
            
            # Search for the song
            tracks, platform, is_playlist = await music_cog.search_manager.search(query, limit=1, extract_audio=False)
            if tracks:
                await music_cog._handle_single_track(ctx, tracks[0], player)
                return True, f"Added '{tracks[0]['title']}' to queue!"
            else:
                return False, "No matching song found!"
                
        except Exception as e:
            logger.error(f"Error playing song: {e}")
            return False, f"Error playing song: {e}"
