"""
modules/bluetooth.py
--------------------
Bluetooth audio setup module for Raspberry Pi 5.
Handles scanning, pairing, trusting, connecting, and PipeWire routing.

Dependencies:
    Built-in — uses bluetoothctl and wpctl via subprocess.

Usage (as module):
    from modules.bluetooth import connect, disconnect

Usage (standalone):
    python -m modules.bluetooth
    python -m modules.bluetooth --scan
"""

import subprocess
import sys
import time
import re
import threading

# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_MAC     = "B4:9A:95:52:F4:DE"
DEFAULT_NAME    = "Soundcore Q10i"

SCAN_DURATION   = 12
CONNECT_TIMEOUT = 10
PIPEWIRE_WAIT   = 3

# ── Interactive bluetoothctl Process ──────────────────────────────────────────

class BluetoothCtl:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0
        )
        self.output_lines = []
        self._start_reader()
        time.sleep(1)

    def _start_reader(self):
        def reader():
            for line in self.proc.stdout:
                decoded = line.decode(errors='ignore').strip()
                if decoded:
                    self.output_lines.append(decoded)
        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def send(self, cmd: str, wait: float = 1.0):
        self.proc.stdin.write((cmd + "\n").encode())
        self.proc.stdin.flush()
        time.sleep(wait)

    def get_output(self) -> list:
        lines = self.output_lines.copy()
        self.output_lines.clear()
        return lines

    def close(self):
        self.send("quit", wait=0.5)
        self.proc.terminate()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode().strip()

def parse_devices(lines: list) -> list:
    devices = []
    seen = set()
    for line in lines:
        match = re.search(r"Device ([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(.+)", line)
        if match:
            mac  = match.group(1).upper()
            name = match.group(2).strip()
            if mac not in seen and not re.match(r"^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$", name):
                devices.append((mac, name))
                seen.add(mac)
    return devices

def pick_device(devices: list, title: str = "Available devices") -> tuple:
    if not devices:
        return None, None
    print("\n[BT] {}:".format(title))
    for i, (mac, name) in enumerate(devices):
        print("  [{}] {}  —  {}".format(i + 1, name, mac))
    while True:
        try:
            idx = int(input("\nEnter number to select (0 to cancel): ").strip())
            if idx == 0:
                return None, None
            if 1 <= idx <= len(devices):
                return devices[idx - 1]
            print("Enter a number between 1 and {}.".format(len(devices)))
        except ValueError:
            print("Please enter a valid number.")

def set_default_audio(mac: str, name: str):
    print("[BT] Waiting for PipeWire to register device...")
    time.sleep(PIPEWIRE_WAIT)

    out = _run("wpctl status")
    if name not in out and mac not in out:
        print("[BT] Device not visible in PipeWire. Try again.")
        return

    sink_id = None
    for line in out.splitlines():
        match = re.search(r"\*?\s*(\d+)\.\s+" + re.escape(name), line)
        if match:
            sink_id = match.group(1)
            break

    source_id = None
    for line in out.splitlines():
        if "bluez_input" in line and mac in line:
            match = re.search(r"\*?\s*(\d+)\.", line)
            if match:
                source_id = match.group(1)
                break

    if sink_id:
        _run("wpctl set-default {}".format(sink_id))
        print("[BT] Default audio output → {} (id: {})".format(name, sink_id))
    else:
        print("[BT] Could not find output sink.")

    if source_id:
        _run("wpctl set-default {}".format(source_id))
        print("[BT] Default audio input  → bluez_input (id: {})".format(source_id))
    else:
        print("[BT] No mic source found.")

# ── Public API ────────────────────────────────────────────────────────────────

