# runeflower

Built this mainly for my own music production workflow. You paste a YouTube link (or just search for a track), it downloads the audio as an MP3, and spits out the BPM and key. There's also a stem separator on the side that works with Spotify links — splits tracks into vocals, drums, bass, etc. using Meta's Demucs model.

Dark mode GUI, nothing too fancy.

---

## What it does

- Download any YouTube video or search result as MP3
- Auto-detect BPM and musical key after download
- Separate Spotify tracks into stems (vocals, drums, bass, other)
- Pick your own output folder

---

## Setup

You need Python 3.9+ and FFmpeg installed first.

**FFmpeg:**
```bash
# Windows
winget install ffmpeg

# Mac
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

**Then install the Python packages:**
```bash
pip install -r requirements.txt
```

If you have an NVIDIA GPU, grab the CUDA version of PyTorch from pytorch.org before installing — makes stem separation way faster. On CPU it can take like 10+ minutes per song.

---

## Running it

```bash
python spotify_stem_app.py
```

For YouTube: paste a URL or type a song name, pick an output folder, hit download. BPM and key show up automatically.

For stems: paste a Spotify track/album/playlist URL, pick a model (`htdemucs` is fastest, `mdx_extra` is best quality), and let it run.

---

## Stack

- `customtkinter` — GUI
- `yt-dlp` — YouTube downloading
- `librosa` — BPM + key detection
- `spotdl` — Spotify audio
- `demucs` — stem separation

---

## Common issues

- **Demucs is slow** — normal on CPU, use `htdemucs` or get a GPU
- **ffmpeg not found** — make sure it's on your PATH after installing
- **Key detection seems off** — works better on longer tracks, short clips can throw it off
