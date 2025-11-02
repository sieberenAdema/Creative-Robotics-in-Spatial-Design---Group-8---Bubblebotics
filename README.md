### Creative Robotics in Spatial Design   Group 8 - Bubblebotics ###
ARIT1507 Creative Robotics in Spatial Design (2025/26 Q1) - Group 8 “Bubblebotics”
Soft pneumatic installation controlled by an ESP32 and a local voice interface.

**TL;DR**: Speak a mood (Sleep / Play / Focus) → PC classifies the phrase → sends `MODE:*` over serial → ESP32 drives pump + valves to inflate/deflate a silicone petal and bubble → a synchronized video plays on a screen.

## 1) Project overview
This project explores ambient, soft robotic behaviors for spatial design.
Two soft pneumatic actuators (referred to as 'petal' and 'bubble') are controlled using an ESP32 microcontroller and a local LLM running on a PC to parse voice inputs.

The three modes are:
- **Sleep** — calm, slow inflation (petal only)
- **Play** — lively, bigger motion (petal 2 + bubble)
- **Focus** — poised, attentive motion (petal 1 + bubble)


The actuators are made of flexible silicone that allow it to bend when air is pumped into it via a small tube.

Microphone → SpeechToText → Text Classifier → Serial Communication → ESP32 → Pump/Valves → Actuators
(from Text Classifier) → VLC → Screen Animation


---
## 2) Hardware
**Core components**
- An **ESP32 board (MicroPython)** to control the pump and solenoid valves.
- A **Grove 1.1 MOSFET driver board** to switch the pump on/off.
- Two silicone components, a **silicone pneumatic petal** and a **bubble actuator**, which inflates and bends when air is pumped in.
- A **12v Pump** to inflate the actuators
- A set of **4 12v solenoid valves** to control airflow to and from the actuators
- 3 **Buttons** to mannually actuate the different modes (The buttons are wired to ground. They use the internal Pull-ups on the ESP32)
- A **Breadboard** to connect all components, **tubing**, **printed manifolds**, **wireing** 

### ESP32 pinout
Refer to **wireing.svg** for exact wireing of all components

Making process video:
https://www.youtube.com/embed/A4v-PSnlZ5w?si=yJa3w9C8E-f-ZMew

## 3) Software
- **ESP32 (MicroPython v1.26.1)** runs valve/pump control and button handling.
- **Windows PC (Python)** runs voice → text, classifies to a mode, sends serial command, and drives VLC for videos.  

### Libraries used:
- **speechrecognition** — captures microphone audio and uses Google Web Speech API to transcribe short phrases.
- **sentence-transformers** — embeds text into vectors for semantic classification.
- **scikit-learn** — provides the probabilistic classifier used to map phrases → modes.
- **joblib** — loads the pre‑trained classifier from `model_classifier_augmented.pkl`.
- **numpy** — vector math for embeddings and probabilities.
- **pyserial** — lists serial ports and sends ASCII `MODE:*` lines to the ESP32 at 115200 baud.
- **python-vlc** — plays the inflate/deflate videos and loops the active mode video.
- **tkinter** — simple window to host the embedded VLC player.
- **collections.deque** — lightweight rolling log of recent phrases/modes.
- **MicroPython `machine`, `Pin`, `UART`** — access GPIO and optional UART on the ESP32.
- **MicroPython `select`** — non‑blocking read of USB CDC for serial commands.

## 4) Modes & behaviors
Timing constants (These are still being tuned and depend highly on the strength of pump used and the geometry of the silicone to be inflated):  
`INFLATE_TIME = 12 s` 
`DEFLATE_TIME = 6 s`

**Valve mapping per mode**
- **Sleep** : `Petal 1 = ON`, `Petal 2 = OFF`, `Bubble = OFF`, `Exhaust = OFF`
- **Play** : `Petal 1 = OFF`, `Petal 2 = ON`, `Bubble = ON`,  `Exhaust = OFF`
- **Focus** : `Petal 1 = ON`, `Petal 2 = OFF`, `Bubble = ON`,  `Exhaust = OFF`

**Cycle logic**
1) On mode change: **deflate** (open *all* valves + exhaust for 6 s)  
2) Then **inflate** the new mode: open that modes valves, run pump for 12 s, stop pump.

## 5) Steps required to get up and running
### A) Flash ESP32 with MicroPython (once)

- Use Windows Device Manager to detect which port the ESP32 is connected to
- Get the latest driver for ESP32 from https://micropython.org/download/ESP32_GENERIC/

```CMD
# Install tooling
python -m pip install --upgrade esptool mpremote setuptools
# Erase and flash (adjust COM port and .bin path)
esptool --port COM5 erase_flash
esptool --chip esp32 --port COM5 --baud 460800 \
  write_flash -z 0x1000 "C:\\Users\\flori\\Desktop\\indiv\\ESP32_GENERIC-20250911-v1.26.1.bin"
```
### B) Upload firmware to the board
```CMD
# List files on the board
mpremote connect COM5 fs ls

# Replace existing main.py
mpremote connect COM5 fs rm "main.py"   
mpremote connect COM5 fs cp "C:\\Users\\flori\\Desktop\\indiv\\main.py" :

# Run & view REPL output
mpremote connect COM5 run "C:\\Users\\flori\\Desktop\\indiv\\main.py"
mpremote connect COM5 repl
```
### C) Set up the PC app
```CMD
pip install speechrecognition sentence-transformers scikit-learn joblib pyserial python-vlc tkinter numpy
```
Place the files next to `main_with_video.py`:
```
model_classifier_augmented.pkl
embedder_augmented/            # SentenceTransformer folder or model reference
videos/
  sleep_inflation.mp4
  sleep_deflation.mp4
  play_inflation.mp4
  play_deflation.mp4
  focus_inflation.mp4
  focus_deflation.mp4
```
Ensure **VLC** is installed at `C:\Program Files\VideoLAN\VLC` (or x86). The script auto-adds that path.

### D) Run
```CMD
python path\to\main_with_video.py
```
- The script will auto‑detect the serial port (or set `SERIAL_PORT = "COM3"`).
- Speak phrases like “**I’m tired**” (Sleep), “**let’s play music**” (Play), “**I need to focus**” (Focus).
- The window should loop the current mode’s *inflate* video, and transition with *deflate* → *inflate* on changes.

## 6) Troubleshooting
- **No serial ports found** — Unplug the board. Check Device Manager. Try a different cable (make sure that the micro-USB is actually a data cable); set `SERIAL_PORT` explicitly in the code.
- **`libvlc.dll` not found** — Install VLC (desktop), then re‑run. Paths are auto‑added from `Program Files`.
- **Videos don’t play** — Verify file names and paths in `VIDEO_PATHS`.
- **Classifier always “low confidence”** — Lower `CONF_THRESHOLD` (e.g., 0.3) or add more training data. Speak closer to mic. Reduce background noise.
- **Pump acts weird / Valves act weird** — Check that wiring is correct, check that all wires are still in the right position.

## 7) Tips
- Make sure that the tubing is tight at valves, pump, manifold and silicone.
- Be carefull with the amount of pressure you add into the silicone actuators. In the current set-up the pump is strong enough rip the silicone should it run for too long.
