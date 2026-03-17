"""
runeflower — YouTube to MP3 Downloader & Analyzer
───────────────────────────────────────────────────
Paste a YouTube URL or search query and this app will:
  1. Download the audio as MP3 via yt-dlp
  2. Detect the BPM and musical key

Dependencies:
  pip install -r requirements.txt
"""

import threading
import sys
import subprocess
from pathlib import Path
from tkinter import filedialog

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
except ImportError:
    print("customtkinter not found. Run: pip install customtkinter")
    sys.exit(1)


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
    try:
        import demucs  # noqa
    except ImportError:
        missing.append("demucs  (run: pip install demucs)")
    import shutil
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp  (run: pip install yt-dlp)")
    return missing


# ──────────────────────────────────────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("runeflower")
        self.geometry("680x580")
        self.minsize(580, 500)
        self.resizable(True, True)
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
        self.output_dir = Path.home() / "Music" / "runeflower"
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
            header,
            text="Download MP3 · Detect Key & BPM",
            font=ctk.CTkFont(size=12),
            text_color="gray"
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
            out_row, text="Browse", width=90, height=38,
            command=self._browse
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
            self,
            text="▶   Download, Analyze & Split",
            height=50,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start
        )
        self.start_btn.pack(fill="x", padx=24, pady=(10, 14))

        # ── Results panel ──
        results_frame = ctk.CTkFrame(self)
        results_frame.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(
            results_frame, text="Results",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(anchor="w", padx=16, pady=(10, 6))

        row = ctk.CTkFrame(results_frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        # BPM box
        bpm_box = ctk.CTkFrame(row, corner_radius=10)
        bpm_box.pack(side="left", expand=True, fill="x", padx=(0, 8))

        ctk.CTkLabel(
            bpm_box, text="BPM",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(pady=(10, 2))

        self.bpm_label = ctk.CTkLabel(
            bpm_box, text="—",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.bpm_label.pack(pady=(0, 10))

        # Key box
        key_box = ctk.CTkFrame(row, corner_radius=10)
        key_box.pack(side="left", expand=True, fill="x", padx=(8, 0))

        ctk.CTkLabel(
            key_box, text="KEY",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(pady=(10, 2))

        self.key_label = ctk.CTkLabel(
            key_box, text="—",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.key_label.pack(pady=(0, 10))

        # Log
        ctk.CTkLabel(
            self, text="Log", font=ctk.CTkFont(size=12, weight="bold"), anchor="w"
        ).pack(anchor="w", padx=26)

        self.log_box = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Courier", size=11)
        )
        self.log_box.pack(fill="both", expand=True, padx=24, pady=(2, 20))
        self.log_box.configure(state="disabled")

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

    def _on_split_toggle(self):
        if self.split_var.get():
            self.start_btn.configure(text="▶   Download, Analyze & Split")
        else:
            self.start_btn.configure(text="▶   Download & Analyze")

    def _set_btn(self, enabled: bool, text: str = None):
        if text is None:
            text = "▶   Download, Analyze & Split" if self.split_var.get() else "▶   Download & Analyze"
        self.after(0, lambda: self.start_btn.configure(
            state="normal" if enabled else "disabled", text=text
        ))

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

        # Reset results
        self.after(0, lambda: self.bpm_label.configure(text="—"))
        self.after(0, lambda: self.key_label.configure(text="—"))

        self._set_btn(False, "⏳  Processing…")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        threading.Thread(target=self._pipeline, args=(url,), daemon=True).start()

    def _pipeline(self, url: str):
        try:
            # Step 1: Download
            self._log("━" * 46)
            self._log("⬇️   Downloading…")
            self._log("━" * 46)
            audio_file = self._download(url)
            if audio_file is None:
                self._log("❌  Download failed. Check the URL and try again.")
                return
            self._log(f"✅  Saved: {audio_file.name}\n")

            # Step 2: Analyze
            self._log("━" * 46)
            self._log("🎵   Analyzing Key & BPM…")
            self._log("━" * 46)
            key, bpm = self._analyze(audio_file)
            self._set_results(bpm, key)
            self._log(f"✅  Done!  BPM: {bpm:.1f}  |  Key: {key}\n")

            # Step 3: Stem splitting (optional)
            if self.split_var.get():
                self._log("━" * 46)
                self._log("🎛️   Splitting stems…  (this may take a few minutes)")
                self._log("━" * 46)
                stems_path = self._split_stems(audio_file)
                if stems_path:
                    self._log(f"✅  Stems saved to: {stems_path}")
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
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", str(self.output_dir / "%(title)s.%(ext)s"),
            "--no-playlist",
            query,
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
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
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        return candidates[0] if candidates else None

    # ── Stem splitting ────────────────────────────────────────────────────────

    def _split_stems(self, audio_file: Path) -> "Path | None":
        stems_out = self.output_dir / "stems"
        stems_out.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "demucs",
            "--out", str(stems_out),
            str(audio_file),
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self._log(f"   {line}")
        proc.wait()

        if proc.returncode != 0:
            return None

        # Demucs outputs to: stems_out/htdemucs/<track_name>/
        track_dir = stems_out / "htdemucs" / audio_file.stem
        return track_dir if track_dir.exists() else stems_out

    # ── Analyze ───────────────────────────────────────────────────────────────

    def _analyze(self, audio_file: Path):
        import librosa
        import numpy as np

        self._log("   Loading audio…")
        y, sr = librosa.load(str(audio_file), duration=180)

        # BPM
        self._log("   Estimating tempo…")
        tempo_result = librosa.beat.beat_track(y=y, sr=sr)
        if isinstance(tempo_result, tuple):
            tempo_val = tempo_result[0]
        else:
            tempo_val = tempo_result
        bpm = float(np.atleast_1d(tempo_val)[0])

        # Key (Krumhansl-Schmuckler)
        self._log("   Detecting key…")
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)

        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F',
                      'F#', 'G', 'G#', 'A', 'A#', 'B']

        best_score = -np.inf
        best_key = "C Major"

        for i in range(12):
            maj = np.corrcoef(np.roll(major_profile, i), chroma_mean)[0, 1]
            mn  = np.corrcoef(np.roll(minor_profile, i), chroma_mean)[0, 1]
            if maj > best_score:
                best_score = maj
                best_key = f"{note_names[i]} Major"
            if mn > best_score:
                best_score = mn
                best_key = f"{note_names[i]} Minor"

        return best_key, bpm


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
