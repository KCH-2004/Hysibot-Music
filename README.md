# 🎶 Bot Discord de Musique

Un bot Discord permettant de jouer de la musique depuis YouTube dans un salon vocal, avec gestion de file d'attente, lecture en boucle et déconnexion automatique.

## ✨ Fonctionnalités

- Lecture audio depuis une **URL YouTube** ou une **recherche par mots-clés**
- Système de **file d'attente** (queue) par serveur
- **Lecture en boucle** d'un morceau
- Affichage de la **playlist actuelle**
- **Pause / reprise** de la lecture
- **Passage** au morceau suivant (skip)
- **Déconnexion automatique** si le salon vocal se vide
- Commande de déconnexion manuelle
- Commandes slash (`/`) synchronisées automatiquement au démarrage

## 📋 Commandes

| Commande | Description |
|---|---|
| `/play recherche isloop` | Joue une musique (URL ou recherche) et l'ajoute à la file si une lecture est déjà en cours. `isloop` (optionnel) active la boucle. |
| `/pause` | Met la musique en pause. |
| `/resume` | Reprend la lecture. |
| `/skip` | Passe au morceau suivant. |
| `/loop` | Active/désactive la boucle du morceau en cours. |
| `/playlist` | Affiche la file d'attente et le morceau en cours. |
| `/deco` | Déconnecte le bot du salon vocal et vide la file. |

## 🛠️ Prérequis

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) installé et accessible dans le `PATH` (ou `ffmpeg.exe` à la racine sous Windows)
- Un compte et une application Discord avec un bot créé sur le [Discord Developer Portal](https://discord.com/developers/applications)
- Un fichier `cookies.txt` (format Netscape) pour l'authentification YouTube via `yt-dlp`, si nécessaire

## 📦 Installation

1. **Cloner le dépôt**

   ```bash
   git clone <url-du-depot>
   cd <nom-du-dossier>
   ```

2. **Créer un environnement virtuel** (recommandé)

   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   ```

3. **Installer les dépendances**

   ```bash
   pip install -r requirements.txt
   ```

4. **Installer FFmpeg** et vérifier qu'il est bien accessible via la commande `ffmpeg` dans le terminal.

## ⚙️ Configuration

Créer un fichier `.env` à la racine du projet contenant le token de votre bot Discord :

```env
discord_token=VOTRE_TOKEN_DISCORD
```

⚠️ Ne partagez jamais ce fichier ni votre token (déjà ignoré via `.gitignore`).

### Intents Discord

Le bot n'utilise que les intents par défaut (`discord.Intents.default()`). Assurez-vous que le bot est bien invité sur votre serveur avec les permissions suivantes :

- Voir les salons
- Se connecter aux salons vocaux
- Parler dans les salons vocaux
- Envoyer des messages / Embeds

## ▶️ Lancer le bot

```bash
python main.py
```

Au démarrage, le bot se connecte à Discord et synchronise automatiquement les commandes slash.

## 📁 Structure du projet

```
.
├── main.py              # Point d'entrée du bot
├── script.py             # Logique principale (commandes, lecture audio, gestion de la file)
├── requirements.txt      # Dépendances Python
├── .env                   # Token du bot (non versionné)
├── cookies.txt            # Cookies YouTube pour yt-dlp (non versionné)
└── .gitignore
```

## 🧩 Dépendances principales

- [`discord.py`](https://pypi.org/project/discord.py/) — interaction avec l'API Discord
- [`yt-dlp`](https://pypi.org/project/yt-dlp/) — extraction audio depuis YouTube
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) — chargement des variables d'environnement
- [`validators`](https://pypi.org/project/validators/) — validation des URLs
- [`PyNaCl`](https://pypi.org/project/PyNaCl/) — chiffrement audio requis par Discord

## ⚠️ Notes

- Le bot se déconnecte automatiquement du salon vocal lorsqu'il ne reste plus aucun humain dedans.
- La recherche par mots-clés utilise le premier résultat retourné par `ytsearch:` sur YouTube.
- Certaines vidéos peuvent nécessiter un fichier `cookies.txt` valide pour être lues (restrictions YouTube).

## 📝 Licence

Ce projet est distribué librement — ajoutez ici la licence de votre choix (MIT, GPL, etc.).
