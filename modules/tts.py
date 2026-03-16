"""
modules/tts.py
--------------
Text-to-speech module using Sarvam AI bulbul:v3.
Plays audio through default audio device (Bluetooth headphones).
Displays text on LCD with Devanagari transliteration support.
LCD scroll and audio playback happen simultaneously.

Dependencies:
    requests, sounddevice, scipy, indic-transliteration

Usage (as module):
    from modules.tts import speak

Usage (standalone test):
    python -m modules.tts
"""

import requests
import base64
import io
import os
import threading
import sounddevice as sd
import scipy.io.wavfile as wav
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

from dotenv import load_dotenv
load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

SARVAM_API_KEY  = os.getenv("SARVAM_API_KEY")
TTS_ENDPOINT    = "https://api.sarvam.ai/text-to-speech"
MODEL           = "bulbul:v3"
SPEAKER         = "ishita"
MAX_CHARS       = 2500
AUDIO_DEVICE    = 1

# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_language(text: str) -> str:
    for char in text:
        if '\u0900' <= char <= '\u097F':
            return 'hi-IN'
    return 'en-IN'

def to_roman(text: str) -> str:
    has_devanagari = any('\u0900' <= ch <= '\u097F' for ch in text)
    if has_devanagari:
        return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    return text

# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str, language: str = None, lcd=None):
    """
    Converts text to speech and plays audio.
    LCD scroll and audio playback happen at the same time.
    """
    if not text.strip():
        return

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]

    if language is None:
        language = detect_language(text)

    print("[TTS] Speaking ({})...".format(language))

    # ── Step 1: Get audio from API first ─────────────────────────────────
    headers = {
        'api-subscription-key': SARVAM_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = {
        'inputs': [text],
        'target_language_code': language,
        'speaker': SPEAKER,
        'model': MODEL,
        'enable_preprocessing': True
    }

    response = requests.post(TTS_ENDPOINT, headers=headers, json=payload)

    if response.status_code != 200:
        print("[TTS] API error {}: {}".format(response.status_code, response.text))
        return

    audio_b64 = response.json().get('audios', [None])[0]
    if not audio_b64:
        print("[TTS] No audio returned.")
        return

    audio_bytes = base64.b64decode(audio_b64)
    sample_rate, audio_data = wav.read(io.BytesIO(audio_bytes))

    # ── Step 2: Play audio and scroll LCD simultaneously ──────────────────
    def play_audio():
        sd.play(audio_data, samplerate=sample_rate, device=AUDIO_DEVICE)
        sd.wait()

    audio_thread = threading.Thread(target=play_audio)
    audio_thread.start()

    if lcd is not None:
        from modules.lcd import lcd_scroll, lcd_show
        lcd_scroll(lcd, to_roman(text), "Speaking")

    audio_thread.join()
    print("[TTS] Done.")

# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from modules.lcd import init_lcd, lcd_show, lcd_close

    print("=" * 40)
    print("  Sarvam AI — Text to Speech")
    print("  Speaker: {} | Model: {}".format(SPEAKER, MODEL))
    print("=" * 40)
    print("Type text and press Enter. Ctrl+C to quit.\n")

    lcd = init_lcd()
    lcd_show(lcd, "  TTS Ready", "Type to speak")

    try:
        while True:
            text = input("[TTS] Enter text: ").strip()
            if text:
                speak(text, lcd=lcd)
    except KeyboardInterrupt:
        print("\n[TTS] Stopped.")
    finally:
        lcd_close(lcd)