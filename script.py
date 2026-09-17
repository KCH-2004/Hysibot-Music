import discord
import os
import random
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
    current_song = {}
    prefetching = {}  # évite de lancer 2 préchargements en parallèle sur le même serveur

    ytdl = yt_dlp.YoutubeDL({
        "format": "bestaudio/best",
	    "noplaylist": True,
	    "extractor_args":{"youtube":["player_client=web,android,ios"]},
        "noplaylist": True,
        "cookiefile": "cookies.txt",
        "source_address": "0.0.0.0",
        "remote_components": ["ejs:github"],
        "js_runtimes": {
            "bun": {},
            "node": {}
        }
    })

    # Instance dédiée pour scraper une playlist rapidement (sans extraire les flux audio)
    ytdl_flat = yt_dlp.YoutubeDL({
        "extract_flat": True,
        "skip_download": True,
        "cookiefile": "cookies.txt",
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
                        if guild_id in music_queue:
                            music_queue[guild_id].clear()
                        if guild_id in current_song:
                            del current_song[guild_id]
                        # On déconnecte le bot
                        await voice_clients[guild_id].disconnect()
                        # TRÈS IMPORTANT : On nettoie nos dictionnaires pour éviter les bugs à la prochaine connexion
                        del voice_clients[guild_id]
    @bot.event
    async def on_ready():
        print(f'✅ {bot.user} est connecté à Discord !')
        try:
            synced = await bot.tree.sync()
            print(f"🔄 {len(synced)} commandes Slash synchronisées !")
        except Exception as e:
            print(f"❌ Erreur de synchronisation : {e}")

    def addqueue(guild_id):
        if guild_id in current_song and current_song[guild_id].get('isloop', False):
            if guild_id not in music_queue:
                music_queue[guild_id] = []
            # On efface le flux préchargé : une URL de flux YouTube ne doit pas être
            # rejouée telle quelle, on force une nouvelle résolution pour la boucle
            current_song[guild_id].pop('url_video', None)
            current_song[guild_id].pop('miniature', None)
            music_queue[guild_id].insert(0, current_song[guild_id])

        if guild_id in music_queue and len(music_queue[guild_id]) > 0:
            asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)
        else:
            if guild_id in current_song:
                del current_song[guild_id]

    def schedule_prefetch(guild_id):
        # Peut être appelé depuis du code sync (ex: callback "after" d'FFmpeg) ou async
        asyncio.run_coroutine_threadsafe(prefetch_next(guild_id), bot.loop)

    async def prefetch_next(guild_id):
        # Résout à l'avance le flux audio du PROCHAIN titre de la file, pendant
        # que le titre actuel joue, pour éliminer le délai d'extraction au moment
        # de l'enchaînement (transition quasi instantanée entre les titres).
        if prefetching.get(guild_id, False):
            return  # un préchargement est déjà en cours pour ce serveur

        if guild_id not in music_queue or len(music_queue[guild_id]) == 0:
            return

        item = music_queue[guild_id][0]

        if item.get('url_video'):
            return  # déjà préchargé

        prefetching[guild_id] = True
        try:
            tasks = asyncio.get_event_loop()
            data = await tasks.run_in_executor(None, lambda: ytdl.extract_info(item['web_url'], download=False))
            if 'entries' in data:
                data = data['entries'][0]

            # On vérifie que l'item est toujours en tête de file (pas de skip entre temps)
            if guild_id in music_queue and len(music_queue[guild_id]) > 0 and music_queue[guild_id][0] is item:
                item['url_video'] = data.get('url')
                item['miniature'] = data.get('thumbnail')
        except Exception as e:
            print(f"Erreur de préchargement : {e}")
        finally:
            prefetching[guild_id] = False

    async def play_next(guild_id):
        if guild_id in music_queue and len(music_queue[guild_id]) > 0:
            item = music_queue[guild_id].pop(0)
            current_song[guild_id] = item
            web_url = item['web_url']
            channel = item['channel']
            titre = item['titreSon']

            try:
                # Si le titre a déjà été préchargé en arrière-plan, on saute l'extraction
                if item.get('url_video'):
                    url_video = item['url_video']
                    miniature = item.get('miniature')
                else:
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

                # On lance déjà le préchargement du titre suivant pendant que celui-ci joue
                schedule_prefetch(guild_id)
            except Exception as e:
                if guild_id in voice_clients and voice_clients[guild_id].is_connected():
                    print(f"Erreur lors de la lecture de la file : {e}")
                    await channel.send(f"❌ Impossible de lire **{titre}**.")
                    addqueue(guild_id)
                else:
                    del voice_clients[guild_id]

    @bot.tree.command(name="play", description="Lance l'audio d'une vidéo ytb")
    @app_commands.describe(recherche="Url ou titre", isloop="lecture en boucle ?")
    async def play(interaction: discord.Interaction, recherche: str, isloop: bool = False):

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
                music_queue[guild_id].append({'web_url': web_url, 'titreSon': titre, 'channel': interaction.channel, 'isloop': isloop})
                embed = discord.Embed(title="✅ Ajouté à la file", description=f"**[{titre}]({web_url})**", color=0xf1c40f)
                embed.set_thumbnail(url=miniature)
                embed.set_footer(text=f"Musique ajouté par {author.display_name}")
                await interaction.followup.send(embed=embed)
                # Si c'est le seul titre en file, on peut déjà le précharger en arrière-plan
                schedule_prefetch(guild_id)
            else:
                current_song[guild_id] = {'web_url': web_url, 'titreSon': titre, 'channel': interaction.channel,'isloop': isloop}
                player = discord.FFmpegPCMAudio(url_video, **ffmpeg_options)
                voice_clients[guild_id].play(player, after=lambda x=None: addqueue(guild_id))
                embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{titre}]({web_url})**", color=0x2ecc71)
                embed.set_image(url=miniature)
                if current_song[guild_id]['isloop']:
                    embed.set_footer(text=f"Musique en boucle 🔁")
                else:
                    embed.set_footer(text=f"Musique lancé par {author.display_name}")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(e)
            embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème YouTube.", color=0xe74c3c)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(name="loadplaylist", description="Charge une playlist et joue des titres aléatoires")
    @app_commands.describe(lien="Url de la playlist", nombre="Nombre de titres aléatoires à jouer (max 10)")
    async def loadplaylist(interaction: discord.Interaction, lien: str, nombre: app_commands.Range[int, 1, 10]):

        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("❌ Tu dois être dans un salon vocal !")
            return

        if not validators.url(lien):
            await interaction.followup.send("❌ Merci de fournir un lien de playlist valide.")
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
            # extract_flat permet de récupérer la liste des titres sans extraire
            # les flux audio de chaque vidéo (beaucoup plus rapide sur une grosse playlist)
            tasks = asyncio.get_event_loop()
            data = await tasks.run_in_executor(None, lambda: ytdl_flat.extract_info(lien, download=False))

            entries = data.get('entries') if data else None
            if not entries:
                embed = discord.Embed(title="❌ Erreur", description="Impossible de trouver des titres dans cette playlist.", color=0xe74c3c)
                await interaction.followup.send(embed=embed)
                return

            # On filtre les entrées invalides (vidéos privées, supprimées, etc.)
            entries_valides = [e for e in entries if e and (e.get('id') or e.get('url'))]

            if not entries_valides:
                embed = discord.Embed(title="❌ Erreur", description="Aucun titre valide trouvé dans cette playlist.", color=0xe74c3c)
                await interaction.followup.send(embed=embed)
                return

            nb_a_choisir = min(nombre, len(entries_valides))
            titres_choisis = random.sample(entries_valides, nb_a_choisir)

            if guild_id not in music_queue:
                music_queue[guild_id] = []

            for entree in titres_choisis:
                # En mode extract_flat, 'url' contient souvent déjà l'URL de la vidéo,
                # sinon on la reconstruit à partir de l'id
                web_url = entree.get('url') or entree.get('webpage_url')
                if web_url and not web_url.startswith('http'):
                    web_url = f"https://www.youtube.com/watch?v={web_url}"
                if not web_url and entree.get('id'):
                    web_url = f"https://www.youtube.com/watch?v={entree['id']}"

                titre = entree.get('title') or 'Titre inconnu'
                music_queue[guild_id].append({'web_url': web_url, 'titreSon': titre, 'channel': interaction.channel, 'isloop': False})

            liste_titres = "\n".join([f"• {e.get('title') or 'Titre inconnu'}" for e in titres_choisis])
            embed = discord.Embed(
                title="🎲 Playlist chargée !",
                description=f"**{nb_a_choisir}** titre(s) ajouté(s) aléatoirement à la file par {author.display_name}.",
                color=0x1abc9c
            )
            embed.add_field(name="Titres ajoutés", value=liste_titres[:1024], inline=False)
            await interaction.followup.send(embed=embed)

            if voice_clients[guild_id].is_playing() or voice_clients[guild_id].is_paused():
                # Une musique tourne déjà : on précharge en arrière-plan le titre en tête de file
                schedule_prefetch(guild_id)
            else:
                # Rien n'est en cours de lecture, on démarre la lecture
                addqueue(guild_id)

        except Exception as e:
            print(e)
            embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème lors du chargement de la playlist.", color=0xe74c3c)
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
                if guild_id in music_queue:
                    music_queue[guild_id].clear()
                if guild_id in current_song:
                    del current_song[guild_id]
                embed = discord.Embed(description="👋 **À demain**", color=0x95a5a6)
                await interaction.response.send_message(embed=embed)
                await voice_clients[guild_id].disconnect()
                del voice_clients[guild_id]
            except Exception as e:
                print(e)

    @bot.tree.command(name="playlist", description="Affiche la playlist")
    async def playlist(interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if guild_id not in voice_clients:
            embed = discord.Embed(title="❌ Erreur", description="Le bot n'est connecté à aucun salon vocal.",
                                  color=0xe74c3c)
            await interaction.response.send_message(embed=embed)
            return

        file_attente = music_queue.get(guild_id, [])

        if guild_id in current_song or len(file_attente) > 0:
            try:
                Playlist = ""

                # 1. On affiche la musique actuellement en cours
                if guild_id in current_song:
                    est_en_boucle = current_song[guild_id].get('isloop', False)
                    statut_loop = " 🔁" if est_en_boucle else ""
                    Playlist += f"**En cours :** {current_song[guild_id]['titreSon']}{statut_loop}\n\n**À suivre :**\n"

                # 2. L'ASTUCE ICI : Si la musique boucle, on l'affiche comme la prochaine à venir
                index_affichage = 1
                if guild_id in current_song and current_song[guild_id].get('isloop', False):
                    Playlist += f"**{index_affichage}.** {current_song[guild_id]['titreSon']} 🔁 *(En boucle)*\n"
                    index_affichage += 1

                # 3. On affiche le reste de la vraie file d'attente
                if len(file_attente) > 0:
                    for Prochains_titre in file_attente:
                        Playlist += f"**{index_affichage}.** {Prochains_titre['titreSon']}\n"
                        index_affichage += 1
                elif index_affichage == 1:
                    # S'il n'y a ni boucle ni musiques en attente
                    Playlist += "*Aucune musique à suivre.*"

                embed = discord.Embed(
                    title="📜 Playlist actuelle :",
                    description=Playlist,
                    color=0x9b59b6
                )
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                print(f"Erreur d'affichage playlist : {e}")
                await interaction.response.send_message("❌ Une erreur est survenue lors de l'affichage de la playlist.")
        else:
            embed = discord.Embed(title="📭 La playlist est vide.", color=0x9b59b6)
            await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="skip", description="Passe la musique")
    async def skip(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in voice_clients and voice_clients[guild_id].is_playing():
            try:
                if guild_id in current_song:
                    current_song[guild_id]['isloop'] = False
                voice_clients[guild_id].stop()
                embed = discord.Embed(title=f"{interaction.user.display_name}", description="A passé la musique ⏭️",
                                      color=0x9b59b6)
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(e)

    @bot.tree.command(name="loop",description="Loop l'audio")
    async def loop(interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if guild_id in voice_clients and voice_clients[guild_id].is_playing():
            if guild_id in current_song:
                current_song[guild_id]['isloop'] = not current_song[guild_id].get('isloop', False)
                if current_song[guild_id]['isloop']:
                    embed = discord.Embed(
                        title="🔁 Boucle activée",
                        description=f"La musique **{current_song[guild_id]['titreSon']}** sera répétée en boucle.",
                        color=0x3498db  # Bleu
                    )
                else:
                    embed = discord.Embed(
                        title="➡️ Boucle désactivée",
                        description="La file d'attente reprendra son cours normal à la fin du morceau.",
                        color=0x95a5a6  # Gris
                    )
                await interaction.response.send_message(embed=embed)
            else:
                # Sécurité au cas où current_song n'est pas encore initialisé
                await interaction.response.send_message("❌ Impossible de modifier l'état de la boucle pour le moment.")
        else:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Il n'y a aucune musique en cours de lecture !",
                color=0xe74c3c  # Rouge
            )
            await interaction.response.send_message(embed=embed)

    bot.run(token)