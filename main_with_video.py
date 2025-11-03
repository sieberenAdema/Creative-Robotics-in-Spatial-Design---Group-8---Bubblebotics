# voice_to_mode_videos_fixed.py
# Mic → Google STT → Local Classifier → MODE:SLEEP/PLAY/FOCUS over serial
# + VLC video transitions (deflate old mode → inflate new mode)
#
# Requires:
# pip install speechrecognition sentence-transformers scikit-learn joblib pyserial python-vlc tkinter

import os
import time
import threading
import serial, serial.tools.list_ports
import speech_recognition as sr
from sentence_transformers import SentenceTransformer
import joblib
import numpy as np
from collections import deque
import tkinter as tk
import vlc

# ========== VLC SETUP ==========
VLC_PATHS = [
    r"C:\Program Files\VideoLAN\VLC",
    r"C:\Program Files (x86)\VideoLAN\VLC",
]
for p in VLC_PATHS:
    if os.path.exists(os.path.join(p, "libvlc.dll")):
        os.add_dll_directory(p)
        print(f"[VLC] Using VLC from: {p}")
        break

# ========== SERIAL CONFIGURATION ==========
SERIAL_PORT = "COM3"  # Set to None to autodetect
BAUD = 115200
SERIAL_COOLDOWN_S = 3
CONF_THRESHOLD = 0.4   # less strict threshold for smoother recognition
PRINT_TRANSCRIPTS = True
CONTEXT_WINDOW = 5

conversation_log = deque(maxlen=CONTEXT_WINDOW)

# ========== CLASSIFIER LOADING ==========
embedder = SentenceTransformer("embedder_augmented")
clf = joblib.load("model_classifier_augmented.pkl")
LABEL_MAP = {0: "MODE:SLEEP", 1: "MODE:PLAY", 2: "MODE:FOCUS"}

# ========== VIDEO PATHS ==========
# You have 6 videos: 3 inflate + 3 deflate
VIDEO_PATHS = {
    "MODE:SLEEP": {"inflate": "videos/sleep_inflation.mp4", "deflate": "videos/sleep_deflation.mp4"},
    "MODE:PLAY":  {"inflate": "videos/play_inflation.mp4",  "deflate": "videos/play_deflation.mp4"},
    "MODE:FOCUS": {"inflate": "videos/focus_inflation.mp4", "deflate": "videos/focus_deflation.mp4"},
}

# ========== SPEECH RECOGNITION ==========
rec = sr.Recognizer()
mic = sr.Microphone()

def transcribe_once() -> str | None:
    with mic as source:
        rec.adjust_for_ambient_noise(source, duration=0.4)
        print("🎤 Listening...")
        audio = rec.listen(source, phrase_time_limit=8)
    try:
        text = rec.recognize_google(audio)
        if PRINT_TRANSCRIPTS:
            print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("(couldn't understand)")
        return None
    except sr.RequestError as e:
        print(f"(speech service error: {e})")
        return None

# ========== SERIAL HELPERS ==========
def autodetect_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found.")
    for p in ports:
        if any(tag in (p.description or "") for tag in ["USB", "CP210", "CH340", "Silicon", "UART"]):
            return p.device
    return ports[0].device

def open_serial():
    port = SERIAL_PORT or autodetect_port()
    ser = serial.Serial(port, BAUD, timeout=0.2)
    print(f"[serial] connected on {ser.port}")
    time.sleep(1.0)
    return ser

# ========== CLASSIFIER HELPERS ==========
def classify_mode_local(text: str):
    vec = embedder.encode([text])
    probs = clf.predict_proba(vec)[0]
    pred = int(np.argmax(probs))
    conf = float(np.max(probs))
    if conf < CONF_THRESHOLD:
        print(f"(low confidence: {conf:.2f} — ignoring)")
        return None
    print(f"[classifier] predicted {LABEL_MAP[pred]} ({conf:.2f})")
    return pred

def mode_to_command(m: int) -> str:
    return LABEL_MAP[m]

