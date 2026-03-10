import discord
import os
import asyncio
import yt_dlp
import validators
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands

def run_bot():
    load_dotenv()
    token = os.getenv("discord_token")
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix=".", intents=intents)

    voice_clients = {}
    music_queue = {}
    ytdl = yt_dlp.YoutubeDL({
        "format": "bestaudio/best",
        "noplaylist": True,
        "cookiefile": "cookies.txt",
        "source_address": "0.0.0.0",
        "remote_components": ["ejs:github"],
        "js_runtimes": {
            "bun": {},
            "node": {}
        }
    })
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

    @bot.event
    async def on_voice_state_update(member, before, after):
        # 1. On ignore si l'événement est déclenché par le bot lui-même
        if member.id == bot.user.id:
            return
        # 2. On vérifie si la personne a QUITTÉ un salon vocal
        # (soit elle s'est déconnectée, soit elle a changé de salon)
        if before.channel is not None and before.channel != after.channel:
            guild_id = before.channel.guild.id
            # 3. On vérifie si notre bot est actuellement connecté sur ce serveur
            if guild_id in voice_clients and voice_clients[guild_id].is_connected():
                bot_channel = voice_clients[guild_id].channel
                # 4. Si le salon que la personne vient de quitter est bien celui où se trouve le bot...
                if before.channel == bot_channel:
                    # 5. On compte combien de "vrais humains" il reste dans le salon
                    # (on exclut les autres bots potentiels)
                    humains_restants = [m for m in bot_channel.members if not m.bot]
                    # S'il n'y a plus aucun humain
                    if len(humains_restants) == 0:
                        print(f"Le salon est vide sur le serveur {guild_id}, déconnexion...")
                        # On arrête la musique en cours s'il y en a une
                        voice_clients[guild_id].stop()
                        # On déconnecte le bot
                        await voice_clients[guild_id].disconnect()
                        # TRÈS IMPORTANT : On nettoie nos dictionnaires pour éviter les bugs à la prochaine connexion
                        del voice_clients[guild_id]
                        if guild_id in music_queue:
                            music_queue[guild_id].clear()

    @bot.event
    async def on_ready():
        print(f'✅ {bot.user} est connecté à Discord !')
        try:
            synced = await bot.tree.sync()
            print(f"🔄 {len(synced)} commandes Slash synchronisées !")
        except Exception as e:
            print(f"❌ Erreur de synchronisation : {e}")

    def addqueue(guild_id):
        if guild_id in music_queue and len(music_queue[guild_id]) > 0:
            asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)

    async def play_next(guild_id):
        if guild_id in music_queue and len(music_queue[guild_id]) > 0:
            item = music_queue[guild_id].pop(0)
            web_url = item['web_url']
            channel = item['channel']
            titre = item['titreSon']
            try:
                tasks = asyncio.get_event_loop()
                data = await tasks.run_in_executor(None, lambda: ytdl.extract_info(web_url, download=False))
                if 'entries' in data:
                    data = data['entries'][0]

                url_video = data.get('url')
                miniature = data.get('thumbnail')
                player = discord.FFmpegPCMAudio(url_video, **ffmpeg_options)
                voice_clients[guild_id].play(player, after=lambda x=None: addqueue(guild_id))
                embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{titre}]({web_url})**", color=0x2ecc71)
                if miniature:
                    embed.set_image(url=miniature)
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Erreur lors de la lecture de la file : {e}")
                await channel.send(f"❌ Impossible de lire **{titre}**.")
                addqueue(guild_id)



    @bot.tree.command(name="play",description="Lance l'audio d'une vidéo ytb")
    @app_commands.describe(recherche="Url ou titre")
    async def play(interaction: discord.Interaction, recherche:str):

        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("❌ Tu dois être dans un salon vocal !")
            return

        guild_id = interaction.guild_id
        author = interaction.user

        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            try:
                voice_clients[guild_id] = await interaction.user.voice.channel.connect()
            except Exception as e:
                print(f"Erreur connexion vocale : {e}")
                await interaction.followup.send("❌ Impossible de rejoindre ton salon vocal.")
                return

        try:
            if not validators.url(recherche):
                recherche = f"ytsearch:{recherche}"

            tasks = asyncio.get_event_loop()
            data = await tasks.run_in_executor(None, lambda: ytdl.extract_info(recherche, download=False))

            if 'entries' in data:
                data = data['entries'][0]

            url_video = data.get('url')
            web_url = data.get('webpage_url')
            titre = data.get('title')
            miniature = data.get('thumbnail')

            if voice_clients[guild_id].is_playing():
                if guild_id not in music_queue:
                    music_queue[guild_id] = []
                music_queue[guild_id].append({'web_url': web_url, 'titreSon': titre, 'channel': interaction.channel})
                embed = discord.Embed(title="✅ Ajouté à la file", description=f"**[{titre}]({web_url})**", color=0xf1c40f)
                embed.set_thumbnail(url=miniature)
                embed.set_footer(text=f"Musique ajouté par {author.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                player = discord.FFmpegPCMAudio(url_video, **ffmpeg_options)
                voice_clients[guild_id].play(player, after=lambda x=None: addqueue(guild_id))
                embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{titre}]({web_url})**", color=0x2ecc71)
                embed.set_image(url=miniature)
                embed.set_footer(text=f"Musique lancé par {author.display_name}")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(e)
            embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème YouTube.", color=0xe74c3c)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(name="pause", description="Met en pause l'audio")
    async def pause(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in voice_clients:
            if voice_clients[guild_id].is_playing():
                try:
                    voice_clients[guild_id].pause()
                    embed = discord.Embed(title=f"{interaction.user.display_name}", description="A mis en pause ⏸️",
                                          color=0xd3000)
                    await interaction.response.send_message(embed=embed)
                except Exception as e:
                    print(e)
            else:
                embed = discord.Embed(title="❌ Erreur", description="Pas de musique en cours.", color=0xe74c3c)
                await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="resume", description="reprend l'audio")
    async def resume(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in voice_clients:
            if voice_clients[guild_id].is_paused():
                try:
                    voice_clients[guild_id].resume()
                    embed = discord.Embed(title=f"{interaction.user.display_name}", description="A repris la musique ✅",color=0x008000)
                    await interaction.response.send_message(embed=embed)
                except Exception as e:
                    print(e)
            else:
                embed = discord.Embed(title="❌ Erreur", description="Pas de musique en Pause.", color=0xe74c3c)
                await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="deco", description="Deconnecte le bot")
    async def deco(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in voice_clients:
            try:
                voice_clients[guild_id].stop()
                embed = discord.Embed(description="👋 **À demain**", color=0x95a5a6)
                await interaction.response.send_message(embed=embed)
                await voice_clients[guild_id].disconnect()
                del voice_clients[guild_id]
                if guild_id in music_queue:
                    music_queue[guild_id].clear()
            except Exception as e:
                print(e)

    @bot.tree.command(name="playlist", description="Affiche la playlist")
    async def playlist(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in voice_clients:
            if guild_id in music_queue and len(music_queue[guild_id]) > 0:
                try:
                    Playlist = ""
                    for i, Prochains_titre in enumerate(music_queue[guild_id]):
                        Playlist += f"{i + 1}. {Prochains_titre['titreSon']}\n"
                    embed = discord.Embed(
                        title="📜Playlist :",
                        description=Playlist,
                        color=0x9b59b6  # Violet
                    )
                    await interaction.response.send_message(embed=embed)
                except Exception as e:
                    print(e)
            else:
                embed = discord.Embed(title="📭La playist est vide.", color=0x9b59b6)
                await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="skip", description="Passe la musique")
    async def skip(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in music_queue:
            try:
                voice_clients[guild_id].stop()
                embed = discord.Embed(title=f"{interaction.user.display_name}", description="A passé la musique ⏭️",
                                      color=0x9b59b6)
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(e)
    bot.run(token)