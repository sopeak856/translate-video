import os
import sys
import subprocess
import shutil
import math
import time
from pathlib import Path
from pydub import AudioSegment

from config import TEMP_DIR
from translator import KhmerTranslator
from tts_engine import KhmerTTSEngine
from audio_separator import AudioSeparator
from transcriber import SpeechTranscriber

def format_srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def write_srt_file(segments: list, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_srt_time(seg["start"])
            end = format_srt_time(seg["end"])
            text = seg.get("khmer_text", seg.get("text", "")).strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def vol_to_db(vol_factor: float) -> float:
    if vol_factor <= 0.001:
        return -120.0
    return 20.0 * math.log10(vol_factor)

class StoryTranslationProcessor:
    def __init__(self, settings: dict, event_callback=None):
        """
        settings keys:
          - video_path: str (absolute path)
          - source_lang: str (e.g. 'auto', 'en', 'zh', 'th')
          - whisper_model: str (e.g. 'base')
          - voice_id: str (e.g. 'km-KH-PisethNeural')
          - voice_speed: int (-50 to 50)
          - voice_pitch: int (-50 to 50)
          - separate_bgm: bool (True to use Demucs)
          - bgm_volume: float (0.0 to 2.0, default 1.0)
          - dub_volume: float (0.5 to 2.0, default 1.2)
          - orig_voice_volume: float (0.0 to 0.5, default 0.0)
          - burn_subtitles: bool
          - save_stems: bool
          - gemini_api_key: str (optional)
        """
        self.settings = settings
        self.event_cb = event_callback
        self.is_cancelled = False

    def emit(self, stage: str, progress: int, message: str, data: dict = None):
        if self.event_cb:
            self.event_cb({
                "stage": stage,
                "progress": progress,
                "message": message,
                "data": data or {}
            })

    def cancel(self):
        self.is_cancelled = True

    def process(self) -> dict:
        video_path = Path(self.settings["video_path"]).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # The user's crucial requirement: Output video goes directly into the ORIGINAL VIDEO FOLDER!
        original_folder = video_path.parent
        stem_name = video_path.stem
        
        output_video_path = original_folder / f"{stem_name}_Khmer_Dubbed.mp4"
        output_srt_path = original_folder / f"{stem_name}_Khmer.srt"
        output_bgm_path = original_folder / f"{stem_name}_BackgroundSound.mp3"

        # Dedicated temporary work directory for this video (use pure ASCII name for tool compatibility)
        import uuid
        job_temp = TEMP_DIR / f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        job_temp.mkdir(parents=True, exist_ok=True)

        try:
            # ----------------------------------------------------
            # STAGE 1: Extract Audio from Video
            # ----------------------------------------------------
            self.emit("extracting", 5, "កំពុងទាញយកសំឡេងចេញពីវីដេអូ...")
            extracted_wav = job_temp / "extracted_audio.wav"
            cmd_extract = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(extracted_wav)
            ]
            subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            raw_audio = AudioSegment.from_file(str(extracted_wav))
            total_duration_sec = len(raw_audio) / 1000.0

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 2: Separate Background Sound (BGM / SFX) & Vocals
            # ----------------------------------------------------
            separate_bgm = self.settings.get("separate_bgm", True)
            vocals_path = str(extracted_wav)
            bgm_path = None

            if separate_bgm:
                self.emit("separating", 15, "កំពុងប្រើ AI Demucs ញែកសំឡេងសាច់រឿង (BGM/SFX) និងសំឡេងនិយាយ...")
                separator = AudioSeparator(model_name="htdemucs")
                demucs_out_dir = job_temp / "demucs"
                
                def demucs_progress(msg):
                    self.emit("separating", 25, msg)

                try:
                    vocals_path, bgm_path = separator.separate(
                        str(extracted_wav), 
                        demucs_out_dir, 
                        progress_cb=demucs_progress
                    )
                    # If user wants to save background audio stem
                    if self.settings.get("save_stems", False) and bgm_path and os.path.exists(bgm_path):
                        shutil.copy2(bgm_path, str(output_bgm_path))
                except Exception as sep_err:
                    print(f"Demucs Warning: {sep_err}. Continuing with original audio track.")
                    self.emit("separating", 25, "AI ញែកសំឡេងមានបញ្ហាស្រាល នឹងបន្តដំណើរការបកប្រែជាមួយសំឡេងដើម...")
                    vocals_path = str(extracted_wav)
                    bgm_path = None
            else:
                self.emit("separating", 25, "រំលងការញែកសំឡេងសាច់រឿង តាមការកំណត់...")

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 3: Speech Transcription (Whisper)
            # ----------------------------------------------------
            self.emit("transcribing", 35, "កំពុងដំណើរការ AI Whisper ស្តាប់ឃ្លានិយាយ និងចាប់យកម៉ោង...")
            whisper_model = self.settings.get("whisper_model", "base")
            source_lang = self.settings.get("source_lang", "auto")
            
            transcriber = SpeechTranscriber(model_name=whisper_model)
            segments = transcriber.transcribe(
                vocals_path,
                language=source_lang,
                progress_cb=lambda msg: self.emit("transcribing", 45, msg)
            )

            if not segments:
                raise ValueError("មិនបានរកឃើញសំឡេងនិយាយនៅក្នុងវីដេអូនេះទេ។ សូមពិនិត្យមើលវីដេអូដើម។")

            self.emit("transcribing", 55, f"រកឃើញ {len(segments)} ឃ្លានិយាយ!", {"total_segments": len(segments)})

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 4: Translate Dialogue into Khmer
            # ----------------------------------------------------
            self.emit("translating", 60, "កំពុងបកប្រែសាច់រឿងជាភាសាខ្មែរ (Khmer Translation)...")
            raw_key = self.settings.get("gemini_api_key")
            api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
            engine = "gemini" if api_key else "google"
            translator = KhmerTranslator(api_key=api_key, engine=engine)

            def trans_progress(idx, total, orig, km):
                pct = 60 + int((idx / total) * 15)
                self.emit("translating", pct, f"កំពុងបកប្រែ {idx}/{total}: {km[:40]}...", {
                    "current": idx,
                    "total": total,
                    "original": orig,
                    "khmer": km
                })

            segments = translator.translate_segments(
                segments, 
                src_lang=source_lang, 
                progress_cb=trans_progress
            )

            # Save SRT Subtitles in original video directory!
            write_srt_file(segments, str(output_srt_path))

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 5: Synthesize Khmer Voice Dubbing (Edge-TTS)
            # ----------------------------------------------------
            self.emit("dubbing", 78, "កំពុងបញ្ចូលសំឡេងនិយាយភាសាខ្មែរ (Edge-TTS Dubbing)...")
            voice_id = self.settings.get("voice_id", "km-KH-PisethNeural")
            speed_pct = int(self.settings.get("voice_speed", 0))
            pitch_hz = int(self.settings.get("voice_pitch", 0))

            tts_engine = KhmerTTSEngine(voice=voice_id, speed_pct=speed_pct, pitch_hz=pitch_hz)

            tts_temp_dir = job_temp / "tts_chunks"
            
            def tts_progress(idx, total, text):
                pct = 78 + int((idx / total) * 12)
                self.emit("dubbing", pct, f"សំឡេងនិយាយខ្មែរ {idx}/{total}: {text[:35]}...", {
                    "current": idx,
                    "total": total,
                    "text": text
                })

            dubbed_speech_wav = tts_engine.generate_dubbed_track(
                segments,
                total_duration_sec,
                tts_temp_dir,
                progress_cb=tts_progress
            )

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 6: Audio Mixing (BGM + Khmer Dub + Ducked Vocals)
            # ----------------------------------------------------
            self.emit("mixing", 92, "កំពុងលាយបញ្ចូលសំឡេងសាច់រឿង (BGM) និងសំឡេងខ្មែរ...")
            bgm_vol = float(self.settings.get("bgm_volume", 1.0))
            dub_vol = float(self.settings.get("dub_volume", 1.2))
            orig_vol = float(self.settings.get("orig_voice_volume", 0.0))

            dub_audio = AudioSegment.from_file(dubbed_speech_wav).apply_gain(vol_to_db(dub_vol))

            if bgm_path and os.path.exists(bgm_path):
                bgm_audio = AudioSegment.from_file(bgm_path).apply_gain(vol_to_db(bgm_vol))
                # Ensure durations align
                if len(bgm_audio) < len(dub_audio):
                    bgm_audio = bgm_audio + AudioSegment.silent(duration=len(dub_audio) - len(bgm_audio))
                final_audio = bgm_audio.overlay(dub_audio)
            else:
                final_audio = dub_audio

            # Add faint original vocal if user requested ducking (e.g. 10%)
            if orig_vol > 0.01 and os.path.exists(vocals_path):
                faint_vocal = AudioSegment.from_file(vocals_path).apply_gain(vol_to_db(orig_vol))
                final_audio = final_audio.overlay(faint_vocal)

            final_audio_path = job_temp / "final_mixed_audio.wav"
            final_audio.export(str(final_audio_path), format="wav")

            if self.is_cancelled: return {"status": "cancelled"}

            # ----------------------------------------------------
            # STAGE 7: Multiplexing Final Video
            # ----------------------------------------------------
            self.emit("muxing", 96, "កំពុងបញ្ចូលសំឡេងចូលក្នុងវីដេអូដើម (Exporting Final Video)...")
            burn_subtitles = self.settings.get("burn_subtitles", False)

            if burn_subtitles:
                # Burn subtitles into video
                escaped_srt = str(output_srt_path).replace("\\", "/").replace(":", "\\:")
                vf_arg = f"subtitles='{escaped_srt}':force_style='FontName=Kantumruy Pro,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1.5,Shadow=1,MarginV=25'"
                cmd_mux = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-i", str(final_audio_path),
                    "-vf", vf_arg,
                    "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest",
                    str(output_video_path)
                ]
            else:
                # Fast remuxing with video copy (takes only ~3 seconds!)
                cmd_mux = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-i", str(final_audio_path),
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest",
                    str(output_video_path)
                ]

            subprocess.run(cmd_mux, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # ----------------------------------------------------
            # STAGE 8: Complete!
            # ----------------------------------------------------
            self.emit("completed", 100, "ការបកប្រែ និងបញ្ចូលសំឡេងជោគជ័យ ១០០%!", {
                "output_video": str(output_video_path),
                "output_srt": str(output_srt_path),
                "output_folder": str(original_folder),
                "duration": total_duration_sec,
                "total_segments": len(segments)
            })

            return {
                "status": "success",
                "output_video": str(output_video_path),
                "output_srt": str(output_srt_path),
                "output_folder": str(original_folder),
                "total_segments": len(segments)
            }

        except Exception as e:
            import traceback
            err_msg = str(e)
            trace = traceback.format_exc()
            print("Processing Error:\n", trace)
            self.emit("error", 0, f"កំហុស (Error): {err_msg}", {"trace": trace})
            raise e
        finally:
            # Clean temporary job files
            try:
                if job_temp.exists():
                    shutil.rmtree(job_temp, ignore_errors=True)
            except Exception:
                pass
