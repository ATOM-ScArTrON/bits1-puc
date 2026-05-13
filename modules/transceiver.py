"""
transceiver.py — LoRa inter-device communication for PUC
Hardware : Waveshare SX1268 433M LoRa HAT
Interface: UART via /dev/ttyS0 (NOT SPI)
Jumpers  : UART selection → B (Pi controls LoRa)
           Mode selection → M0 shorted, M1 shorted (transmission mode)

Both PUC units must have identical freq, air_speed, and net_id.
Change DEVICE_ID to "PUC-2" on the second unit.
"""

import json
import serial
import threading
import time
import logging
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Identity ─────────────────────────────────────────────────────────────────
DEVICE_ID = "PUC-2"       # Change to "PUC-2" on the second unit

# ── Serial port ──────────────────────────────────────────────────────────────
# Pi 5 serial port — confirm with: ls -l /dev/serial*
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE   = 9600        # Must match air_speed setting on both modules

# ── Packet schema ─────────────────────────────────────────────────────────────
# All packets are newline-terminated JSON:
# {"type": "msg"|"sensor", "from": "<id>", "payload": <str or dict>}
# -----------------------------------------------------------------------------


class Transceiver:
    def __init__(
        self,
        tts_callback: Optional[Callable[[str], None]] = None,
        lcd_callback: Optional[Callable[[str], None]] = None,
    ):
        self.tts_callback = tts_callback
        self.lcd_callback = lcd_callback
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None

    # ── Setup / teardown ─────────────────────────────────────────────────────

    def setup(self):
        """Open serial port. Call once before send/listen."""
        try:
            self._ser = serial.Serial(
                port=SERIAL_PORT,
                baudrate=BAUD_RATE,
                timeout=1,
            )
            self._ser.flushInput()
            logger.info("Serial port %s opened at %d baud.", SERIAL_PORT, BAUD_RATE)
        except serial.SerialException as e:
            logger.error("Failed to open serial port: %s", e)
            raise

    def teardown(self):
        """Stop listener and close serial port."""
        self.stop_listening()
        if self._ser and self._ser.is_open:
            self._ser.close()
        logger.info("Transceiver shut down.")

    # ── Send ─────────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> bool:
        """Send a text message to the other PUC unit."""
        return self._send_packet("msg", text)

    def send_sensor(self, heart_rate: int, extra: Optional[dict] = None) -> bool:
        """Send heart rate (and optional extra fields) to the other unit."""
        payload = {"heart_rate": heart_rate}
        if extra:
            payload.update(extra)
        return self._send_packet("sensor", payload)

    def _send_packet(self, ptype: str, payload) -> bool:
        packet = {
            "type": ptype,
            "from": DEVICE_ID,
            "payload": payload,
        }
        try:
            # Newline-terminated so the receiver knows where the packet ends
            data = (json.dumps(packet) + "\n").encode("utf-8")
            with self._lock:
                self._ser.write(data)
            logger.info("Sent [%s]: %s", ptype, payload)
            return True
        except Exception as e:
            logger.error("Send failed: %s", e)
            return False

    # ── Listen ───────────────────────────────────────────────────────────────

    def start_listening(self):
        """Start background thread that reads incoming LoRa packets."""
        if self._running:
            return
        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="lora-listener"
        )
        self._listener_thread.start()
        logger.info("LoRa listener started.")

    def stop_listening(self):
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=3)
        logger.info("LoRa listener stopped.")

    def _listen_loop(self):
        buffer = b""
        while self._running:
            try:
                if self._ser.in_waiting:
                    chunk = self._ser.read(self._ser.in_waiting)
                    buffer += chunk
                    # Process all complete newline-terminated packets
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line.strip():
                            self._handle_packet(line.strip())
                else:
                    time.sleep(0.05)
            except Exception as e:
                logger.warning("Listen error: %s", e)
                time.sleep(0.5)

    def _handle_packet(self, raw: bytes):
        try:
            packet = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Malformed packet: %s | raw: %s", e, raw)
            return

        ptype   = packet.get("type")
        sender  = packet.get("from", "unknown")
        payload = packet.get("payload")

        logger.info("Received [%s] from %s: %s", ptype, sender, payload)

        if ptype == "msg":
            self._on_message(sender, payload)
        elif ptype == "sensor":
            self._on_sensor(sender, payload)
        else:
            logger.warning("Unknown packet type: %s", ptype)

    def _on_message(self, sender: str, text: str):
        display = f"{sender}: {text}"
        if self.lcd_callback:
            self.lcd_callback(display)
        if self.tts_callback:
            self.tts_callback(f"Message from {sender}: {text}")

    def _on_sensor(self, sender: str, data: dict):
        hr = data.get("heart_rate", "?")
        display = f"{sender} HR:{hr}bpm"
        if self.lcd_callback:
            self.lcd_callback(display)
        # Speak an alert only if heart rate is abnormal
        if isinstance(hr, int) and (hr < 50 or hr > 120):
            if self.tts_callback:
                self.tts_callback(
                    f"Alert: {sender} heart rate is {hr} beats per minute."
                )


# ── Voice command handler (call from main.py) ─────────────────────────────────

def handle_lora_command(command: str, transceiver: Transceiver) -> bool:
    """
    Parse a voice command and trigger LoRa send.
    Returns True if a LoRa command was matched.

    Recognised commands:
      "send message <text>"
      "send heart rate" / "send sensor"
    """
    cmd = command.lower().strip()

    if cmd.startswith("send message"):
        text = command[len("send message"):].strip()
        if text:
            return transceiver.send_message(text)
        return False

    if "send heart rate" in cmd or "send sensor" in cmd:
        from modules.heart_rate import get_bpm
        hr = get_bpm()
        if hr and hr > 0:
            return transceiver.send_sensor(int(hr))
        return False

    return False

# ── Standalone Test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "listen"

    def on_msg(text):
        print("[RECEIVED]", text)

    t = Transceiver(tts_callback=on_msg, lcd_callback=on_msg)
    t.setup()

    if mode == "send":
        msg = " ".join(sys.argv[2:]) or "test message"
        print("[TX] Sending: {}".format(msg))
        t.send_message(msg)
        import time; time.sleep(1)

    else:
        print("[RX] Listening on {}... Ctrl+C to stop.".format(SERIAL_PORT))
        t.start_listening()
        try:
            while True:
                import time; time.sleep(1)
        except KeyboardInterrupt:
            print("\n[RX] Stopped.")

    t.teardown()