"""
main.py
-------
PUC Device — main entry point.
Orchestrates all modules: Bluetooth, LCD, STT, TTS, Heart Rate, Camera, Transceiver.

Usage:
    python main.py
"""

from modules.bluetooth  import connect            as bt_connect
from modules.lcd        import init_lcd, lcd_show, lcd_close
from modules.stt        import listen
from modules.tts        import speak
from modules.heart_rate import init_heart_rate, get_bpm, cleanup_heart_rate
from modules.camera     import init_camera, capture, close_camera

import time

# ── Voice Command Keywords ────────────────────────────────────────────────────

CMD_CAPTURE   = ["capture", "photo", "click"]
CMD_HEARTRATE = ["heart rate", "pulse", "bpm"]
CMD_EXIT      = ["exit", "quit", "stop", "shutdown"]

# ── Command Handler ───────────────────────────────────────────────────────────

def handle_command(transcript: str, lcd) -> bool:
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

    else:
        speak("You said: {}".format(transcript), lcd=lcd)
        lcd_show(lcd, "Heard:", transcript[:16])

    return True

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
    bt_connect()

    # Initialise sensors
    lcd_show(lcd, "Initialising", "sensors...")
    init_heart_rate()
    init_camera()

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
            should_continue = handle_command(transcript, lcd)

            if not should_continue:
                break

    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user.")

    finally:
        lcd_show(lcd, "  Shutting", "   down...")
        time.sleep(1)
        lcd_close(lcd)
        close_camera()
        cleanup_heart_rate()
        print("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    main()