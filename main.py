# esp32_mode_control_serial.py
# Your valve/pump control + buttons + non-blocking serial listener for MODE:SLEEP/PLAY/FOCUS

from machine import Pin, UART
import sys, time

# CONFIGURE PINS (adjust as needed)
# Outputs
PUMP_PIN = 23          # MOSFET SIG (pump)
EXHAUST_VALVE_PIN = 18 # ULN input for exhaust valve (deflate)
PETAL_1_VALVE = 19     # ULN input for Sleep valve
PETAL_2_VALVE = 17     # ULN input for Play valve
BUBBLE_VALVE = 16      # ULN input for Bubble valve

# Inputs (buttons, active LOW)
BTN_SLEEP_PIN = 12
BTN_PLAY_PIN  = 13
BTN_FOCUS_PIN = 14

# Timing (seconds)
INFLATE_TIME = 10
DEFLATE_TIME = 7
DEBOUNCE_MS = 200

# SERIAL MODE
USE_USB_SERIAL = True  # True = read commands from USB CDC (no extra wires)
# If you want UART pins instead, set to False and configure below:
UART_PORT = 2           # UART(2) is usually free
UART_BAUD = 115200
UART_TX = 4             # pick free pins that don't clash!
UART_RX = 2

# SETUP HARDWARE
pump = Pin(PUMP_PIN, Pin.OUT)
exhaust_valve = Pin(EXHAUST_VALVE_PIN, Pin.OUT)
P_1_valve = Pin(PETAL_1_VALVE, Pin.OUT)
P_2_valve = Pin(PETAL_2_VALVE, Pin.OUT)
bubble_valve = Pin(BUBBLE_VALVE, Pin.OUT)

btn_sleep = Pin(BTN_SLEEP_PIN, Pin.IN, Pin.PULL_UP)
btn_play  = Pin(BTN_PLAY_PIN, Pin.IN, Pin.PULL_UP)
btn_focus = Pin(BTN_FOCUS_PIN, Pin.IN, Pin.PULL_UP)

if not USE_USB_SERIAL:
    uart = UART(UART_PORT, baudrate=UART_BAUD, tx=UART_TX, rx=UART_RX)

# Ensure everything off initially
def all_off():
    pump.value(0)
    exhaust_valve.value(0)
    P_1_valve.value(0)
    P_2_valve.value(0)
    bubble_valve.value(0)

all_off()

# Mode name constants
MODE_SLEEP = "Sleep"
MODE_PLAY  = "Play"
MODE_FOCUS = "Focus"
current_mode = MODE_PLAY

# HELPER FUNCTIONS
def set_mode_valves(mode):
    if mode == MODE_SLEEP:
        P_1_valve.value(1); P_2_valve.value(0); bubble_valve.value(0); exhaust_valve.value(0)
    elif mode == MODE_PLAY:
        P_1_valve.value(0); P_2_valve.value(0); bubble_valve.value(1); exhaust_valve.value(0)
    elif mode == MODE_FOCUS:
        P_1_valve.value(1); P_2_valve.value(0); bubble_valve.value(1); exhaust_valve.value(0)
    else:
        P_1_valve.value(0); P_2_valve.value(0); bubble_valve.value(0); exhaust_valve.value(0)

def deflate_cycle():
    print("Deflate: opening exhaust")
    pump.value(0)
    # open all valves so everything can dump
    exhaust_valve.value(1)
    P_1_valve.value(1)
    P_2_valve.value(1)
    bubble_valve.value(1)
    time.sleep(DEFLATE_TIME)
    # close exhaust
    exhaust_valve.value(0)
    P_1_valve.value(0)
    P_2_valve.value(0)
    bubble_valve.value(0)
    print("Deflate complete")

def inflate_for_mode(mode):
    print("Inflating for mode:", mode)
    set_mode_valves(mode)
    time.sleep(0.2)  # let valves open
    pump.value(1)
    time.sleep(INFLATE_TIME)
    pump.value(0)
    exhaust_valve.value(0)  # keep mode valves open
    print("Inflation done (pump stopped)")

def change_mode(new_mode):
    global current_mode
    if new_mode == current_mode:
        print("Already in", new_mode, "- no change")
        return
    print("Switching from", current_mode, "to", new_mode)
    deflate_cycle()
    inflate_for_mode(new_mode)
    current_mode = new_mode
    print("Mode is now", current_mode)

print("Starting - inflating initial mode:", current_mode)
inflate_for_mode(current_mode)

# BUTTONS (debounced)
last_btn_times = {"sleep": 0, "play": 0, "focus": 0}
def button_pressed(key):
    now = time.ticks_ms()
    last = last_btn_times[key]
    if time.ticks_diff(now, last) < DEBOUNCE_MS:
        return False
    last_btn_times[key] = now
    return True

# SERIAL PARSER (non-blocking)
# Accepts lines like: MODE:SLEEP / MODE:PLAY / MODE:FOCUS
buf = ""

def poll_serial_line():
    global buf
    try:
        if USE_USB_SERIAL:
            # read one char if available from USB CDC without blocking
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                ch = sys.stdin.read(1)
            else:
                ch = None
        else:
            if not hasattr(uart, "any") or not uart.any():
                ch = None
            else:
                ch = uart.read(1)
                if ch is not None:
                    ch = ch.decode("utf-8", "ignore")
        if ch:
            buf += ch
            if ch == "\n":
                line = buf.strip()
                buf = ""
                return line
    except Exception as e:
        # swallow transient decode/IO issues
        buf = ""
    return None

def handle_command(line: str):
    up = line.strip().upper()
    if up == "MODE:SLEEP":
        change_mode(MODE_SLEEP)
    elif up == "MODE:PLAY":
        change_mode(MODE_PLAY)
    elif up == "MODE:FOCUS":
        change_mode(MODE_FOCUS)
    else:
        print("Unknown command:", line)

# MAIN LOOP

try:
    while True:
        # 1) Serial
        line = poll_serial_line()
        if line:
            print("Received:", line)
            handle_command(line)

        # 2) Buttons (active LOW)
        if btn_sleep.value() == 0 and button_pressed("sleep"):
            change_mode(MODE_SLEEP)
        elif btn_play.value() == 0 and button_pressed("play"):
            change_mode(MODE_PLAY)
        elif btn_focus.value() == 0 and button_pressed("focus"):
            change_mode(MODE_FOCUS)

        time.sleep_ms(30)

except KeyboardInterrupt:
    print("Interrupted, turning everything off")
    all_off()
