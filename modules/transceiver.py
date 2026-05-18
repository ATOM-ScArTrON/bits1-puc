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
import sys
from typing import Callable, Optional

# ── Identity ─────────────────────────────────────────────────────────────────
DEVICE_ID = "PUC-2"       # Change to "PUC-2" on the second unit

# ── Serial port ──────────────────────────────────────────────────────────────
# Pi 5 serial port — confirm with: ls -l /dev/serial*
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE   = 9600        # Must match air_speed setting on both modules

# ── Interactive Console State ────────────────────────────────────────────────
_is_prompting = False
_prompt_text = "Enter message: "

def safe_print(text: str):
    """Prints text cleanly, avoiding clashes with an active input() prompt."""
    if _is_prompting:
        # \r moves cursor to start of line, \033[K clears the line
        sys.stdout.write("\r\033[K")
        print(text)
        # Reprint the prompt so the user can continue typing seamlessly
        sys.stdout.write(_prompt_text)
        sys.stdout.flush()
    else:
        print(text)


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
        except serial.SerialException as e:
            safe_print(f"[LORA] Failed to open serial port: {e}")
            raise

    def teardown(self):
        """Stop listener and close serial port."""
        self.stop_listening()
        if self._ser and self._ser.is_open:
            self._ser.close()

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
            return True
        except Exception as e:
            safe_print(f"[LORA] Send failed: {e}")
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
        safe_print("LoRa listener started.")

    def stop_listening(self):
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=3)

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
                safe_print(f"[LORA] Listen error: {e}")
                time.sleep(0.5)

    def _handle_packet(self, raw: bytes):
        try:
            packet = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            safe_print(f"[LORA] Malformed packet: {e} | raw: {raw}")
            return

        ptype   = packet.get("type")
        sender  = packet.get("from", "unknown")
        payload = packet.get("payload")

        if ptype == "msg":
            self._on_message(sender, payload)
        elif ptype == "sensor":
            self._on_sensor(sender, payload)
        else:
            safe_print(f"[LORA] Unknown packet type: {ptype}")

    def _on_message(self, sender: str, text: str):
        safe_print(f"[RECEIVED] Message from {sender}: {text}")
        
        display = f"{sender}: {text}"
        if self.lcd_callback:
            self.lcd_callback(display)
        if self.tts_callback:
            self.tts_callback(f"Message from {sender}: {text}")

        # Reprint STT prompt if we aren't in the interactive terminal loop
        if not _is_prompting:
            print("\n[STT] Press Enter to START recording...")
            sys.stdout.flush()

    def _on_sensor(self, sender: str, data: dict):
        hr = data.get("heart_rate", "?")
        safe_print(f"[RECEIVED] Sensor from {sender} HR: {hr}bpm")
        
        display = f"{sender} HR:{hr}bpm"
        if self.lcd_callback:
            self.lcd_callback(display)
            
        if isinstance(hr, int) and (hr < 50 or hr > 120):
            if self.tts_callback:
                self.tts_callback(
                    f"Alert: {sender} heart rate is {hr} beats per minute."
                )

        # Reprint STT prompt if we aren't in the interactive terminal loop
        if not _is_prompting:
            print("\n[STT] Press Enter to START recording...")
            sys.stdout.flush()


# ── Interactive Input Function ────────────────────────────────────────────────

def interactive_prompt(transceiver: Transceiver, allow_voice=False, lcd=None):
    """
    Brings up the terminal input prompt for sending a message.
    If allow_voice is True, pressing Enter with a blank prompt switches to Voice input.
    """
    global _is_prompting
    global _prompt_text
    
    # Update prompt text based on whether voice is allowed
    if allow_voice:
        _prompt_text = "Enter message (or press ENTER for voice, 'exit' to cancel): "
    else:
        _prompt_text = "Enter message (or 'exit' to cancel): "

    _is_prompting = True
    try:
        sys.stdout.write(_prompt_text)
        sys.stdout.flush()
        msg = input().strip()
    except (KeyboardInterrupt, EOFError):
        msg = "exit"
        print() # Drop to a newline gracefully
    finally:
        _is_prompting = False
        
    if msg.lower() == 'exit':
        return None
        
    # If user left it blank and voice is enabled, fall back to STT
    if not msg and allow_voice:
        safe_print("[LORA] Switching to voice input...")
        from modules.stt import listen
        # listen() will handle its own "Press Enter to start..." prompts
        msg = listen(lcd=lcd)
        if not msg:
            safe_print("[TX] No voice recorded. Cancelled.")
            return False
        
    if msg:
        success = transceiver.send_message(msg)
        if success:
            safe_print(f"[TX] Sent: {msg}")
        else:
            safe_print("[TX] Failed to send.")
        return success
        
    return False


# ── Voice command handler (call from main.py) ─────────────────────────────────

def handle_lora_command(command: str, transceiver: Transceiver, lcd=None) -> bool:
    """
    Parse a voice command and trigger LoRa send.
    """
    cmd = command.lower().strip()

    if "send message" in cmd:
        # Force the interactive prompt instead of auto-sending text.
        # This gives the user the choice between terminal typing or voice dictation.
        status = interactive_prompt(transceiver, allow_voice=True, lcd=lcd)
        return True if status else False

    if "send heart rate" in cmd or "send sensor" in cmd:
        from modules.heart_rate import get_bpm
        hr = get_bpm()
        if hr and hr > 0:
            success = transceiver.send_sensor(int(hr))
            if success:
                safe_print(f"[TX] Sent HR: {int(hr)}bpm")
            return success
        return False

    return False

# ── Standalone Test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    t = Transceiver(tts_callback=lambda x: None, lcd_callback=lambda x: None)
    t.setup()

    print("========================================")
    print("  LoRa Bidirectional Chat Mode")
    print(f"  Listening on {SERIAL_PORT}...")
    print("========================================")
    
    t.start_listening()

    try:
        while True:
            # Standalone test allows voice fallback too, so you can test STT integration
            status = interactive_prompt(t, allow_voice=True)
            
            if status is None:
                break
                
    except KeyboardInterrupt:
        print("\n[LORA] Stopped by user.")
    finally:
        t.teardown()