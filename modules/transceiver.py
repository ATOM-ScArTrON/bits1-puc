"""
modules/transceiver.py
----------------------
Inter-device communication module.
Handles WiFi (demo) and LoRa (production) communication between two RPi 5s.

Dependencies:
    socket (WiFi), LoRa library (TBD)

Usage (as module):
    from modules.transceiver import send, receive

Usage (standalone test):
    python -m modules.transceiver
"""

# TODO: implement WiFi socket comms, then LoRa

def send(message: str):
    """Sends a message to the other device."""
    raise NotImplementedError("Transceiver module not yet implemented.")

def receive() -> str:
    """Receives a message from the other device."""
    raise NotImplementedError("Transceiver module not yet implemented.")

if __name__ == "__main__":
    print("[TX] Transceiver module — not yet implemented.")
