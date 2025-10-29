### Creative Robotics in Spatial Design   Group 8 - Bubblebotics ###
ARIT1507 Creative Robotics in Spatial Design (2025/26 Q1) - Group 8

# General
This project was made for the Q5 studio of Creative Robotics in Spatial Design at TU Delft.
This project controls soft pneumatic actuators (often referred to as 'pedal' and 'bubble') using an ESP32 microcontroller.
The actuators are made of flexible silicone that allow it to bend when air is pumped into it via a small tube.
The ESP32 manages the pumps & valves to enable programmable motion for the soft robotic using voice and button inputs.

---

# Coding aplication
The code used in this project is python which is run trough VS Studio Code, this is done in combination with a small amount of micropython that is run on the ESP32 itself.

---

# Components
The system uses:
- An **ESP32 board** to control the pump and solenoid valves.
- A **MOSFET driver circuit** to switch the pump on/off.
- A **silicone pneumatic pedal / bubble actuator**, which inflates and bends when air is pumped in.
- A **Pump** to inflate the actuators
- A set of **4 valves** to control airflow to and from the actuators



