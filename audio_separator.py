import os
import sys
import subprocess
from pathlib import Path

class AudioSeparator:
    def __init__(self, model_name: str = "htdemucs"):
        self.model_name = model_name

    def separate(self, audio_path: str, output_dir: Path, progress_cb=None) -> tuple[str, str]:
        """
        Separates vocal and background sound from an audio file using Demucs.
        Returns (vocals_path, background_sound_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        track_name = Path(audio_path).stem

        if progress_cb:
            progress_cb("កំពុងដំណើរការ AI ញែកសំឡេងសាច់រឿង (Background Sound) និងសំឡេងនិយាយ...")

        # Setup UTF-8 environment to prevent Windows cp1252 UnicodeEncodeError
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        cmd = [
            sys.executable, "-X", "utf8", "-m", "demucs.separate",
            "-n", self.model_name,
            "--two-stems", "vocals",
            "--mp3",
            "-o", str(output_dir),
            str(audio_path)
        ]

        error_lines = []
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            env=env
        )

        for line in process.stdout:
            line_str = line.strip()
            if not line_str:
                continue
            error_lines.append(line_str)
            if len(error_lines) > 40:
                error_lines.pop(0)

            if "%" in line_str and progress_cb:
                # Progress line e.g. 45%|████ ...
                progress_cb(f"AI Demucs: {line_str[:60]}")
            elif "Separating track" in line_str and progress_cb:
                progress_cb(f"កំពុងញែកសាច់រឿង: {track_name}")

        process.wait()

        # Search for generated stems
        vocals = None
        no_vocals = None

        for root, _, files in os.walk(str(output_dir)):
            for f in files:
                f_lower = f.lower()
                if f_lower.startswith("vocals"):
                    vocals = Path(root) / f
                elif f_lower.startswith("no_vocals"):
                    no_vocals = Path(root) / f

        if not vocals or not no_vocals:
            last_err = "\n".join(error_lines[-10:])
            print(f"Demucs execution details:\n{last_err}")
            raise RuntimeError(f"Demucs separation error (Exit code {process.returncode}):\n{last_err}")

        return str(vocals), str(no_vocals)
