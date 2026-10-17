import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment
import edge_tts

class KhmerTTSEngine:
    def __init__(self, voice: str = "km-KH-PisethNeural", speed_pct: int = 0, pitch_hz: int = 0):
        self.voice = voice
        self.speed_pct = speed_pct # e.g. +10, -5
        self.pitch_hz = pitch_hz   # e.g. +5Hz, -5Hz

    def _get_rate_str(self, additional_speed_pct: int = 0) -> str:
        total = self.speed_pct + additional_speed_pct
        if total >= 0:
            return f"+{total}%"
        else:
            return f"{total}%"

    def _get_pitch_str(self) -> str:
        if self.pitch_hz >= 0:
            return f"+{self.pitch_hz}Hz"
        else:
            return f"{self.pitch_hz}Hz"

    async def _synth_segment(self, text: str, output_path: str, rate_str: str) -> bool:
        try:
            pitch_str = self._get_pitch_str()
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=rate_str,
                pitch=pitch_str
            )
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"TTS synth error for '{text[:20]}...': {e}")
            return False

    def synthesize_to_file(self, text: str, output_path: str, rate_str: str = "+0%") -> bool:
        return asyncio.run(self._synth_segment(text, output_path, rate_str))

    def generate_dubbed_track(self, segments: list, total_duration_sec: float, temp_dir: Path, progress_cb=None) -> str:
        """
        Synthesizes all Khmer segments and places them on a full-length silent audio track
        with millisecond precision according to each segment's start time.
        Returns the path to the synchronized khmer_speech.wav file.
        """
        temp_dir.mkdir(parents=True, exist_ok=True)
        total_duration_ms = int(total_duration_sec * 1000) + 1000
        dubbed_track = AudioSegment.silent(duration=total_duration_ms, frame_rate=44100)
        
        total_segs = len(segments)
        for i, seg in enumerate(segments):
            km_text = seg.get("khmer_text", "").strip()
            if not km_text:
                continue

            start_sec = seg["start"]
            end_sec = seg["end"]
            allowed_duration = max(0.5, end_sec - start_sec)
            start_ms = int(start_sec * 1000)

            # Check next segment start to avoid severe overlap
            next_start_sec = segments[i + 1]["start"] if i + 1 < total_segs else total_duration_sec
            max_duration_before_next = max(allowed_duration, next_start_sec - start_sec - 0.1)

            seg_mp3 = temp_dir / f"seg_{i}.mp3"
            
            # Initial generation at user's base rate
            self.synthesize_to_file(km_text, str(seg_mp3), self._get_rate_str(0))

            if seg_mp3.exists() and os.path.getsize(seg_mp3) > 0:
                try:
                    clip = AudioSegment.from_file(str(seg_mp3))
                    clip_duration_sec = len(clip) / 1000.0

                    # If clip is longer than available window, speed it up
                    if clip_duration_sec > max_duration_before_next:
                        speed_factor = min(1.6, clip_duration_sec / max_duration_before_next)
                        # Re-synthesize with higher rate or use ffmpeg atempo
                        speed_boost_pct = int((speed_factor - 1.0) * 80)
                        if speed_boost_pct > 10:
                            seg_mp3_fast = temp_dir / f"seg_{i}_fast.mp3"
                            self.synthesize_to_file(km_text, str(seg_mp3_fast), self._get_rate_str(speed_boost_pct))
                            if seg_mp3_fast.exists() and os.path.getsize(seg_mp3_fast) > 0:
                                clip = AudioSegment.from_file(str(seg_mp3_fast))

                    # Overlay onto dubbed track
                    dubbed_track = dubbed_track.overlay(clip, position=start_ms)
                except Exception as e:
                    print(f"Error overlaying segment {i}: {e}")

            if progress_cb:
                progress_cb(i + 1, total_segs, km_text)

        output_wav = temp_dir / "dubbed_khmer_speech.wav"
        dubbed_track.export(str(output_wav), format="wav")
        return str(output_wav)
