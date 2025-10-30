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
                                                └──────────────→ VLC → Screen Animation
---

---
## 2) Hardware
# Components
The system uses:
- An **ESP32 board** to control the pump and solenoid valves.
- A **Grove 1.1 MOSFET driver board** to switch the pump on/off.
- Two silicone components, a **silicone pneumatic petal** and a **bubble actuator**, which inflates and bends when air is pumped in.
- A **12v Pump** to inflate the actuators
- A set of **4 12v solenoid valves** to control airflow to and from the actuators
- 3 **Buttons** to mannually actuate the different modes
- A **Breadboard** to connect all components 




# Coding aplication
The code used in this project is python which is run trough VS Studio Code, this is done in combination with a small amount of micropython that is run on the ESP32 itself.

# Code Structure
The main code consists of two files, **main.py** runnning on the ESP32 and **main_with_video.py** running locally on a laptop connected to the ESP32


---

