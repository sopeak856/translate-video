import sys
import os
import time
import socket
import threading
import webbrowser
import uvicorn
import webview

# Configure UTF-8 output to prevent Windows cp1252 UnicodeEncodeError
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_free_port(start_port: int = 8000) -> int:
    port = start_port
    while is_port_in_use(port):
        port += 1
    return port

def run_fastapi_server(port: int):
    uvicorn.run("server:app", host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port(8000)
    server_url = f"http://127.0.0.1:{port}"

    # Start FastAPI server in background thread
    server_thread = threading.Thread(target=run_fastapi_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be responsive
    for _ in range(50):
        if is_port_in_use(port):
            break
        time.sleep(0.1)

    print("=" * 60)
    print(" Khmer Story Studio AI (កម្មវិធីបកប្រែរឿង & ញែក BGM)")
    print(f" Web UI running at: {server_url}")
    print("=" * 60)

    # Launch PyWebView desktop application window
    try:
        window = webview.create_window(
            title="Khmer Story Studio AI - កម្មវិធីបកប្រែ និងបញ្ចូលសំឡេងរឿងជាភាសាខ្មែរ",
            url=server_url,
            width=1380,
            height=880,
            min_size=(1024, 700),
            background_color="#090d16"
        )
        webview.start(debug=False)
    except Exception as e:
        print(f"PyWebView window error: {e}. Opening default web browser instead...")
        webbrowser.open(server_url)
        # Keep process alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")

if __name__ == "__main__":
    main()
