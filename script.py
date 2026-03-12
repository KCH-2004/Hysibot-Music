import discord
import os
import wavelink
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands


def run_bot():
    load_dotenv()
    token = os.getenv("discord_token")
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix=".", intents=intents)

    # --- Connexion au serveur Lavalink (Nœud Public) ---
    async def setup_hook():
        node = wavelink.Node(
            identifier="Public_Node",
            uri="https://lavalink.oops.wtf:443",
            password="www.freelavalink.rest"
        )
        await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)

    bot.setup_hook = setup_hook

    # --- Événements ---
    @bot.event
    async def on_ready():
        print(f'✅ {bot.user} est connecté à Discord et Wavelink !')

        # Nettoyage des sessions fantômes au redémarrage
        for guild in bot.guilds:
            if guild.voice_client:
                await guild.voice_client.disconnect(force=True)

        try:
            synced = await bot.tree.sync()
            print(f"🔄 {len(synced)} commandes Slash synchronisées !")
        except Exception as e:
            print(f"❌ Erreur de synchronisation : {e}")

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
                    await player.disconnect()  # Wavelink vide la file automatiquement !

    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player: return

        # Gestion automatique de la musique suivante
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)

            # Envoi de ton embed exact quand la musique suivante se lance
            if hasattr(player, "reply_channel"):
                embed = discord.Embed(title="🎶 Lecture en cours",
                                      description=f"**[{next_track.title}]({next_track.uri})**", color=0x2ecc71)
                if next_track.artwork:
                    embed.set_image(url=next_track.artwork)
                await player.reply_channel.send(embed=embed)

    # --- Commandes ---
    @bot.tree.command(name="play", description="Lance l'audio d'une vidéo ytb")
    @app_commands.describe(recherche="Url ou titre")
    async def play(interaction: discord.Interaction, recherche: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("❌ Tu dois être dans un salon vocal !")
            return

        player: wavelink.Player = interaction.guild.voice_client

        if not player:
            try:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            except Exception as e:
                print(f"Erreur connexion vocale : {e}")
                await interaction.followup.send("❌ Impossible de rejoindre ton salon vocal.")
                return

        # On sauvegarde le salon texte pour que l'événement "track_end" sache où envoyer les messages
        player.reply_channel = interaction.channel

        try:
            # Recherche via Wavelink
            tracks = await wavelink.Playable.search(recherche)
            if not tracks:
                embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème YouTube.",
                                      color=0xe74c3c)
                return await interaction.followup.send(embed=embed)

            track = tracks[0]

            if player.playing:
                await player.queue.put_wait(track)
                embed = discord.Embed(title="✅ Ajouté à la file", description=f"**[{track.title}]({track.uri})**",
                                      color=0xf1c40f)
                if track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                embed.set_footer(text=f"Musique ajouté par {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await player.play(track)
                embed = discord.Embed(title="🎶 Lecture en cours", description=f"**[{track.title}]({track.uri})**",
                                      color=0x2ecc71)
                if track.artwork:
                    embed.set_image(url=track.artwork)
                embed.set_footer(text=f"Musique lancé par {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(e)
            embed = discord.Embed(title="❌ Erreur", description="Lien invalide ou problème YouTube.", color=0xe74c3c)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(name="pause", description="Met en pause l'audio")
    async def pause(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.playing:
            try:
                await player.pause(True)
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
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.paused:
            try:
                await player.pause(False)
                embed = discord.Embed(title=f"{interaction.user.display_name}", description="A repris la musique ✅",
                                      color=0x008000)
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(e)
        else:
            embed = discord.Embed(title="❌ Erreur", description="Pas de musique en Pause.", color=0xe74c3c)
            await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="deco", description="Deconnecte le bot")
    async def deco(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player:
            try:
                embed = discord.Embed(description="👋 **À demain**", color=0x95a5a6)
                await interaction.response.send_message(embed=embed)
                await player.disconnect()
            except Exception as e:
                print(e)
        else:
            await interaction.response.send_message("❌ Je ne suis pas connecté.", ephemeral=True)

    @bot.tree.command(name="playlist", description="Affiche la playlist")
    async def playlist(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and not player.queue.is_empty:
            try:
                Playlist_text = ""
                for i, track in enumerate(player.queue):
                    Playlist_text += f"{i + 1}. {track.title}\n"
                embed = discord.Embed(
                    title="📜Playlist :",
                    description=Playlist_text,
                    color=0x9b59b6
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(e)
        else:
            embed = discord.Embed(title="📭La playist est vide.", color=0x9b59b6)
            await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="skip", description="Passe la musique")
    async def skip(interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client
        if player and (player.playing or player.paused):
            try:
                await player.skip(force=True)  # Saute nativement au prochain son de la file
                embed = discord.Embed(title=f"{interaction.user.display_name}", description="A passé la musique ⏭️",
                                      color=0x9b59b6)
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(e)
        else:
            await interaction.response.send_message("❌ Rien à passer.", ephemeral=True)

    bot.run(token)