# ========== TKINTER + VLC WINDOW ==========
root = tk.Tk()
root.title("Ambient Space Display")
root.geometry("1280x720")
root.configure(bg="black")

embed_frame = tk.Frame(root, bg="black")
embed_frame.pack(fill="both", expand=True)

instance = vlc.Instance("--no-xlib")
player = instance.media_player_new()
root.update_idletasks()
player.set_hwnd(embed_frame.winfo_id())

# ========== VIDEO CONTROL ==========
player_busy = threading.Event()
current_mode = "MODE:SLEEP"  # start mode

def play_video(path: str, block=False, loop=False, timeout=30):
    """Play a video. Optionally block until finished (with timeout) or loop manually."""
    global player_busy
    if not os.path.exists(path):
        print(f"[video] Missing file: {path}")
        return

    # Stop current playback
    if player.is_playing():
        player.stop()
        time.sleep(0.3)

    media = instance.media_new(path)
    player.set_media(media)
    player.play()
    player_busy.set()
    print(f"[video] playing {os.path.basename(path)}")

    # Attach event BEFORE playback ends
    def on_end(event):
        print(f"[video] finished: {os.path.basename(path)}")
        if loop:
            print(f"[video] looping {os.path.basename(path)}")
            player.play()
        else:
            player_busy.clear()

    em = player.event_manager()
    em.event_detach(vlc.EventType.MediaPlayerEndReached)
    em.event_attach(vlc.EventType.MediaPlayerEndReached, on_end)

    # Blocking mode with timeout
    if block:
        start = time.time()
        while player_busy.is_set():
            time.sleep(0.1)
            if time.time() - start > timeout:
                print(f"[video] timeout waiting for {os.path.basename(path)} to finish")
                player_busy.clear()
                break


def transition_to_mode(new_mode: str):
    """Play deflate of old mode, then inflate of new mode."""
    global current_mode
    if new_mode == current_mode:
        print(f"[video] already in {new_mode}, skipping transition")
        return

    print(f"[video] Transition: {current_mode} → {new_mode}")

    # 1️⃣ Deflate previous mode
    deflate_path = VIDEO_PATHS.get(current_mode, {}).get("deflate")
    if deflate_path:
        play_video(deflate_path, block=True, timeout=25)
    else:
        print(f"[video] no deflate video for {current_mode}")

    # 2️⃣ Inflate new mode (looped)
    inflate_path = VIDEO_PATHS.get(new_mode, {}).get("inflate")
    if inflate_path:
        play_video(inflate_path, loop=True)
    else:
        print(f"[video] no inflate video for {new_mode}")

    current_mode = new_mode


# ========== INITIAL VIDEO ==========
play_video(VIDEO_PATHS["MODE:SLEEP"]["inflate"], loop=True)

# ========== MAIN VOICE + SERIAL LOOP ==========
def voice_loop():
    ser = open_serial()
    last_sent = None
    last_switch_ts = 0
    print("Say something like “I’m tired”, “let’s play music”, or “I need to focus”. CTRL+C to quit.")
    while True:
        text = transcribe_once()
        if not text:
            continue

        m = classify_mode_local(text)
        if m is None:
            print("Please repeat.")
            continue

        cmd = mode_to_command(m)
        conversation_log.append({"text": text, "mode": cmd})
        print(f"[log] recent: {[c['mode'] for c in conversation_log]}")

        now = time.time()
        if cmd != last_sent and (last_sent is None or now - last_switch_ts >= SERIAL_COOLDOWN_S):
            try:
                ser.write((cmd + "\n").encode("utf-8"))
                print(f"→ sent {cmd}")
            except serial.SerialException as e:
                print(f"[serial error] {e}")
                try:
                    ser.close()
                except:
                    pass
                ser = open_serial()
                continue

            last_sent = cmd
            last_switch_ts = now
            transition_to_mode(cmd)
        else:
            print(f"(holding mode: {last_sent})")

# Run the voice loop in the background
threading.Thread(target=voice_loop, daemon=True).start()
root.mainloop()
