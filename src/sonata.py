import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv

def bot_on():
    load_dotenv()
    token = os.getenv("discord_token")
    client_intents = discord.Intents.default()
    client_intents.message_content = True
    sonata_client = discord.Client(intents=client_intents)

    voice_clients = {}
    queues = {}  # song queues for each guild
    current_songs = {}  # storing current song for each guild
    audio_players = {}  # preloaded audio players for each guild
    
    # optimized ytdl options for faster streaming
    ytdl_options = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=720]",  # prefer audio, fallback to lower quality video
        "noplaylist": True,
        "extract_flat": False,
        "quiet": True,
        "no_warnings": True,
        "prefer_insecure": False,  # use HTTPS when possible for faster connections
        "socket_timeout": 30,      # faster timeout for quicker failures
        "fragment_retries": 3      # fewer retries for faster error handling
    }
    ytdl = yt_dlp.YoutubeDL(ytdl_options)

    # optimized ffmpeg options for faster streaming
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -fflags +discardcorrupt",
        "options": "-vn -bufsize 1024k -maxrate 192k -ac 2 -ar 48000"
    }

    async def preload_audio_player(song_info):
        """Preload audio player asynchronously"""
        loop = asyncio.get_event_loop()
        try:
            audio_player = await loop.run_in_executor(
                None, 
                lambda: discord.FFmpegOpusAudio(song_info["url"], **ffmpeg_options)
            )
            return audio_player
        except Exception as e:
            print(f"Error preloading audio: {e}")
            return None

    def play_next_song(guild_id):
        """Play the next song in the queue"""
        if guild_id in queues and queues[guild_id]:
            song_info = queues[guild_id].pop(0)
            current_songs[guild_id] = song_info
            
            # use preloaded player if available, otherwise create new one
            if guild_id in audio_players and audio_players[guild_id]:
                song_player = audio_players[guild_id].pop(0)
            else:
                # fallback: create player synchronously (slower)
                song_player = discord.FFmpegOpusAudio(song_info["url"], **ffmpeg_options)
            
            voice_clients[guild_id].play(song_player, after=lambda e: play_next_song(guild_id) if e is None else None)
        else:
            # queue is empty, clear current song
            if guild_id in current_songs:
                del current_songs[guild_id]

    @sonata_client.event
    async def on_ready():
        print(f"{sonata_client.user} is now ready")

    @sonata_client.event
    async def on_message(message):
        if message.content.startswith("!play"):
            try:
                bot_voice_client = await message.author.voice.channel.connect()
                voice_clients[bot_voice_client.guild.id] = bot_voice_client
            except Exception as e:
                print(e)

            try:
                # incase of space between message and link
                song_url = message.content.split()[1]

                # allows the bot to run and play music at the same time as other things
                loop = asyncio.get_event_loop()

                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_url, download=False))

                # get song information
                song_title = data.get("title", "Unknown Title")
                song_artist = data.get("uploader", "Unknown Artist")
                song_url_audio = data["url"]
                
                song_info = {
                    "title": song_title,
                    "artist": song_artist,
                    "url": song_url_audio
                }

                # init queue if it doesn't exist
                if message.guild.id not in queues:
                    queues[message.guild.id] = []

                # add song to queue
                queues[message.guild.id].append(song_info)

                # preload audio player for faster playback
                audio_player = await preload_audio_player(song_info)
                if audio_player:
                    if message.guild.id not in audio_players:
                        audio_players[message.guild.id] = []
                    audio_players[message.guild.id].append(audio_player)

                # if nothing is playing, start playing immediately
                voice_client = voice_clients.get(message.guild.id)
                if voice_client and not voice_client.is_playing() and not voice_client.is_paused():
                    play_next_song(message.guild.id)
                    await message.channel.send(f"Now playing: {song_title} -- {song_artist}")
                else:
                    await message.channel.send(f"Added to queue: {song_title} -- {song_artist}")
                    
            except Exception as e:
                print(e)
                await message.channel.send("Error playing song")
        
        elif message.content.startswith("!pause"):
            try:
                voice_client = voice_clients.get(message.guild.id)
                if voice_client and voice_client.is_playing():
                    voice_client.pause()
                    await message.channel.send("Music paused")
                elif voice_client and voice_client.is_paused():
                    voice_client.resume()
                    await message.channel.send("Music resumed")
                else:
                    await message.channel.send("No music is currently playing")
            except Exception as e:
                print(e)
                await message.channel.send("Error pausing/resuming music")
        
        elif message.content.startswith("!skip"):
            try:
                voice_client = voice_clients.get(message.guild.id)
                if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                    voice_client.stop()
                    # play_next_song will be called automatically by the after callback
                    await message.channel.send("Song skipped!")
                else:
                    await message.channel.send("No music is currently playing")
            except Exception as e:
                print(e)
                await message.channel.send("Error skipping song!")
        
        elif message.content.startswith("!queue"):
            try:
                guild_id = message.guild.id
                if guild_id in queues and queues[guild_id]:
                    queue_list = "**Current Queue:**\n"
                    for i, song in enumerate(queues[guild_id], 1):
                        queue_list += f"{i}. {song['title']} -- {song['artist']}\n"
                    await message.channel.send(queue_list)
                else:
                    await message.channel.send("Queue is empty")
            except Exception as e:
                print(e)
                await message.channel.send("Error displaying queue")
        
        elif message.content.startswith("!info"):
            try:
                guild_id = message.guild.id
                if guild_id in current_songs:
                    song = current_songs[guild_id]
                    await message.channel.send(f"**Now Playing:** {song['title']} -- {song['artist']}")
                else:
                    await message.channel.send("No song is currently playing")
            except Exception as e:
                print(e)
                await message.channel.send("Error getting song info")
        
        elif message.content.startswith("!leave"):
            try:
                voice_client = voice_clients.get(message.guild.id)
                if voice_client:
                    # stop any playing music
                    if voice_client.is_playing() or voice_client.is_paused():
                        voice_client.stop()
                    
                    # disconnect from voice channel
                    await voice_client.disconnect()
                    
                    # clean up resources
                    guild_id = message.guild.id
                    if guild_id in voice_clients:
                        del voice_clients[guild_id]
                    if guild_id in queues:
                        del queues[guild_id]
                    if guild_id in current_songs:
                        del current_songs[guild_id]
                    if guild_id in audio_players:
                        del audio_players[guild_id]
                    
                    await message.channel.send("Left the voice channel")
                else:
                    await message.channel.send("Not connected to a voice channel")
            except Exception as e:
                print(e)
                await message.channel.send("Error leaving voice channel")
    
    sonata_client.run(token)
            
