"""
runeflower — YouTube to MP3 Downloader & Analyzer
───────────────────────────────────────────────────
Paste a YouTube URL or search query and this app will:
  1. Download the audio as MP3 via yt-dlp
  2. Detect the BPM and musical key
  3. Optionally split into stems via Demucs

Dependencies:
  pip install -r requirements.txt
"""

import shutil
import tempfile
import threading
import sys
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
except ImportError:
    print("customtkinter not found. Run: pip install customtkinter")
    sys.exit(1)

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

STEMS = ["vocals", "drums", "bass", "other"]
STEM_COLORS  = {"vocals": "#e91e8c", "drums": "#00bcd4", "bass": "#ff9800", "other": "#4caf50"}
STEM_ICONS   = {"vocals": "🎤", "drums": "🥁", "bass": "🎸", "other": "🎹"}


# ──────────────────────────────────────────────────────────────────────────────
# Dependency check
# ──────────────────────────────────────────────────────────────────────────────

def check_deps():
    missing = []
    try:
        import librosa  # noqa
    except ImportError:
        missing.append("librosa")
    try:
        import numpy  # noqa
    except ImportError:
        missing.append("numpy")
    if not shutil.which("demucs"):
        missing.append("demucs  (run: pip install demucs)")
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp  (run: pip install yt-dlp)")
    if not _HAS_AUDIO:
        missing.append("sounddevice  (run: pip install sounddevice)")
    return missing


