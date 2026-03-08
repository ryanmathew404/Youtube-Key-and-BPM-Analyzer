# Spotify Stem Separator — Setup Guide

## What this app does
Paste any Spotify track, album, or playlist URL and the app will:
1. **Download** the audio (via spotdl, which matches to YouTube Music)
2. **Detect the BPM and musical key** (using librosa)
3. **Separate into stems** — vocals, drums, bass, other (using Meta's Demucs)

---

## Requirements

- Python 3.9 or newer
- FFmpeg (required by both spotdl and demucs)

---

## Step-by-step installation

### 1. Install FFmpeg

**Windows:**
```
winget install ffmpeg
```
Or download from https://ffmpeg.org/download.html and add it to your PATH.

**macOS:**
```
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```
sudo apt install ffmpeg
```

---

### 2. Install Python packages

Open a terminal in the folder containing these files and run:

```
pip install -r requirements.txt
```

> ⚠️ **Note on PyTorch (for Demucs):** The `torch` and `torchaudio` packages are large (~1–2 GB).
> If you have an NVIDIA GPU, install the CUDA version from https://pytorch.org for much faster stem separation.
> CPU-only will work fine, but processing a full song can take 5–15 minutes.

---

### 3. Run the app

```
python spotify_stem_app.py
```

---

## How to use

1. Paste a Spotify URL into the **Spotify URL** field
   - Works with tracks, albums, and playlists
2. Choose an **Output Folder** (default: `~/StemSeparator`)
3. Pick a **Stem Model:**
   - `htdemucs` — 4 stems (vocals, drums, bass, other) — fastest, recommended
   - `htdemucs_6s` — 6 stems (adds piano & guitar) — better for instruments
   - `mdx_extra` — highest quality, slower
4. Click **▶ Start Processing** and watch the log

---

## Output folder structure

```
~/StemSeparator/
├── downloads/
│   └── Song Title.mp3          ← downloaded audio
└── stems/
    └── htdemucs/
        └── Song Title/
            ├── vocals.wav
            ├── drums.wav
            ├── bass.wav
            └── other.wav
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `spotdl: command not found` | Run `pip install spotdl` and make sure your pip bin is in PATH |
| Download fails | spotdl requires an internet connection and sometimes a Spotify cookie for newer tracks |
| Demucs takes forever | Normal on CPU. Consider a GPU, or try `htdemucs` which is the fastest model |
| Key detection seems wrong | Try longer songs — the algorithm works better with more audio data |
| `ffmpeg not found` error | Install FFmpeg and make sure it's on your PATH |

---

## Notes

- **spotdl** downloads audio by finding the matching track on YouTube Music — it does not download directly from Spotify's servers.
- Key detection uses the **Krumhansl-Schmuckler** tonal profiles, which is the standard musicology algorithm for key estimation.
- BPM detection uses librosa's beat tracker, which is highly accurate for music with a clear beat.
