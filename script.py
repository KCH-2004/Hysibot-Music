import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
import wavelink


def run_bot():
    load_dotenv()
    token = os.getenv("discord_token")

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix=".", intents=intents)

    # Fonction pour connecter le bot au serveur Lavalink au démarrage
    async def setup_hook():
        # Paramètres par défaut d'un serveur Lavalink local
        node = wavelink.Node(
        uri = "http://127.0.0.1:2333",
        password="youshallnotpass",
        identifier = "MAIN_NODE")
        await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)

    bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        print(f'✅ {bot.user} est connecté à Discord et à Lavalink !')
        try:
            synced = await bot.tree.sync()
            print(f"🔄 {len(synced)} commandes Slash synchronisées !")
        except Exception as e:
            print(f"❌ Erreur de synchronisation : {e}")

    @bot.event
    async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
        print(f"🟢 Node Lavalink connecté : {payload.node.identifier}")

    # Gestion automatique de la musique suivante
    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player: return

        # Si la file d'attente n'est pas vide, on lance la suite
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id:
            return

        if before.channel is not None and before.channel != after.channel:
            guild = before.channel.guild
            player: wavelink.Player = guild.voice_client

            if player and before.channel == player.channel:
                humains_restants = [m for m in player.channel.members if not m.bot]
                if len(humains_restants) == 0:
                    print(f"Le salon est vide sur le serveur {guild.id}, déconnexion...")
                    await player.disconnect()  # Wavelink nettoie tout automatiquement !

    @bot.tree.command(name="play", description="Lance l'audio d'une vidéo YouTube")
    @app_commands.describe(recherche="Url ou titre")
    async def play(interaction: discord.Interaction, recherche: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send("❌ Tu dois être dans un salon vocal !")

        player: wavelink.Player = interaction.guild.voice_client

        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)

        # NETTOYAGE DE L'URL (pour éviter le doublon dans les logs)
        recherche = recherche.split(' ')[0]

        try:
            # Recherche via Lavalink
            tracks: wavelink.Search = await wavelink.Playable.search(recherche)
            if not tracks:
                return await interaction.followup.send("❌ Aucun résultat trouvé.")

            track = tracks[0]

            # Gestion de la file d'attente
            await player.queue.put_wait(track)

            # RÉCUPÉRATION DES INFOS POUR L'EMBED (Style Ancien)
            titre = track.title
            url_video = track.uri
            miniature = track.artwork  # Wavelink récupère l'image automatiquement
            author = interaction.user

            if player.playing:
                # Embed style "Ajouté à la file"
                embed = discord.Embed(title="✅ Ajouté à la file", description=f"**[{titre}]({url_video})**",
                                      color=0xf1c40f)
                if miniature: embed.set_thumbnail(url=miniature)
                embed.set_footer(text=f"Musique ajouté par {author.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                # Lancement de la musique
                await player.play(player.queue.get())
                # Embed style "Lecture en cours"
                embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{titre}]({url_video})**",
                                      color=0x2ecc71)
                if miniature: embed.set_image(url=miniature)
                embed.set_footer(text=f"Musique lancée par {author.display_name}")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Erreur Play: {e}")
            await interaction.followup.send("❌ Problème avec YouTube ou Lavalink.")

    @bot.tree.command(name="pause", description="Met en pause l'audio")
    async def pause(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.playing:
            await player.pause(True)
            embed = discord.Embed(title=f"{interaction.user.display_name}", description="A mis en pause ⏸️",
                                  color=0xd30000)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Pas de musique en cours.", ephemeral=True)

    @bot.tree.command(name="resume", description="Reprend l'audio")
    async def resume(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.paused:
            await player.pause(False)
            embed = discord.Embed(title=f"{interaction.user.display_name}", description="A repris la musique ✅",
                                  color=0x008000)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Pas de musique en pause.", ephemeral=True)

    @bot.tree.command(name="skip", description="Passe la musique")
    async def skip(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if not player or not player.playing:
            return await interaction.response.send_message("❌ Rien à passer.", ephemeral=True)
        await player.stop()
        await interaction.response.send_message(f"⏭️ **{interaction.user.display_name}** a passé la musique.")

    @bot.tree.command(name="playlist", description="Affiche la playlist")
    async def playlist(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client

        if player and not player.queue.is_empty:
            playlist_text = ""
            for i, track in enumerate(player.queue):
                playlist_text += f"**{i + 1}.** {track.title}\n"

            embed = discord.Embed(title="📜 Playlist :", description=playlist_text, color=0x9b59b6)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                embed=discord.Embed(title="📭 La playlist est vide.", color=0x9b59b6))

    @bot.tree.command(name="deco", description="Déconnecte le bot")
    async def deco(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player:
            await player.disconnect()
            embed = discord.Embed(description="👋 **À demain**", color=0x95a5a6)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Je ne suis pas connecté.", ephemeral=True)

    bot.run(token)