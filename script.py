import discord
import os
import asyncio
import yt_dlp
import validators
from dotenv import load_dotenv
import subprocess
import sys


def update_libs():
    # Liste des librairies critiques à vérifier
    libs_to_update = [
        "yt-dlp",  # Pour YouTube (Indispensable)
        "discord.py",  # Pour l'API Discord
        "PyNaCl",  # Pour la voix (Indispensable)
        "validators"  # Pour tes vérifications d'URL
    ]

    print("🛠️ Vérification des librairies critiques...")

    for lib in libs_to_update:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", lib],
                stdout=subprocess.DEVNULL,  # Cache le blabla technique
                stderr=subprocess.DEVNULL
            )
            print(f"✅ {lib} est à jour.")
        except Exception as e:
            print(f"⚠️ Impossible de mettre à jour {lib} : {e}")

def run_bot():
    load_dotenv()
    token = os.getenv("discord_token")
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents = intents)

    voice_clients = {}
    music_queue = {}
    ytdl = yt_dlp.YoutubeDL({"format": "bestaudio/best", "noplaylist": True,"cookiefile": "cookies.txt","remote_components": ["ejs:github"]})
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn'}

    def addqueue(guild_id):
        if guild_id in music_queue and len(music_queue[guild_id]) > 0:
            source = music_queue[guild_id].pop(0)
            voice_clients[guild_id].play(source['sourceAudio'], after=lambda x=None: addqueue(guild_id))

    @client.event
    async def on_ready():
        await client.change_presence(activity=discord.Game(name=".help pour l'affichage des commandes"))
        print(f'{client.user} has connected to Discord!')


    @client.event
    async def on_message(message):
        if message.guild is None:
            return
        if message.author == client.user:
            return
        if not message.content:
            return
        guild_ID = message.guild.id

        commande = message.content.split()[0].lower()

        if commande =='.help':
            embed = discord.Embed(
                title ="🎧 Aide du Bot Musique",
                description = "📋 Liste des commandes:",
                color=0x3498db
            )
            embed.add_field(name='.play <url>/nom', value="▶️ Lance une vidéo youtube en audio")
            embed.add_field(name='️.stop', value=" ⏸️ mettre en pause la musique en cours")
            embed.add_field(name='️.resume', value=" ▶️ reprise de la musique en pause")
            embed.add_field(name='️.skip', value=" ⏭️ passer à la musique suivante")
            embed.add_field(name='️.playlist / .queue', value=" 📜 affiche la playlist")
            embed.add_field(name= '.deco', value="🛑 déconnecte le bot")
            await message.channel.send(embed = embed)

        if commande =='.play':
            try:
                await message.delete()
            except Exception as e:
                print(f"Je n'ai pas la permission de supprimer les messages : {e}")
            try:
                if message.author.voice:
                    if guild_ID not in voice_clients or not voice_clients[guild_ID].is_connected():
                        voice_client = await message.author.voice.channel.connect()
                        voice_clients[guild_ID] = voice_client
                else:
                    await message.channel.send("❌ Tu dois être dans un salon vocal !")
                    return
            except Exception as e:
                print(f"Erreur connexion : {e}")
            try:
                    titre_ou_url = " ".join(message.content.split()[1:])

                    if not validators.url(titre_ou_url):
                        titre_ou_url = f"ytsearch:{titre_ou_url}"

                    tasks = asyncio.get_event_loop()
                    data = await tasks.run_in_executor(None, lambda: ytdl.extract_info(titre_ou_url, download=False))

                    if 'entries' in data:
                        data = data['entries'][0]
                    url_video = data.get('url')
                    web_url = data.get('webpage_url')
                    titre = data.get('title')
                    miniature = data.get('thumbnail')
                    player = discord.FFmpegPCMAudio(url_video, **ffmpeg_options)

                    if voice_clients[guild_ID].is_playing():
                        if guild_ID not in music_queue:
                            music_queue[guild_ID] = []
                        music_queue[guild_ID].append({'sourceAudio':player, 'titreSon': data.get('title')})
                        embed = discord.Embed(title="✅ Ajouté à la file", description=f"**[{titre}]({web_url})**", color=0xf1c40f)
                        embed.set_thumbnail(url=miniature)
                        embed.set_footer(text=f"Musique ajouté par {message.author.display_name}")
                        await message.channel.send(embed=embed)
                    else:
                        voice_clients[guild_ID].play(player, after=lambda x = None: addqueue(guild_ID))
                        embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{titre}]({web_url})**", color=0x2ecc71)
                        embed.set_image(url=miniature)
                        embed.set_footer(text=f"Musique lancé par {message.author.display_name}")
                        await message.channel.send(embed = embed)
            except Exception as e:
                print(e)
                embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème YouTube.",color=0xe74c3c)
                await message.channel.send(embed = embed)

        elif commande =='.pause':
            if voice_clients[guild_ID].is_playing():
                try:
                    voice_clients[guild_ID].pause()
                    embed = discord.Embed(title=f"{message.author.display_name}", description="A mis en pause ⏸️", color=0xd3000)
                    await message.channel.send(embed = embed)
                except Exception as e:
                    print(e)
            else:
                embed = discord.Embed(title="❌ Erreur", description="Pas de musique en cours.",color=0xe74c3c)
                await message.channel.send(embed = embed)

        elif commande =='.resume':
            if voice_clients[guild_ID].is_paused():
                try:
                    voice_clients[guild_ID].resume()
                    embed = discord.Embed(title=f"{message.author.display_name}", description="A repris la musique ✅",color=0x008000)
                    await message.channel.send(embed=embed)
                except Exception as e:
                    print(e)
            else:
                embed = discord.Embed(title="❌ Erreur", description="Pas de musique en Pause.", color=0xe74c3c)
                await message.channel.send(embed=embed)

        elif commande =='.deco':
            try:
                voice_clients[guild_ID].stop()
                embed = discord.Embed(description="👋 **À demain**", color=0x95a5a6)
                await message.channel.send(embed = embed)
                await voice_clients[guild_ID].disconnect()
            except Exception as e:
                print(e)

        elif commande =='.skip':
            try:
                voice_clients[guild_ID].stop()
                embed = discord.Embed(title=f"{message.author.display_name}", description="A passé la musique ⏭️", color=0x9b59b6)
                await message.channel.send(embed = embed)
            except Exception as e:
                print(e)

        elif commande =='.playlist' or commande =='.queue':
            if guild_ID in music_queue and len(music_queue[guild_ID]) > 0:
                try:
                    Playlist = ""
                    for i, Prochains_titre in enumerate(music_queue[guild_ID]):
                        Playlist += f"{i + 1}. {Prochains_titre['titreSon']}\n"
                    embed = discord.Embed(
                        title="📜Playlist :",
                        description=Playlist,
                        color=0x9b59b6  # Violet
                    )
                    await message.channel.send(embed=embed)
                except Exception as e:
                    print(e)
            else:
                embed= discord.Embed(title="📭La playist est vide.",color=0x9b59b6)
                await message.channel.send(embed = embed)
    client.run(token)