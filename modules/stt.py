"""
modules/stt.py
--------------
Speech-to-text module using Sarvam AI saarika:v2.5.
Records from default audio input (Bluetooth headphones mic).
Press Enter to start recording, Enter again to stop.

Dependencies:
    sounddevice, scipy, numpy, requests

Usage (as module):
    from modules.stt import record, transcribe, listen

Usage (standalone test):
    python -m modules.stt
"""

import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import requests
import tempfile
import os
import threading

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from dotenv import load_dotenv
load_dotenv()

def to_roman(text: str) -> str:
    """Converts Devanagari text to Roman script for LCD display."""
    has_devanagari = any('\u0900' <= ch <= '\u097F' for ch in text)
    if has_devanagari:
        return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    return text

# ── Configuration ─────────────────────────────────────────────────────────────

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
STT_ENDPOINT    = "https://api.sarvam.ai/speech-to-text"
MODEL           = "saarika:v2.5"
LANGUAGE        = "unknown"     # auto-detect English/Hindi
SAMPLE_RATE     = 16000
CHANNELS        = 1
MAX_DURATION    = 29
AUDIO_DEVICE    = 1             # sounddevice device index

# ── Public API ────────────────────────────────────────────────────────────────

def record(lcd=None) -> str:
    """
    Records audio from mic. Press Enter to start, Enter to stop.
    lcd: optional LCD object — shows 'Speaking...' while recording.
    Returns path to saved WAV file, or None if nothing recorded.
    """
    print("\n[STT] Press Enter to START recording...")
    input()

    if lcd is not None:
        from modules.lcd import lcd_show
        lcd_show(lcd, "  Speaking...", "")

    print("[STT] Recording... Press Enter to STOP (max {}s)".format(MAX_DURATION))

    frames = []
    stop_event = threading.Event()

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
        device=AUDIO_DEVICE,
        callback=callback
    )

    with stream:
        stop_thread = threading.Thread(target=lambda: (input(), stop_event.set()))
        stop_thread.daemon = True
        stop_thread.start()
        stop_event.wait(timeout=MAX_DURATION)

    if not frames:
        print("[STT] No audio recorded.")
        return None

    audio_data = np.concatenate(frames, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(tmp.name, SAMPLE_RATE, audio_data)
    print("[STT] Recording saved ({:.1f}s)".format(len(audio_data) / SAMPLE_RATE))
    return tmp.name

def transcribe(audio_path: str, lcd=None) -> str:
    """
    Sends WAV file to Sarvam STT API.
    lcd: optional LCD object — shows transcript after transcription.
    Returns transcript string, or None on failure.
    """
    print("[STT] Transcribing...")

    if lcd is not None:
        from modules.lcd import lcd_show
        lcd_show(lcd, "Transcribing...", "")

    with open(audio_path, 'rb') as f:
        response = requests.post(
            STT_ENDPOINT,
            headers={'api-subscription-key': SARVAM_API_KEY},
            files={'file': ('audio.wav', f, 'audio/wav')},
            data={'model': MODEL, 'language_code': LANGUAGE}
        )

    os.unlink(audio_path)  # clean up temp file

    if response.status_code == 200:
        transcript = response.json().get('transcript', '')
        if lcd is not None and transcript:
            from modules.lcd import lcd_scroll
            lcd_scroll(lcd, to_roman(transcript), "Transcript")
        return transcript
    else:
        print("[STT] API error {}: {}".format(response.status_code, response.text))
        return None

def listen(lcd=None) -> str:
    """
    Convenience function — records and transcribes in one call.
    lcd: optional LCD object for display updates.
    Returns transcript string, or None on failure.
    """
    audio_path = record(lcd=lcd)
    if not audio_path:
        return None
    return transcribe(audio_path, lcd=lcd)

# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from modules.lcd import init_lcd, lcd_show, lcd_close

    print("=" * 40)
    print("  Sarvam AI — Speech to Text")
    print("  Language: auto (English / Hindi)")
    print("=" * 40)

    lcd = init_lcd()
    lcd_show(lcd, "  STT Ready", "Press Enter...")

    try:
        while True:
            transcript = listen(lcd=lcd)
            if transcript:
                print("\n[TRANSCRIPT] {}".format(transcript))
            print("\n[STT] Ready for next recording.")
            lcd_show(lcd, "  STT Ready", "Press Enter...")
    except KeyboardInterrupt:
        print("\n[STT] Stopped.")
    finally:
        lcd_close(lcd)