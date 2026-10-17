import os
import sys
import subprocess
import threading
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import KHMER_VOICES, SOURCE_LANGUAGES, WHISPER_MODELS, BASE_DIR
from processor import StoryTranslationProcessor
from tts_engine import KhmerTTSEngine

app = FastAPI(title="Khmer Story Video Translator & Dubber")

# Mount static web directory
WEB_DIR = BASE_DIR / "web"
WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# Global state
active_processor: Optional[StoryTranslationProcessor] = None
processing_thread: Optional[threading.Thread] = None
current_state = {
    "is_busy": False,
    "stage": "idle",
    "progress": 0,
    "message": "រួចរាល់សម្រាប់ដំណើរការ (Ready)",
    "data": {},
    "logs": []
}
connected_clients: list[WebSocket] = []

def broadcast_state(event_data: dict):
    global current_state
    current_state["stage"] = event_data.get("stage", current_state["stage"])
    current_state["progress"] = event_data.get("progress", current_state["progress"])
    current_state["message"] = event_data.get("message", current_state["message"])
    current_state["data"] = event_data.get("data", current_state["data"])
    
    log_entry = {
        "time": event_data.get("time", ""),
        "stage": current_state["stage"],
        "message": current_state["message"]
    }
    current_state["logs"].append(log_entry)
    if len(current_state["logs"]) > 200:
        current_state["logs"].pop(0)

    # Broadcast via WebSocket if clients connected
    dead_clients = []
    for client in connected_clients:
        try:
            asyncio.run(client.send_json(event_data))
        except Exception:
            dead_clients.append(client)
    for dc in dead_clients:
        if dc in connected_clients:
            connected_clients.remove(dc)

@app.get("/")
def serve_index():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_path))

@app.get("/api/config")
def get_config():
    return {
        "voices": KHMER_VOICES,
        "languages": SOURCE_LANGUAGES,
        "whisper_models": WHISPER_MODELS
    }

@app.get("/api/status")
def get_status():
    return current_state

@app.post("/api/select-video")
def select_video():
    """
    Opens native Windows File Dialog to let user pick any video file.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        
        file_path = filedialog.askopenfilename(
            title="ជ្រើសរើសវីដេអូរឿងដែលត្រូវបកប្រែ (Select Story Video)",
            filetypes=[
                ("Video Files", "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.flv;*.ts;*.m4v"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        
        if not file_path:
            return {"cancelled": True}
            
        p = Path(file_path).resolve()
        size_mb = round(p.stat().st_size / (1024 * 1024), 2)
        return {
            "cancelled": False,
            "file_path": str(p),
            "filename": p.name,
            "folder": str(p.parent),
            "size_mb": size_mb
        }
    except Exception as e:
        return {"error": str(e)}

class ProcessRequest(BaseModel):
    video_path: str
    source_lang: str = "auto"
    whisper_model: str = "base"
    voice_id: str = "km-KH-PisethNeural"
    voice_speed: int = 0
    voice_pitch: int = 0
    separate_bgm: bool = True
    bgm_volume: float = 1.0
    dub_volume: float = 1.2
    orig_voice_volume: float = 0.0
    burn_subtitles: bool = False
    save_stems: bool = False
    gemini_api_key: Optional[str] = None

@app.post("/api/start-translation")
def start_translation(req: ProcessRequest):
    global active_processor, processing_thread, current_state
    
    if current_state["is_busy"]:
        return JSONResponse(status_code=400, content={"error": "ដំណើរការមួយកំពុងដំណើរការហើយ (A task is already running)"})

    current_state["is_busy"] = True
    current_state["stage"] = "starting"
    current_state["progress"] = 1
    current_state["message"] = "កំពុងចាប់ផ្តើម..."
    current_state["logs"] = []
    current_state["data"] = {}

    def runner():
        global active_processor, current_state
        try:
            active_processor = StoryTranslationProcessor(
                settings=req.dict(),
                event_callback=broadcast_state
            )
            result = active_processor.process()
            current_state["is_busy"] = False
        except Exception as e:
            current_state["is_busy"] = False
            current_state["stage"] = "error"
            broadcast_state({
                "stage": "error",
                "progress": 0,
                "message": f"កំហុស: {str(e)}",
                "data": {"error": str(e)}
            })

    processing_thread = threading.Thread(target=runner, daemon=True)
    processing_thread.start()
    
    return {"status": "started"}

@app.post("/api/cancel")
def cancel_translation():
    global active_processor, current_state
    if active_processor:
        active_processor.cancel()
        current_state["is_busy"] = False
        current_state["stage"] = "cancelled"
        current_state["message"] = "បានបញ្ឈប់ដំណើរការ (Cancelled)"
        return {"status": "cancelled"}
    return {"status": "not_running"}

class PreviewVoiceRequest(BaseModel):
    voice_id: str
    text: Optional[str] = "សួស្តីបងប្អូន នេះជាការសាកល្បងសំឡេងបកប្រែរឿងជាភាសាខ្មែរ។"
    speed: int = 0
    pitch: int = 0

@app.post("/api/preview-voice")
def preview_voice(req: PreviewVoiceRequest):
    try:
        tts = KhmerTTSEngine(voice=req.voice_id, speed_pct=req.speed, pitch_hz=req.pitch)
        out_path = BASE_DIR / "temp" / f"preview_{req.voice_id}.mp3"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tts.synthesize_to_file(req.text, str(out_path))
        if out_path.exists():
            return FileResponse(str(out_path), media_type="audio/mpeg")
        raise HTTPException(status_code=500, detail="Voice generation failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OpenFolderRequest(BaseModel):
    folder_or_file: str

@app.post("/api/open-folder")
def open_folder(req: OpenFolderRequest):
    """
    Opens Windows Explorer highlighting the file or opening the folder.
    """
    target = Path(req.folder_or_file).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    
    try:
        if target.is_file():
            # Highlight file in Windows Explorer
            subprocess.Popen(f'explorer /select,"{str(target)}"')
        else:
            subprocess.Popen(f'explorer "{str(target)}"')
        return {"status": "opened"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/video-file")
def get_video_file(path: str):
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(str(p), media_type="video/mp4")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "stage": current_state["stage"],
            "progress": current_state["progress"],
            "message": current_state["message"],
            "data": current_state["data"]
        })
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
