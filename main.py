"""
main.py
-------
PUC Device — main entry point.
Orchestrates all modules: Bluetooth, LCD, STT, TTS, Heart Rate, Camera, Transceiver.

Usage:
    sudo python main.py

Note: sudo required for lgpio (LoRa M0/M1 GPIO control)
"""

from modules.bluetooth  import connect as bt_connect, pair_new as bt_pair
from modules.lcd        import init_lcd, lcd_show, lcd_close
from modules.stt        import listen
from modules.tts        import speak
from modules.heart_rate import init_heart_rate, get_bpm, cleanup_heart_rate
from modules.camera     import init_camera, capture, close_camera
from modules.transceiver import Transceiver, handle_lora_command

import time

# ── Device Identity ───────────────────────────────────────────────────────────
# Change to "PUC-2" on the second unit
DEVICE_ID = "PUC-1"

# ── Voice Command Keywords ────────────────────────────────────────────────────

CMD_CAPTURE   = ["capture", "photo", "click"]
CMD_HEARTRATE = ["heart rate", "pulse", "bpm"]
CMD_EXIT      = ["exit", "quit", "stop", "shutdown"]
CMD_LORA_MSG  = ["send message"]
CMD_LORA_HR   = ["send heart rate", "send sensor"]

# ── Command Handler ───────────────────────────────────────────────────────────

def handle_command(transcript: str, lcd, transceiver: Transceiver) -> bool:
    """
    Parses transcript for voice commands and executes them.
    Returns False if exit command detected, True otherwise.
    """
    text = transcript.lower()

    if any(cmd in text for cmd in CMD_EXIT):
        speak("Shutting down. Goodbye.", lcd=lcd)
        lcd_show(lcd, "  Shutting", "   down...")
        return False

    elif any(cmd in text for cmd in CMD_CAPTURE):
        speak("Capturing photo.", lcd=lcd)
        try:
            capture(lcd=lcd)
            speak("Photo captured.", lcd=lcd)
        except Exception as e:
            print("[MAIN] Camera error: {}".format(e))
            speak("Camera error.", lcd=lcd)
            lcd_show(lcd, "Camera error", str(e)[:16])

    elif any(cmd in text for cmd in CMD_HEARTRATE):
        bpm = get_bpm()
        if bpm > 0:
            msg = "Your heart rate is {} beats per minute.".format(int(bpm))
            speak(msg, lcd=lcd)
            lcd_show(lcd, "Heart Rate:", "  {} BPM".format(int(bpm)))
        else:
            speak("Place your finger on the sensor.", lcd=lcd)
            lcd_show(lcd, "Place finger on", "   sensor...   ")

    elif any(cmd in text for cmd in CMD_LORA_MSG):
        # "send message hello are you there" → sends over LoRa
        matched = handle_lora_command(transcript, transceiver)
        if matched:
            speak("Message sent.", lcd=lcd)
            lcd_show(lcd, "LoRa:", "Message sent")
        else:
            speak("Please say the message after send message.", lcd=lcd)

    elif any(cmd in text for cmd in CMD_LORA_HR):
        # "send heart rate" → reads BPM and sends over LoRa
        matched = handle_lora_command(transcript, transceiver)
        if matched:
            speak("Heart rate sent.", lcd=lcd)
            lcd_show(lcd, "LoRa:", "HR sent")
        else:
            speak("Could not read heart rate.", lcd=lcd)

    else:
        speak("You said: {}".format(transcript), lcd=lcd)
        lcd_show(lcd, "Heard:", transcript[:16])

    return True

# ── Transceiver callbacks ─────────────────────────────────────────────────────

def on_lora_message(lcd):
    """Returns a callback that speaks and displays incoming LoRa messages."""
    def _cb(text: str):
        print("[LORA] Incoming: {}".format(text))
        speak(text, lcd=lcd)
        lcd_show(lcd, "LoRa msg:", text[:16])
    return _cb

def on_lora_lcd(lcd):
    """Returns a callback that displays incoming LoRa data on LCD."""
    def _cb(text: str):
        lcd_show(lcd, "LoRa:", text[:16])
    return _cb

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 40)
    print("  PUC Device — Starting Up")
    print("=" * 40)

    # Initialise LCD
    lcd = init_lcd()
    lcd_show(lcd, "  PUC Device", " Starting up...")
    time.sleep(1)

    # Connect Bluetooth
    lcd_show(lcd, "Connecting", "Bluetooth...")
    connected = bt_connect()

    if not connected:
        print("[MAIN] BT connect failed. Entering pairing mode.")
        lcd_show(lcd, "BT failed.", "Pairing mode...")
        speak("Bluetooth not found. Entering pairing mode.", lcd=lcd)
        paired = bt_pair()
        if not paired:
            print("[MAIN] Pairing failed. Continuing without audio.")
            lcd_show(lcd, "No audio.", "Continuing...")
            time.sleep(2)

    # Initialise sensors
    lcd_show(lcd, "Initialising", "sensors...")
    init_heart_rate()
    init_camera()

    # Initialise LoRa transceiver
    lcd_show(lcd, "Initialising", "LoRa...")
    transceiver = Transceiver(
        tts_callback=lambda text: speak(text, lcd=lcd),
        lcd_callback=lambda text: lcd_show(lcd, "LoRa:", text[:16]),
    )
    try:
        transceiver.setup()
        transceiver.start_listening()
        print("[MAIN] LoRa transceiver ready.")
        lcd_show(lcd, "LoRa ready", DEVICE_ID)
        time.sleep(1)
    except Exception as e:
        print("[MAIN] LoRa init failed: {}".format(e))
        lcd_show(lcd, "LoRa failed", str(e)[:16])
        speak("LoRa initialisation failed.", lcd=lcd)
        time.sleep(2)

    # Ready
    speak("PUC device ready.", lcd=lcd)
    lcd_show(lcd, "  PUC Device", "    Ready")
    print("\n[MAIN] Device ready. Listening for commands...")

    try:
        while True:
            transcript = listen(lcd=lcd)

            if not transcript:
                continue

            print("[MAIN] Command: {}".format(transcript))
            should_continue = handle_command(transcript, lcd, transceiver)

            if not should_continue:
                break

    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user.")

    finally:
        lcd_show(lcd, "  Shutting", "   down...")
        time.sleep(1)
        transceiver.teardown()
        lcd_close(lcd)
        close_camera()
        cleanup_heart_rate()
        print("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    main()