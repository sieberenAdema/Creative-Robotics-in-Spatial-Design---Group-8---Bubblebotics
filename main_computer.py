# Mic -> Google STT -> Local Classifier -> MODE:SLEEP/PLAY/FOCUS over serial
# Make sure to install required packages:
# pip install speechrecognition sentence-transformers scikit-learn joblib pyserial

import os, time, re
import speech_recognition as sr
import serial, serial.tools.list_ports
from sentence_transformers import SentenceTransformer
import joblib
import numpy as np
from collections import deque
os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
import vlc
import tkinter as tk

# ---------------------------------------------------------
# Set VLC DLL path (adjust if your VLC is elsewhere)
os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")

# ---------------------------------------------------------
# Video paths
VIDEO_PATHS = {
    "MODE:SLEEP": "videos/sleep.mp4",
    "MODE:PLAY":  "videos/play.mp4",
    "MODE:FOCUS": "videos/focus.mp4",
}

# ---------------------------------------------------------
# Create the GUI window
root = tk.Tk()
root.title("Ambient Space Display")
root.geometry("1280x720")  # or use fullscreen with root.attributes('-fullscreen', True)

# Create an embedded frame for VLC video
embed_frame = tk.Frame(root, bg="black")
embed_frame.pack(fill="both", expand=True)

# ---------------------------------------------------------
# Create VLC instance and player
instance = vlc.Instance("--no-xlib")
player = instance.media_player_new()

# Embed player in Tkinter window
player.set_hwnd(embed_frame.winfo_id())

# ---------------------------------------------------------
def play_video(mode):
    """Switch video in the same window, keeping position if desired."""
    if mode not in VIDEO_PATHS:
        print(f"[video] Unknown mode: {mode}")
        return

    path = VIDEO_PATHS[mode]
    if not os.path.exists(path):
        print(f"[video] Missing file for {mode}: {path}")
        return

    # optional: remember playback time (if you want continuous space)
    timestamp = player.get_time() if player.is_playing() else 0

    # create new media and set it to player
    media = instance.media_new(path)
    player.set_media(media)
    player.play()

    # wait briefly, then resume at previous timestamp
    time.sleep(0.2)
    player.set_time(timestamp)

    print(f"[video] Switched to {mode} ({path}) at {timestamp/1000:.1f}s")

# Start playing something initially
play_video("MODE:SLEEP")

# You can run `play_video("MODE:PLAY")` etc. from your main logic.
root.after(100, lambda: print("[video] Window ready."))
root.mainloop()

# configuration values
SERIAL_PORT     = "COM3"
BAUD            = 115200
SERIAL_COOLDOWN_S = 3
PRINT_TRANSCRIPTS = True
CONF_THRESHOLD = 0.6  # minimum probability to trust classifier --> more test data = more confidence

# small rolling log for context
CONTEXT_WINDOW = 5
conversation_log = deque(maxlen=CONTEXT_WINDOW)

# serial helper
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

# Speech recognition
rec = sr.Recognizer()
mic = sr.Microphone()

def transcribe_once() -> str | None:
    with mic as source:
        rec.adjust_for_ambient_noise(source, duration=0.4)
        print("Listening...")
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

# Classifier (train before running!)

embedder = SentenceTransformer("embedder_augmented")  # folder created during training
clf = joblib.load("model_classifier_augmented.pkl")

LABEL_MAP = {0: "MODE:SLEEP", 1: "MODE:PLAY", 2: "MODE:FOCUS"}

def classify_mode_local(text: str):
    vec = embedder.encode([text])
    probs = clf.predict_proba(vec)[0]
    pred = int(np.argmax(probs))
    conf = float(np.max(probs))

    if conf < CONF_THRESHOLD:
        print(f"(low confidence: {conf:.2f} — ignoring)")
        return None  # skip uncertain classifications

    return pred

# Mode helpers
def mode_to_command(m: int) -> str:
    return LABEL_MAP[m]

# loop
def main():
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

        # add to context log
        conversation_log.append({"text": text, "mode": cmd})
        print(f"[log] recent: {[c['mode'] for c in conversation_log]}")

        # cooldown before switching mode
        now = time.time()
        if cmd != last_sent and (last_sent is None or now - last_switch_ts >= SERIAL_COOLDOWN_S):
            ser.write((cmd + "\n").encode("utf-8"))
            last_sent = cmd
            last_switch_ts = now
            print(f"→ sent {cmd}")
            
            # play corresponding video
            play_video(cmd)
            
        else:
            print(f"(holding mode: {last_sent})")

if __name__ == "__main__":
    main()