def connect(mac: str = DEFAULT_MAC, name: str = DEFAULT_NAME) -> bool:
    """
    Connects to a paired BT device and sets it as default audio device.
    Returns True if successful.
    """
    bt = BluetoothCtl()

    bt.send("info {}".format(mac), wait=1.0)
    info = "\n".join(bt.get_output())

    if "Paired: yes" in info:
        if "Connected: yes" in info:
            print("[BT] Already connected to {}.".format(name))
            bt.close()
            set_default_audio(mac, name)
            return True

        print("[BT] Connecting to {}...".format(name))
        bt.send("connect {}".format(mac), wait=2.0)

        connected = False
        for i in range(CONNECT_TIMEOUT):
            bt.send("info {}".format(mac), wait=0.5)
            info = "\n".join(bt.get_output())
            if "Connected: yes" in info:
                connected = True
                break
            print("[BT] Waiting... ({}/{})".format(i + 1, CONNECT_TIMEOUT))

        bt.close()

        if connected:
            print("[BT] Connected to {}.".format(name))
            set_default_audio(mac, name)
            return True
        else:
            print("[BT] Connection failed.")
            return False
    else:
        # Device may be out of range or cache issue — try anyway
        print("[BT] Device status unclear — attempting connect anyway...")
        bt.send("connect {}".format(mac), wait=2.0)

        connected = False
        for i in range(CONNECT_TIMEOUT):
            bt.send("info {}".format(mac), wait=0.5)
            info = "\n".join(bt.get_output())
            if "Connected: yes" in info:
                connected = True
                break
            print("[BT] Waiting... ({}/{})".format(i + 1, CONNECT_TIMEOUT))

        bt.close()

        if connected:
            print("[BT] Connected to {}.".format(name))
            set_default_audio(mac, name)
            return True
        else:
            print("[BT] Device not available.")
            return False

def disconnect(mac: str = DEFAULT_MAC, name: str = DEFAULT_NAME):
    """Disconnects the BT device."""
    bt = BluetoothCtl()
    bt.send("disconnect {}".format(mac), wait=2.0)
    bt.close()
    print("[BT] Disconnected from {}.".format(name))

# ── Standalone ────────────────────────────────────────────────────────────────

def _standalone():
    force_scan = "--scan" in sys.argv
    print("=" * 40)
    print("  Bluetooth Audio Setup")
    print("=" * 40)

    if not force_scan:
        success = connect()
        if success:
            print("\n[BT] Done. You can now run stt.py or tts.py.")
        else:
            print("\n[BT] Switching to scan mode.")
            force_scan = True

    if force_scan:
        bt = BluetoothCtl()
        print("[BT] Scanning for {} seconds...".format(SCAN_DURATION))
        bt.send("scan on", wait=0.5)
        for i in range(SCAN_DURATION):
            time.sleep(1)
            print("[BT] Scanning... ({}/{})".format(i + 1, SCAN_DURATION), end="\r")
        bt.send("scan off", wait=1.0)
        bt.send("devices", wait=1.0)
        lines = bt.get_output()
        print()

        devices = parse_devices(lines)
        if not devices:
            print("[BT] No devices found.")
            bt.close()
            return

        mac, name = pick_device(devices, title="Discovered devices")
        if not mac:
            bt.close()
            return

        bt.send("info {}".format(mac), wait=0.5)
        info = "\n".join(bt.get_output())
        if "Paired: yes" not in info:
            print("[BT] Pairing with {}...".format(name))
            bt.send("pair {}".format(mac), wait=5.0)
            bt.send("trust {}".format(mac), wait=1.0)
            bt.get_output()
            print("[BT] Paired and trusted.")

        bt.send("connect {}".format(mac), wait=2.0)
        connected = False
        for i in range(CONNECT_TIMEOUT):
            bt.send("info {}".format(mac), wait=0.5)
            info = "\n".join(bt.get_output())
            if "Connected: yes" in info:
                connected = True
                break
            print("[BT] Waiting... ({}/{})".format(i + 1, CONNECT_TIMEOUT))

        bt.close()

        if connected:
            print("[BT] Connected to {}.".format(name))
            set_default_audio(mac, name)
            print("\n[BT] Done.")
        else:
            print("[BT] Connection failed.")

if __name__ == "__main__":
    _standalone()