# ──────────────────────────────────────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("runeflower")
        self.geometry("740x800")
        self.minsize(620, 640)
        self.resizable(True, True)
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
        self.output_dir = Path(r"C:\Users\Gamin\OneDrive\Desktop\stemsfromapp")

        # Playback state
        self._stem_dir:   "Path | None"         = None
        self._stems_data: "dict[str, tuple]"    = {}   # stem -> (ndarray, sr)
        self._muted:      "dict[str, bool]"     = {s: False for s in STEMS}
        self._soloed:     "str | None"          = None
        self._play_pos:   int                   = 0
        self._playing:    bool                  = False
        self._stream:     "object | None"       = None
        self._max_len:    int                   = 0
        self._sr:         int                   = 44100

        # UI refs for stem rows (populated in _build_stem_player)
        self._stem_canvases:    "dict[str, tk.Canvas]"          = {}
        self._stem_check_vars:  "dict[str, ctk.BooleanVar]"     = {}
        self._solo_btns:        "dict[str, ctk.CTkButton]"      = {}
        self._mute_btns:        "dict[str, ctk.CTkButton]"      = {}

        # Drum MIDI state
        self._track_dir:        "Path | None"                   = None
        self._midi_btn:         "ctk.CTkButton | None"          = None
        self._midi_status_lbl:  "ctk.CTkLabel | None"           = None

        # Most-recent analysis results (used to tag save folder names)
        self._last_bpm:         "float | None"                  = None
        self._last_key:         "str | None"                    = None

        self._build_ui()
        self._check_deps_async()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 4))

        ctk.CTkLabel(
            header, text="Ryan's Audio Analyzer",
            font=ctk.CTkFont(size=26, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Download MP3 · Detect Key & BPM",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(side="left", padx=(14, 0), pady=(6, 0))

        ctk.CTkFrame(self, height=1, fg_color="#333").pack(fill="x", padx=24, pady=(4, 14))

        # URL input
        self._section_label("YouTube URL or search query")
        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.pack(fill="x", padx=24, pady=(2, 10))
        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="https://youtube.com/watch?v=…  or  Artist - Song Name",
            height=42, font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(fill="x")

        # Output folder
        self._section_label("Output Folder")
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=24, pady=(2, 10))
        self.out_entry = ctk.CTkEntry(out_row, font=ctk.CTkFont(size=12), height=38)
        self.out_entry.insert(0, str(self.output_dir))
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            out_row, text="Browse", width=90, height=38, command=self._browse
        ).pack(side="right")

        # Stem split toggle
        opts_row = ctk.CTkFrame(self, fg_color="transparent")
        opts_row.pack(fill="x", padx=24, pady=(0, 4))
        self.split_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts_row,
            text="Split into stems  (vocals · drums · bass · other)",
            variable=self.split_var,
            font=ctk.CTkFont(size=13),
            command=self._on_split_toggle,
        ).pack(side="left")

        # Start button
        self.start_btn = ctk.CTkButton(
            self, text=self._btn_text(), height=50,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start
        )
        self.start_btn.pack(fill="x", padx=24, pady=(10, 14))

        # Results panel
        results_frame = ctk.CTkFrame(self)
        results_frame.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(
            results_frame, text="Results",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(anchor="w", padx=16, pady=(10, 6))

        row = ctk.CTkFrame(results_frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        bpm_box = ctk.CTkFrame(row, corner_radius=10)
        bpm_box.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(bpm_box, text="BPM", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(10, 2))
        self.bpm_label = ctk.CTkLabel(bpm_box, text="—", font=ctk.CTkFont(size=32, weight="bold"))
        self.bpm_label.pack(pady=(0, 10))

        key_box = ctk.CTkFrame(row, corner_radius=10)
        key_box.pack(side="left", expand=True, fill="x", padx=(8, 0))
        ctk.CTkLabel(key_box, text="KEY", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(10, 2))
        self.key_label = ctk.CTkLabel(key_box, text="—", font=ctk.CTkFont(size=32, weight="bold"))
        self.key_label.pack(pady=(0, 10))

        # Stem player panel — hidden until stems are ready
        self._stem_player_frame = ctk.CTkFrame(self)
        self._build_stem_player()

        # Log label (stored so stem player can pack before it)
        self._log_label = ctk.CTkLabel(
            self, text="Log", font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        )
        self._log_label.pack(anchor="w", padx=26)

        self.log_box = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Courier", size=11)
        )
        self.log_box.pack(fill="both", expand=True, padx=24, pady=(2, 20))
        self.log_box.configure(state="disabled")

    def _build_stem_player(self):
        f = self._stem_player_frame

        # Transport row
        transport = ctk.CTkFrame(f, fg_color="transparent")
        transport.pack(fill="x", padx=14, pady=(12, 6))

        self._play_btn = ctk.CTkButton(
            transport, text="▶  Play", width=90, height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_play,
        )
        self._play_btn.pack(side="left", padx=(0, 12))

        self._time_label = ctk.CTkLabel(
            transport, text="0:00 / 0:00",
            font=ctk.CTkFont(family="Courier", size=12), text_color="gray"
        )
        self._time_label.pack(side="left")

        ctk.CTkLabel(
            transport,
            text="S = solo · M = mute · ✓ = include in save",
            font=ctk.CTkFont(size=11), text_color="#555"
        ).pack(side="right")

        ctk.CTkFrame(f, height=1, fg_color="#2a2a2a").pack(fill="x", padx=14, pady=(4, 6))

        # One row per stem
        for stem in STEMS:
            self._build_stem_row(f, stem)

        ctk.CTkFrame(f, height=1, fg_color="#2a2a2a").pack(fill="x", padx=14, pady=(6, 0))

        # Save row
        save_row = ctk.CTkFrame(f, fg_color="transparent")
        save_row.pack(fill="x", padx=14, pady=(8, 12))

        ctk.CTkLabel(
            save_row, text="Save checked stems to output folder →",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(side="left")

        ctk.CTkButton(
            save_row, text="💾  Save Selected",
            height=36, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save_selected_stems,
        ).pack(side="right")

        # ── Drum MIDI section ──────────────────────────────────────────────
        ctk.CTkFrame(f, height=1, fg_color="#2a2a2a").pack(fill="x", padx=14, pady=(4, 0))

        midi_section = ctk.CTkFrame(f, fg_color="transparent")
        midi_section.pack(fill="x", padx=14, pady=(8, 12))

        midi_left = ctk.CTkFrame(midi_section, fg_color="transparent")
        midi_left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            midi_left,
            text="🥁  Drum MIDI  —  Transcribe the drum stem into snare/clap + hi-hat MIDI (grid-quantized)",
            font=ctk.CTkFont(size=12), text_color="gray", anchor="w",
        ).pack(anchor="w")

        self._midi_status_lbl = ctk.CTkLabel(
            midi_left, text="",
            font=ctk.CTkFont(family="Courier", size=11), text_color="#aaa", anchor="w",
        )
        self._midi_status_lbl.pack(anchor="w", pady=(2, 0))

        self._midi_btn = ctk.CTkButton(
            midi_section,
            text="🎹  Generate Drum MIDI",
            height=36, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._generate_drum_midi,
        )
        self._midi_btn.pack(side="right")

    def _build_stem_row(self, parent, stem: str):
        color = STEM_COLORS[stem]
        icon  = STEM_ICONS[stem]

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=3)

        # Icon + name
        ctk.CTkLabel(
            row, text=f"{icon} {stem.capitalize()}",
            font=ctk.CTkFont(size=12), width=86, anchor="w"
        ).pack(side="left")

        # Waveform canvas
        canvas = tk.Canvas(row, height=54, bg="#1c1c1c", highlightthickness=1,
                           highlightbackground="#2a2a2a")
        canvas.pack(side="left", fill="x", expand=True, padx=(4, 10))
        self._stem_canvases[stem] = canvas

        # Solo button
        solo_btn = ctk.CTkButton(
            row, text="S", width=32, height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2a2a2a", hover_color="#444",
            command=lambda s=stem: self._toggle_solo(s),
        )
        solo_btn.pack(side="left", padx=(0, 4))
        self._solo_btns[stem] = solo_btn

        # Mute button
        mute_btn = ctk.CTkButton(
            row, text="M", width=32, height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2a2a2a", hover_color="#444",
            command=lambda s=stem: self._toggle_mute(s),
        )
        mute_btn.pack(side="left", padx=(0, 10))
        self._mute_btns[stem] = mute_btn

        # Download checkbox
        var = ctk.BooleanVar(value=True)
        self._stem_check_vars[stem] = var
        ctk.CTkCheckBox(
            row, text="", variable=var, width=24,
            checkbox_width=22, checkbox_height=22,
        ).pack(side="left")

    def _section_label(self, text):
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(anchor="w", padx=26, pady=(0, 2))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, folder)

    def _log(self, msg: str):
        self.after(0, self._log_main, msg)

    def _log_main(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_results(self, bpm: float, key: str):
        self.after(0, lambda: self.bpm_label.configure(text=f"{bpm:.1f}"))
        self.after(0, lambda: self.key_label.configure(text=key))

    def _btn_text(self) -> str:
        return "▶   Download, Analyze & Split" if self.split_var.get() else "▶   Download & Analyze"

    def _on_split_toggle(self):
        self.start_btn.configure(text=self._btn_text())

    def _set_btn(self, enabled: bool, text: str = None):
        if text is None:
            text = self._btn_text()
        self.after(0, lambda: self.start_btn.configure(
            state="normal" if enabled else "disabled", text=text
        ))

    def _tagged_folder_name(self, base_name: str) -> str:
        """Append the detected BPM and key to a folder name, e.g.
        'Song Title [120BPM C Major]'.  Falls back to the plain name
        if analysis hasn't completed yet."""
        if self._last_bpm is None or self._last_key is None:
            return base_name
        bpm_int = int(round(self._last_bpm))
        # Sanitise key (just in case): strip filesystem-hostile chars
        key = self._last_key.replace("/", "-").replace("\\", "-").strip()
        tag = f"[{bpm_int}BPM {key}]"
        # Avoid double-tagging if the base name already ends with this tag
        if base_name.endswith(tag):
            return base_name
        return f"{base_name} {tag}"

    def _show_stem_player(self):
        self.after(0, lambda: self._stem_player_frame.pack(
            fill="x", padx=24, pady=(0, 12), before=self._log_label
        ))

    def _hide_stem_player(self):
        self._stop_playback()
        self.after(0, self._stem_player_frame.pack_forget)

    # ── Dependency check ──────────────────────────────────────────────────────

    def _check_deps_async(self):
        threading.Thread(target=self._check_deps_worker, daemon=True).start()

    def _check_deps_worker(self):
        missing = check_deps()
        if missing:
            self._log("⚠️  Missing dependencies:")
            for m in missing:
                self._log(f"   • {m}")
            self._log("   → Run: pip install -r requirements.txt\n")
        else:
            self._log("✅  All dependencies found. Ready!\n")

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _start(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log("⚠️  Please enter a YouTube URL or search query first.")
            return

        out_dir = self.out_entry.get().strip() or str(self.output_dir)
        self.output_dir = Path(out_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.after(0, lambda: self.bpm_label.configure(text="—"))
        self.after(0, lambda: self.key_label.configure(text="—"))
        self._hide_stem_player()

        if self._stem_dir and self._stem_dir.exists():
            shutil.rmtree(self._stem_dir, ignore_errors=True)
            self._stem_dir = None

        self._set_btn(False, "⏳  Processing…")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        threading.Thread(target=self._pipeline, args=(url,), daemon=True).start()

    def _pipeline(self, url: str):
        try:
            self._log("━" * 46)
            self._log("⬇️   Downloading…")
            self._log("━" * 46)
            audio_file = self._download(url)
            if audio_file is None:
                self._log("❌  Download failed. Check the URL and try again.")
                return
            self._log(f"✅  Saved: {audio_file.name}\n")

            self._log("━" * 46)
            self._log("🎵   Analyzing Key & BPM…")
            self._log("━" * 46)
            key, bpm = self._analyze(audio_file)
            self._last_bpm = bpm
            self._last_key = key
            self._set_results(bpm, key)
            self._log(f"✅  Done!  BPM: {bpm:.1f}  |  Key: {key}\n")

            if self.split_var.get():
                self._log("━" * 46)
                self._log("🎛️   Splitting stems…  (this may take a few minutes)")
                self._log("━" * 46)
                track_dir = self._split_stems(audio_file)
                if track_dir:
                    self._stem_dir = track_dir.parent.parent
                    # Auto-save every stem immediately
                    folder_name = self._tagged_folder_name(track_dir.name)
                    auto_dest   = self.output_dir / "stems" / folder_name
                    auto_dest.mkdir(parents=True, exist_ok=True)
                    auto_saved = []
                    for stem in STEMS:
                        src = track_dir / f"{stem}.wav"
                        if src.exists():
                            shutil.copy2(src, auto_dest / f"{stem}.wav")
                            auto_saved.append(stem)
                    if auto_saved:
                        self._log(f"💾  Auto-saved stems ({', '.join(auto_saved)}) → {auto_dest}")
                    self._log("✅  Stems ready — use the player below.\n")
                    self._load_stems_for_playback(track_dir)
                else:
                    self._log("❌  Stem splitting failed. Is demucs installed?")

        except Exception as exc:
            self._log(f"\n❌  Error: {exc}")
            import traceback
            self._log(traceback.format_exc())
        finally:
            self._set_btn(True)

    # ── Download ──────────────────────────────────────────────────────────────

    def _download(self, url: str) -> "Path | None":
        self.output_dir.mkdir(parents=True, exist_ok=True)
        query = url if url.startswith("http") else f"ytsearch1:{url}"
        cmd = [
            "yt-dlp", "--extract-audio", "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", str(self.output_dir / "%(title)s.%(ext)s"),
            "--no-playlist", query,
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self._log(f"   {line}")
        proc.wait()

        if proc.returncode != 0:
            return None

        candidates = sorted(
            list(self.output_dir.glob("*.mp3")) +
            list(self.output_dir.glob("*.flac")) +
            list(self.output_dir.glob("*.wav")),
            key=lambda f: f.stat().st_mtime, reverse=True
        )
        return candidates[0] if candidates else None

    # ── Stem splitting ────────────────────────────────────────────────────────

    def _split_stems(self, audio_file: Path) -> "Path | None":
        tmp = Path(tempfile.mkdtemp(prefix="runeflower_stems_"))

        # torchaudio 2.6+ requires torchcodec (broken on many Windows setups).
        # Patch torchaudio.save to use soundfile instead, then hand off to demucs.
        patcher_code = (
            "import sys, soundfile as sf, torchaudio\n"
            "torchaudio.save = lambda p, src, sample_rate=44100, **kw: "
            "sf.write(str(p), src.numpy().T, sample_rate, subtype='PCM_16')\n"
            "from demucs.__main__ import main\n"
            "sys.exit(main() or 0)\n"
        )
        patcher = Path(tempfile.mktemp(suffix="_demucs_run.py"))
        patcher.write_text(patcher_code, encoding="utf-8")

        cmd = [
            sys.executable, str(patcher),
            "--out", str(tmp),
            str(audio_file),
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self._log(f"   {line}")
        proc.wait()
        patcher.unlink(missing_ok=True)

        if proc.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return None

        track_dir = tmp / "htdemucs" / audio_file.stem
        return track_dir if track_dir.exists() else None

    # ── Stem loading & waveform ───────────────────────────────────────────────

    def _load_stems_for_playback(self, track_dir: Path):
        self._track_dir = track_dir  # store for MIDI generation

        # Reset MIDI status label
        if self._midi_status_lbl:
            self.after(0, lambda: self._midi_status_lbl.configure(text=""))
        if self._midi_btn:
            self.after(0, lambda: self._midi_btn.configure(
                state="normal", text="🎹  Generate Drum MIDI"
            ))

        if not _HAS_AUDIO:
            self._log("⚠️  sounddevice not installed — playback unavailable.")
            self._show_stem_player()
            return

        self._stems_data = {}
        for stem in STEMS:
            path = track_dir / f"{stem}.wav"
            if path.exists():
                data, sr = sf.read(str(path), dtype="float32", always_2d=True)
                self._stems_data[stem] = (data, sr)
                self._sr = sr

        if not self._stems_data:
            return

        self._max_len = max(len(d) for d, _ in self._stems_data.values())
        self._muted   = {s: False for s in STEMS}
        self._soloed  = None
        self._play_pos = 0
        self._playing  = False

        # Reset solo/mute button colours
        for stem in STEMS:
            self.after(0, lambda s=stem: self._solo_btns[s].configure(fg_color="#2a2a2a"))
            self.after(0, lambda s=stem: self._mute_btns[s].configure(fg_color="#2a2a2a"))

        # Draw waveforms (needs widget dimensions — schedule after render)
        for stem, (data, _) in self._stems_data.items():
            self.after(200, lambda s=stem, d=data: self._draw_waveform(s, d))

        self._show_stem_player()

    def _draw_waveform(self, stem: str, audio: "np.ndarray"):
        canvas = self._stem_canvases.get(stem)
        if canvas is None:
            return
        canvas.update_idletasks()
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10:
            self.after(200, lambda: self._draw_waveform(stem, audio))
            return

        canvas.delete("all")
        color = STEM_COLORS[stem]
        mono = audio.mean(axis=1) if audio.ndim > 1 else audio

        bar_w     = 3
        n_bars    = w // bar_w
        chunk_sz  = max(1, len(mono) // n_bars)
        mid       = h // 2

        for i in range(n_bars):
            chunk = mono[i * chunk_sz : i * chunk_sz + chunk_sz]
            if not len(chunk):
                continue
            amp   = float(np.max(np.abs(chunk)))
            bar_h = max(1, int(amp * (mid - 2)))
            x     = i * bar_w + bar_w // 2
            canvas.create_line(x, mid - bar_h, x, mid + bar_h, fill=color, width=2)

    # ── Playback ──────────────────────────────────────────────────────────────

    def _toggle_play(self):
        if not _HAS_AUDIO or not self._stems_data:
            return
        if self._playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._playing = True
        self.after(0, lambda: self._play_btn.configure(text="⏸  Pause"))
        self._stream = sd.OutputStream(
            samplerate=self._sr,
            channels=2,
            dtype="float32",
            callback=self._audio_callback,
            finished_callback=self._on_stream_finished,
        )
        self._stream.start()
        self._update_progress()

    def _stop_playback(self):
        self._playing = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.after(0, lambda: self._play_btn.configure(text="▶  Play"))

    def _on_stream_finished(self):
        self._playing  = False
        self._play_pos = 0
        self.after(0, lambda: self._play_btn.configure(text="▶  Play"))
        self.after(0, lambda: self._time_label.configure(text="0:00 / 0:00"))

    def _audio_callback(self, outdata, frames, time_info, status):
        if not self._stems_data or self._play_pos >= self._max_len:
            outdata[:] = 0
            raise sd.CallbackStop()

        mixed  = np.zeros((frames, 2), dtype=np.float32)
        active = 0

        for stem, (data, _) in self._stems_data.items():
            if self._soloed and self._soloed != stem:
                continue
            if self._muted.get(stem):
                continue
            end   = min(self._play_pos + frames, len(data))
            chunk = data[self._play_pos:end]
            if len(chunk) < frames:
                chunk = np.pad(chunk, ((0, frames - len(chunk)), (0, 0)))
            mixed  += chunk
            active += 1

        self._play_pos += frames
        outdata[:] = np.clip(mixed / max(active, 1), -1.0, 1.0)

    def _update_progress(self):
        if not self._playing:
            return
        pos_s   = self._play_pos / self._sr
        total_s = self._max_len  / self._sr
        p = f"{int(pos_s // 60)}:{int(pos_s % 60):02d}"
        t = f"{int(total_s // 60)}:{int(total_s % 60):02d}"
        self._time_label.configure(text=f"{p} / {t}")
        self.after(250, self._update_progress)

    def _toggle_solo(self, stem: str):
        if self._soloed == stem:
            self._soloed = None
            self._solo_btns[stem].configure(fg_color="#2a2a2a")
        else:
            if self._soloed:
                self._solo_btns[self._soloed].configure(fg_color="#2a2a2a")
            self._soloed = stem
            self._solo_btns[stem].configure(fg_color=STEM_COLORS[stem])

    def _toggle_mute(self, stem: str):
        self._muted[stem] = not self._muted[stem]
        self._mute_btns[stem].configure(
            fg_color="#e53935" if self._muted[stem] else "#2a2a2a"
        )

    # ── Save selected stems ───────────────────────────────────────────────────

    def _save_selected_stems(self):
        if not self._stem_dir:
            return
        track_dirs = list((self._stem_dir / "htdemucs").glob("*"))
        if not track_dirs:
            self._log("❌  Could not find stem files.")
            return
        track_dir = track_dirs[0]

        folder_name = self._tagged_folder_name(track_dir.name)
        dest = self.output_dir / "stems" / folder_name
        dest.mkdir(parents=True, exist_ok=True)

        saved = []
        for stem in STEMS:
            if not self._stem_check_vars[stem].get():
                continue
            src = track_dir / f"{stem}.wav"
            if src.exists():
                shutil.copy2(src, dest / f"{stem}.wav")
                saved.append(stem)

        if saved:
            self._log(f"💾  Saved: {', '.join(saved)}")
            self._log(f"   → {dest}")
        else:
            self._log("⚠️  No stems selected.")

    # ── Drum MIDI generation ──────────────────────────────────────────────────

    # General MIDI drum note numbers
    _GM_SNARE   = 38   # Acoustic Snare (also used for claps)
    _GM_HIHAT   = 42   # Closed Hi-Hat

    # Frequency bands (Hz) used to isolate each part from the drum stem.
    # Kick / 808 live below ~200 Hz and are intentionally excluded — they're
    # trivial to add by ear once the snare and hat patterns are down.
    _SNARE_BAND = (250, 4000)     # snare + clap body / noise
    _HIHAT_BAND = (6000, None)    # None -> up to Nyquist

    # Quantize grids, expressed as a fraction of one beat.
    # 0.25 = 1/16 note, 0.125 = 1/32 note (finer, preserves hi-hat rolls).
    _SNARE_GRID = 0.25
    _HIHAT_GRID = 0.125

    def _generate_drum_midi(self):
        """Kick off the MIDI generation in a background thread."""
        if self._track_dir is None:
            self._log("⚠️  Run stem splitting first.")
            return

        drums_path = self._track_dir / "drums.wav"
        if not drums_path.exists():
            self._log("❌  drums.wav not found — make sure stems were split.")
            return

        # Disable button while running
        if self._midi_btn:
            self._midi_btn.configure(state="disabled", text="⏳  Analysing…")
        if self._midi_status_lbl:
            self._midi_status_lbl.configure(text="Detecting onsets…")

        threading.Thread(
            target=self._generate_drum_midi_worker,
            args=(drums_path,),
            daemon=True,
        ).start()

    def _generate_drum_midi_worker(self, drums_path: Path):
        """Background worker: isolate snare/clap and hi-hats by frequency band,
        detect onsets in each band, quantize to a grid, and write one MIDI file
        per part. Kick/808 are deliberately skipped — they share an onset and
        are trivial to add by ear once the snare and hat patterns are in place."""
        try:
            import librosa
            import numpy as np
            try:
                from scipy.signal import butter, sosfilt
            except ImportError:
                self._log("❌  SciPy not installed. Run: pip install scipy")
                self.after(0, lambda: self._midi_btn.configure(
                    state="normal", text="🎹  Generate Drum MIDI"))
                self.after(0, lambda: self._midi_status_lbl.configure(text=""))
                return
            try:
                from midiutil import MIDIFile
            except ImportError:
                self._log("❌  MIDIUtil not installed. Run: pip install MIDIUtil")
                self.after(0, lambda: self._midi_btn.configure(
                    state="normal", text="🎹  Generate Drum MIDI"))
                self.after(0, lambda: self._midi_status_lbl.configure(text=""))
                return

            self._log("━" * 46)
            self._log("🥁   Generating Drum MIDI  (snare/clap + hi-hats)…")
            self._log("━" * 46)

            # ── 1. Load drum stem ──────────────────────────────────────────
            self._log("   Loading drum stem…")
            y, sr = librosa.load(str(drums_path), mono=True, sr=None)

            # ── 2. Estimate tempo (drives the quantize grid) ───────────────
            tempo_result = librosa.beat.beat_track(y=y, sr=sr)
            tempo_val    = tempo_result[0] if isinstance(tempo_result, tuple) else tempo_result
            bpm          = float(np.atleast_1d(tempo_val)[0])
            bpm          = max(60.0, min(bpm, 220.0))
            sec_per_beat = 60.0 / bpm
            self._log(f"   Tempo ≈ {bpm:.1f} BPM")

            # ── Helpers ────────────────────────────────────────────────────
            def _band_filter(sig, lo, hi):
                """4th-order Butterworth band-pass (or high-pass if hi is None)."""
                nyq = sr / 2.0
                if hi is None or hi >= nyq:
                    sos = butter(4, lo / nyq, btype="highpass", output="sos")
                else:
                    sos = butter(4, [lo / nyq, hi / nyq], btype="bandpass", output="sos")
                return sosfilt(sos, sig)

            def _detect(sig, min_gap_s):
                """Return (onset_times_s, normalized_strengths) for a band."""
                hop = 256
                env = librosa.onset.onset_strength(y=sig, sr=sr, hop_length=hop)
                peak = float(env.max()) if len(env) else 0.0
                if peak <= 0:
                    return np.array([]), np.array([])
                env = env / peak                                  # normalize to 0..1
                wait = max(1, int(min_gap_s * sr / hop))          # min frames between hits
                frames = librosa.onset.onset_detect(
                    onset_envelope=env, sr=sr, hop_length=hop,
                    backtrack=True, wait=wait, delta=0.05,
                )
                if not len(frames):
                    return np.array([]), np.array([])
                times     = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
                strengths = env[np.clip(frames, 0, len(env) - 1)]
                return times, strengths

            def _quantize(times, strengths, grid):
                """Snap onsets to the nearest grid slot; collapse collisions,
                keeping the loudest hit. Returns sorted [(beat, strength)]."""
                slots = {}
                for t, s in zip(times, strengths):
                    snapped = round((t / sec_per_beat) / grid) * grid
                    if snapped < 0:
                        continue
                    if snapped not in slots or s > slots[snapped]:
                        slots[snapped] = float(s)
                return sorted(slots.items())

            # ── 3. Snare / clap (mid band, 1/16 grid) ──────────────────────
            self._log("   Detecting snare / clap…")
            snare_hits = _quantize(
                *_detect(_band_filter(y, *self._SNARE_BAND), min_gap_s=0.08),
                self._SNARE_GRID,
            )

            # ── 4. Hi-hats (high band, finer 1/32 grid for rolls) ──────────
            self._log("   Detecting hi-hats…")
            hihat_hits = _quantize(
                *_detect(_band_filter(y, *self._HIHAT_BAND), min_gap_s=0.03),
                self._HIHAT_GRID,
            )

            # ── 5. Write one MIDI file per part ────────────────────────────
            self._log("   Writing MIDI files…")
            stem_name   = self._track_dir.name
            folder_name = self._tagged_folder_name(stem_name)
            midi_dest   = self.output_dir / "stems" / folder_name
            midi_dest.mkdir(parents=True, exist_ok=True)

            # label -> (filename, GM note, note duration in beats, hits)
            part_defs = {
                "snare": ("snare.mid", self._GM_SNARE, self._SNARE_GRID, snare_hits),
                "hihat": ("hihat.mid", self._GM_HIHAT, self._HIHAT_GRID, hihat_hits),
            }

            saved_files = []
            counts = {}
            for label, (fname, gm_note, grid, hits) in part_defs.items():
                counts[label] = len(hits)
                if not hits:
                    self._log(f"   ⚠️  No {label} hits detected — skipping {fname}")
                    continue

                mid = MIDIFile(1, adjust_origin=False)
                mid.addTempo(0, 0, bpm)
                mid.addTrackName(0, 0, label.capitalize())
                for beat_time, strength in hits:
                    # Map onset strength (0..1) → MIDI velocity so ghost notes
                    # and roll dynamics survive.
                    vel = max(40, min(127, int(40 + 87 * strength)))
                    mid.addNote(
                        track=0, channel=9,
                        pitch=gm_note,
                        time=beat_time,
                        duration=grid,
                        volume=vel,
                    )
                with open(str(midi_dest / fname), "wb") as fout:
                    mid.writeFile(fout)
                saved_files.append(fname)
                self._log(f"   💾  {fname}  ({len(hits)} hits)")

            summary = f"snare={counts.get('snare', 0)}  hihat={counts.get('hihat', 0)}"
            self._log(f"✅  Saved {len(saved_files)} MIDI files → {midi_dest}")
            self._log(f"   {summary}  |  BPM: {bpm:.1f}\n")

            self.after(0, lambda: self._midi_status_lbl.configure(
                text=f"✅  {summary}  |  {bpm:.1f} BPM  →  {folder_name}/"
            ))
            self.after(0, lambda: self._midi_btn.configure(
                state="normal", text="🎹  Regenerate Drum MIDI"
            ))

        except Exception as exc:
            import traceback
            self._log(f"❌  Drum MIDI error: {exc}")
            self._log(traceback.format_exc())
            self.after(0, lambda: self._midi_btn.configure(
                state="normal", text="🎹  Generate Drum MIDI"
            ))
            self.after(0, lambda: self._midi_status_lbl.configure(text="❌  Failed — see log"))

    # ── Analyze ───────────────────────────────────────────────────────────────

    def _analyze(self, audio_file: Path):
        import librosa
        import numpy as np

        self._log("   Loading audio…")
        y, sr = librosa.load(str(audio_file), duration=180)

        self._log("   Estimating tempo…")
        tempo_result = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val    = tempo_result[0] if isinstance(tempo_result, tuple) else tempo_result
        bpm          = float(np.atleast_1d(tempo_val)[0])

        self._log("   Detecting key…")
        chroma      = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)

        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        note_names = ["C", "C#", "D", "D#", "E", "F",
                      "F#", "G", "G#", "A", "A#", "B"]

        best_score = -np.inf
        best_key   = "C Major"
        for i in range(12):
            maj = np.corrcoef(np.roll(major_profile, i), chroma_mean)[0, 1]
            mn  = np.corrcoef(np.roll(minor_profile, i), chroma_mean)[0, 1]
            if maj > best_score:
                best_score, best_key = maj, f"{note_names[i]} Major"
            if mn > best_score:
                best_score, best_key = mn, f"{note_names[i]} Minor"

        return best_key, bpm


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
