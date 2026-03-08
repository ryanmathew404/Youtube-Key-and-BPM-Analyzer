# runeflower 🎵

A desktop app for music producers and audio enthusiasts. Paste a **YouTube URL or search query** to download audio as MP3, then automatically detect its **BPM and musical key** — all in a clean dark-mode GUI. Also includes a **Spotify Stem Separator** that splits any track into vocals, drums, bass, and more.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python) ![License](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- 🎧 **YouTube → MP3** — download any YouTube video or search result as a high-quality MP3
- 🎼 **BPM Detection** — accurate tempo analysis using `librosa`'s beat tracker
- 🎹 **Key Detection** — musical key estimation via the Krumhansl-Schmuckler algorithm
- 🎛️ **Stem Separation** — split Spotify tracks into vocals, drums, bass, and other stems using Meta's Demucs model
- 🖥️ **Desktop GUI** — built with `customtkinter` for a modern dark-mode interface
- 📁 **Custom Output Folder** — choose where your downloads and stems are saved

---

## Screenshots

> _Add screenshots of the app here_

---

## Requirements

- Python 3.9+
- FFmpeg ([install guide](https://ffmpeg.org/download.html))

---

## Installation

**1. Clone the repo:**
```bash
git clone https://github.com/YOUR_USERNAME/runeflower.git
cd runeflower
```

**2. Install FFmpeg:**
```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

**3. Install Python dependencies:**
```bash
pip install -r requirements.txt
```

> ⚠️ **GPU Note:** Demucs stem separation benefits greatly from an NVIDIA GPU. Install PyTorch with CUDA from [pytorch.org](https://pytorch.org) for much faster processing. CPU-only works but can take 5–15 min per song.

---

## Usage

```bash
python spotify_stem_app.py
```

### YouTube to MP3 + Analysis
1. Paste a YouTube URL or type a search query
2. Choose your output folder
3. Click **Download** — the app downloads the MP3 and displays the detected BPM and key

### Stem Separation (Spotify)
1. Paste a Spotify track, album, or playlist URL
2. Choose a stem model:
   - `htdemucs` — 4 stems (vocals, drums, bass, other) — fastest
   - `htdemucs_6s` — 6 stems (adds piano & guitar)
   - `mdx_extra` — highest quality, slowest
3. Click **Start Processing** and monitor the log

### Output structure
```
~/Music/
├── downloads/
│   └── Song Title.mp3
└── stems/
    └── htdemucs/
        └── Song Title/
            ├── vocals.wav
            ├── drums.wav
            ├── bass.wav
            └── other.wav
```

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| `customtkinter` | Dark-mode desktop GUI |
| `yt-dlp` | YouTube audio downloading |
| `librosa` | BPM & key detection |
| `spotdl` | Spotify audio matching & download |
| `demucs` | AI-powered stem separation (Meta Research) |
| `FFmpeg` | Audio encoding & conversion |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `yt-dlp: command not found` | Run `pip install yt-dlp` |
| Download fails | Check your internet connection; some tracks may need a VPN |
| Demucs is very slow | Normal on CPU — use GPU or try `htdemucs` (fastest model) |
| Key detection seems off | Works best on longer tracks with a clear tonal center |
| `ffmpeg not found` | Install FFmpeg and add it to your system PATH |

---

## License

MIT — free to use, modify, and distribute.
