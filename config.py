import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Edge-TTS Khmer voices
KHMER_VOICES = [
    {
        "id": "km-KH-PisethNeural",
        "name": "Piseth (ពិសិដ្ឋ)",
        "gender": "Male",
        "desc": "សំឡេងប្រុស ច្បាស់ ធ្ងន់ និងធម្មជាតិ ស័ក្តិសមសម្រាប់រឿងនិទាន និងភាពយន្ត"
    },
    {
        "id": "km-KH-SreymomNeural",
        "name": "Sreymom (ស្រីមុំ)",
        "gender": "Female",
        "desc": "សំឡេងស្រី ស្រទន់ រលូន និងច្បាស់ ស័ក្តិសមសម្រាប់សាច់រឿងរំជួលចិត្ត"
    }
]

# Supported Source Languages for Whisper
SOURCE_LANGUAGES = [
    {"code": "auto", "name": "ស្វែងរកស្វ័យប្រវត្តិ (Auto Detect)"},
    {"code": "en", "name": "អង់គ្លេស (English)"},
    {"code": "zh", "name": "ចិន (Chinese)"},
    {"code": "th", "name": "ថៃ (Thai)"},
    {"code": "ko", "name": "កូរ៉េ (Korean)"},
    {"code": "ja", "name": "ជប៉ុន (Japanese)"},
    {"code": "vi", "name": "វៀតណាម (Vietnamese)"},
    {"code": "fr", "name": "បារាំង (French)"},
    {"code": "es", "name": "អេស្ប៉ាញ (Spanish)"},
    {"code": "ru", "name": "រុស្ស៊ី (Russian)"},
    {"code": "hi", "name": "ហិណ្ឌូ (Hindi)"},
    {"code": "id", "name": "ឥណ្ឌូណេស៊ី (Indonesian)"},
    {"code": "de", "name": "អាល្លឺម៉ង់ (German)"}
]

WHISPER_MODELS = [
    {"id": "tiny", "name": "Tiny (លឿនបំផុត - ស្រាល)", "vram": "~1 GB"},
    {"id": "base", "name": "Base (លឿន និងសមរម្យ - Recommended)", "vram": "~1 GB"},
    {"id": "small", "name": "Small (ច្បាស់ល្អ)", "vram": "~2 GB"},
    {"id": "medium", "name": "Medium (ច្បាស់ខ្លាំង)", "vram": "~5 GB"}
]
