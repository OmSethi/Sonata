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
    ytdl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(ytdl_options)

    ffmpeg_options = {"options": "-vn"}

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

                song = data["url"]
                song_player = discord.FFmpegOpusAudio(song, **ffmpeg_options)

                voice_clients[message.guild.id].play(song_player)
            except Exception as e:
                print(e)
    
    sonata_client.run(token)

    @sonata_client.event
    async def on_message(message):
        if message.content.startswith("!leave"):
            try:
                bot_voice_client = await message.author.voice.channel.disconnect()
                voice_clients[bot_voice_client.guild.id] = bot_voice_client
            except Exception as e:
                print(e)
            
