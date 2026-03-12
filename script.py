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
        nodes = [wavelink.Node(uri="http://127.0.0.1:2333", password="youshallnotpass")]
        await wavelink.Pool.connect(nodes=nodes, client=bot, cache_capacity=100)

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

        # Récupère le player Lavalink du serveur
        player: wavelink.Player = interaction.guild.voice_client

        # S'il n'y a pas de player, on connecte le bot
        if not player:
            try:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            except Exception as e:
                print(e)
                return await interaction.followup.send("❌ Impossible de rejoindre ton salon vocal.")

        # Recherche de la musique via Lavalink
        try:
            tracks: wavelink.Search = await wavelink.Playable.search(recherche)
            if not tracks:
                return await interaction.followup.send("❌ Aucun résultat trouvé.")

            track: wavelink.Playable = tracks[0]  # On prend le premier résultat

            # On ajoute à la file d'attente intégrée de Wavelink
            await player.queue.put_wait(track)

            embed = discord.Embed(title="🎶 Musique", color=0x2ecc71)
            embed.set_footer(text=f"Ajouté par {interaction.user.display_name}")
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)

            if not player.playing:
                # Si le bot ne joue rien, on lance la musique
                next_track = player.queue.get()
                await player.play(next_track)
                embed.description = f"**Lecture en cours :** [{track.title}]({track.uri})"
            else:
                # Sinon c'est juste ajouté à la file
                embed.color = 0xf1c40f
                embed.description = f"**Ajouté à la file :** [{track.title}]({track.uri})"

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Erreur Play: {e}")
            await interaction.followup.send("❌ Une erreur est survenue lors de la recherche.")

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
        if player and player.playing:
            await player.skip(force=True)
            embed = discord.Embed(title=f"{interaction.user.display_name}", description="A passé la musique ⏭️",
                                  color=0x9b59b6)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Rien à passer.", ephemeral=True)

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