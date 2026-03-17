# PUC Device

Friend/Foe detection communication device for the Indian Army, built on Raspberry Pi 5.

## Features

- Voice biometric authentication (SpeechBrain)
- Heart rate biometric authentication (Pulse Sensor)
- Speech to text (Sarvam AI — saarika:v2.5)
- Text to speech (Sarvam AI — bulbul:v3)
- Voice command integration (capture photo, read heart rate, etc.)
- Inter-device communication (WiFi demo, LoRa production)
- 1602 I2C LCD display

## Hardware

| Component | Interface | Library |
|---|---|---|
| Pulse Sensor | Digital GPIO | RPi.GPIO |
| 1602 LCD | I2C | RPLCD + smbus2 |
| Waveshare WM8960 Audio HAT | I2S | sounddevice |
| Sarvam STT/TTS | HTTP API | requests |
| SpeechBrain voice auth | Python | speechbrain |
| LoRa module | SPI/UART | TBD |
| Bluetooth/WiFi | OS level | socket |

## Setup

```bash
git clone "https://github.com/ATOM-ScArTrON/bits1-puc"
cd puc-device
bash setup.sh
```

## Usage

```bash
python main.py
```

To test individual modules:
```bash
python -m modules.tts
python -m modules.stt
python -m modules.heart_rate
python -m modules.bluetooth
python -m modules.lcd
```

## Configuration

Add your Sarvam API key in `modules/stt.py` and `modules/tts.py`:
```python
SARVAM_API_KEY = "your_key_here"
```

## Project Structure

```
puc-device/
├── main.py               # entry point
├── requirements.txt      # Python dependencies
├── setup.sh              # first-time setup script
├── README.md
└── modules/
    ├── __init__.py
    ├── lcd.py            # 1602 I2C LCD
    ├── bluetooth.py      # Bluetooth audio
    ├── heart_rate.py     # pulse sensor
    ├── stt.py            # speech to text
    ├── tts.py            # text to speech
    ├── camera.py         # photo capture (TODO)
    └── transceiver.py    # inter-device comms (TODO)
```
