import os
import whisper

class SpeechTranscriber:
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        if self.model is None:
            self.model = whisper.load_model(self.model_name)
        return self.model

    def transcribe(self, audio_path: str, language: str = "auto", progress_cb=None) -> list[dict]:
        """
        Transcribes clean vocals audio using Whisper.
        Returns a list of dicts with 'id', 'start', 'end', 'text'.
        """
        if progress_cb:
            progress_cb(f"កំពុងទាញយក/ដំណើរការ Whisper Model ({self.model_name})...")

        model = self.load_model()

        if progress_cb:
            progress_cb("កំពុងស្តាប់ និងកំណត់ពេលវេលាឃ្លានិយាយ (Timestamps)...")

        options = {
            "task": "transcribe",
            "verbose": False
        }
        if language and language != "auto":
            options["language"] = language

        result = model.transcribe(audio_path, **options)

        segments = []
        for idx, seg in enumerate(result.get("segments", [])):
            text = seg["text"].strip()
            if text:
                segments.append({
                    "id": idx,
                    "start": round(seg["start"], 3),
                    "end": round(seg["end"], 3),
                    "text": text
                })

        return segments
