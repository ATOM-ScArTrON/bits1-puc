"""
modules/heart_rate.py
---------------------
Heart rate reader using digital pulse sensor (D0 output) and RPi.GPIO.
Displays BPM on LCD and terminal.

Hardware:
    - Pulse Sensor (D0 -> GPIO17, Pin 11)
    - 1602 I2C LCD (via modules/lcd.py)

Dependencies:
    RPi.GPIO, RPLCD, smbus2

Usage (as module):
    from modules.heart_rate import init_heart_rate, get_bpm, cleanup_heart_rate

Usage (standalone test):
    python -m modules.heart_rate
"""

import RPi.GPIO as GPIO
import time

# ── Configuration ─────────────────────────────────────────────────────────────

PULSE_PIN       = 17
BEAT_WINDOW     = 5
NO_BEAT_TIMEOUT = 5
BPM_MIN         = 30
BPM_MAX         = 220

# ── Internal State ─────────────────────────────────────────────────────────────

beat_times = []

def _beat_detected(channel):
    beat_times.append(time.time())
    if len(beat_times) > BEAT_WINDOW + 1:
        beat_times.pop(0)

# ── Public API ────────────────────────────────────────────────────────────────

def init_heart_rate():
    """Initialises GPIO and starts interrupt-based beat detection."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PULSE_PIN, GPIO.IN)
    GPIO.add_event_detect(
        PULSE_PIN,
        GPIO.RISING,
        callback=_beat_detected,
        bouncetime=300
    )
    print("[HR] Heart rate sensor initialised.")

def get_bpm() -> float:
    """
    Returns current BPM calculated from recent beat timestamps.
    Returns 0.0 if not enough data or no finger detected.
    """
    if not beat_times:
        return 0.0

    if (time.time() - beat_times[-1]) > NO_BEAT_TIMEOUT:
        beat_times.clear()
        return 0.0

    if len(beat_times) < 2:
        return 0.0

    intervals = [
        beat_times[i] - beat_times[i - 1]
        for i in range(1, len(beat_times))
    ]
    avg_interval = sum(intervals) / len(intervals)

    if avg_interval <= 0:
        return 0.0

    bpm = round(60.0 / avg_interval, 1)

    if bpm < BPM_MIN or bpm > BPM_MAX:
        return 0.0

    return bpm

def cleanup_heart_rate():
    """Cleans up GPIO. Call on exit."""
    GPIO.cleanup()
    print("[HR] GPIO cleaned up.")

# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from modules.lcd import init_lcd, lcd_show, lcd_close

    print("[HR] Initialising...")
    lcd = init_lcd()
    lcd_show(lcd, "Place finger on", "   sensor...   ")
    init_heart_rate()

    print("[HR] Ready. Place finger on sensor. Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
            bpm = get_bpm()

            if bpm == 0.0:
                print("[HR] Waiting for heartbeat...")
                lcd_show(lcd, "Place finger on", "   sensor...   ")
            else:
                print("[BPM] {} BPM".format(bpm))
                lcd_show(lcd, "Heart Rate:", "  {} BPM".format(bpm))

    except KeyboardInterrupt:
        print("\n[HR] Stopped.")
        lcd_show(lcd, "  Shutting", "   down...")
        time.sleep(1)
        lcd_close(lcd)
        cleanup_heart_rate()
