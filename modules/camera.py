"""
modules/camera.py
-----------------
Camera module using Arducam OV2640 (SPI + I2C).
Triggered by voice command "capture" from main.py.

Hardware:
    - Arducam OV2640
    - SPI: CS -> GPIO8 (CE0), MOSI -> GPIO10, MISO -> GPIO9, SCK -> GPIO11
    - I2C: SDA -> GPIO2, SCL -> GPIO3

Dependencies:
    spidev, smbus2, Pillow

Usage (as module):
    from modules.camera import init_camera, capture, close_camera

Usage (standalone test):
    python -m modules.camera
"""

import spidev
import smbus2
import time
import os
from PIL import Image
import io

# ── OV2640 Constants ──────────────────────────────────────────────────────────

ARDUCHIP_MODE      = 0x02
CAM_SPI_MODE       = 0x01
ARDUCHIP_TRIG      = 0x41
CAP_DONE_MASK      = 0x08
ARDUCHIP_FIFO      = 0x04
FIFO_CLEAR_MASK    = 0x01
FIFO_START_MASK    = 0x02
SINGLE_FIFO_READ   = 0x3D
FIFO_SIZE1         = 0x42
FIFO_SIZE2         = 0x43
FIFO_SIZE3         = 0x44
OV2640_CHIPID_HIGH = 0x0A
OV2640_CHIPID_LOW  = 0x0B
OV2640_I2C_ADDR    = 0x30

# ── Camera Class ──────────────────────────────────────────────────────────────

class Camera:
    def __init__(self, spi_bus=0, spi_device=0, i2c_bus=1):
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = 1000000
        self.spi.mode = 0b00
        self.bus = smbus2.SMBus(i2c_bus)
        self._init_camera()

    def _write_reg(self, addr, data):
        self.spi.xfer2([addr | 0x80, data])

    def _read_reg(self, addr):
        return self.spi.xfer2([addr & 0x7F, 0x00])[1]

    def _write_sensor_reg(self, reg, data):
        self.bus.write_byte_data(OV2640_I2C_ADDR, reg, data)
        time.sleep(0.001)

    def _read_sensor_reg(self, reg):
        return self.bus.read_byte_data(OV2640_I2C_ADDR, reg)

    def _init_camera(self):
        print("[CAM] Initialising OV2640...")

        self._write_reg(0x00, 0x55)
        if self._read_reg(0x00) != 0x55:
            raise RuntimeError("[CAM] SPI test failed — check wiring")
        print("[CAM] SPI OK")

        self._write_reg(0x00, 0x00)

        self._write_sensor_reg(0xFF, 0x01)
        vid = self._read_sensor_reg(OV2640_CHIPID_HIGH)
        pid = self._read_sensor_reg(OV2640_CHIPID_LOW)
        if vid != 0x26 or pid not in (0x41, 0x42):
            raise RuntimeError("[CAM] OV2640 not found: VID={} PID={}".format(hex(vid), hex(pid)))
        print("[CAM] OV2640 found — VID={} PID={}".format(hex(vid), hex(pid)))

        self._write_sensor_reg(0xFF, 0x01)
        self._write_sensor_reg(0x12, 0x80)
        time.sleep(0.1)

        self._configure_jpeg_qvga()
        self._write_reg(ARDUCHIP_MODE, CAM_SPI_MODE)
        print("[CAM] Ready.")

    def _configure_jpeg_qvga(self):
        regs = [
            (0xFF, 0x00), (0x2C, 0xFF), (0x2E, 0xDF),
            (0xFF, 0x01), (0x3C, 0x32), (0x11, 0x00),
            (0x09, 0x02), (0x04, 0x28), (0x13, 0xE5),
            (0x14, 0x48), (0x2C, 0x0C), (0x33, 0x78),
            (0x3A, 0x33), (0x3B, 0xFB), (0x3E, 0x00),
            (0x43, 0x11), (0x16, 0x10),
            (0xFF, 0x00), (0xE5, 0x7F), (0xF9, 0xC0),
            (0x41, 0x24), (0xE0, 0x14), (0x76, 0xFF),
            (0x33, 0xA0), (0x42, 0x20), (0x43, 0x18),
            (0x4C, 0x00), (0x87, 0xD5), (0x88, 0x3F),
            (0xD7, 0x03), (0xD9, 0x10), (0xD3, 0x82),
            (0xC0, 0x64), (0xC1, 0x4B), (0x8C, 0x00),
            (0x86, 0x3D), (0x50, 0x00), (0x51, 0xC8),
            (0x52, 0x96), (0x53, 0x00), (0x54, 0x00),
            (0x55, 0x00), (0x57, 0x00), (0x5A, 0x50),
            (0x5B, 0x3C), (0x5C, 0x00), (0xD3, 0x04),
            (0xFF, 0x00), (0xE0, 0x04), (0xC0, 0x64),
            (0xC1, 0x4B), (0x8C, 0x00), (0x86, 0x35),
            (0x50, 0x89), (0x51, 0xC8), (0x52, 0x96),
            (0x53, 0x00), (0x54, 0x00), (0x55, 0x00),
            (0x57, 0x00), (0x5A, 0x50), (0x5B, 0x3C),
            (0x5C, 0x00), (0xE0, 0x00),
        ]
        for reg, val in regs:
            self._write_sensor_reg(reg, val)
        time.sleep(0.05)

    def _burst_read(self, length: int) -> list:
        """Read FIFO byte by byte using xfer2, scan for FF D9 end marker."""
        # First byte: send command, get dummy back
        self.spi.xfer2([SINGLE_FIFO_READ])
        
        data = []
        prev = 0x00
        
        for _ in range(length + 20):
            byte = self.spi.xfer2([SINGLE_FIFO_READ, 0x00])[1]
            data.append(byte)
            if prev == 0xFF and byte == 0xD9:
                break
            prev = byte
        
        return data

    def capture_jpeg(self) -> bytes:
        """Captures and returns raw JPEG bytes using burst read."""
        self._write_reg(ARDUCHIP_FIFO, FIFO_CLEAR_MASK)
        time.sleep(0.1)
        self._write_reg(ARDUCHIP_FIFO, FIFO_START_MASK)
        time.sleep(0.05)
        self._read_reg(ARDUCHIP_TRIG)
        time.sleep(0.05)

        deadline = time.time() + 3.0
        while not (self._read_reg(ARDUCHIP_TRIG) & CAP_DONE_MASK):
            if time.time() > deadline:
                raise RuntimeError("[CAM] Capture timeout — check wiring")
            time.sleep(0.01)

        time.sleep(0.05)
        
        size = (
            self._read_reg(FIFO_SIZE1)
            | (self._read_reg(FIFO_SIZE2) << 8)
            | ((self._read_reg(FIFO_SIZE3) & 0x7F) << 16)
        )
        print("[CAM] FIFO size: {} bytes".format(size))

        if size == 0 or size > 200 * 1024:
            raise RuntimeError("[CAM] Invalid FIFO size: {}".format(size))

        data = self._burst_read(size)

        # Search for FF D8 start marker within first 5 bytes
        start = -1
        for i in range(min(5, len(data) - 1)):
            if data[i] == 0xFF and data[i + 1] == 0xD8:
                start = i
                break

        if start == -1:
            raise RuntimeError("[CAM] JPEG start not found. First 5: {}".format(
                [hex(b) for b in data[:5]]))

        data = data[start:]  # trim leading garbage bytes

        if data[-2] != 0xFF or data[-1] != 0xD9:
            raise RuntimeError("[CAM] Invalid JPEG footer. Last 4: {}".format(
                [hex(b) for b in data[-4:]]))

        print("[CAM] JPEG valid, {} bytes".format(len(data)))
        return bytes(data)

    def close(self):
        self.spi.close()
        self.bus.close()

# ── Module-level camera instance ──────────────────────────────────────────────

_cam = None

# ── Public API ────────────────────────────────────────────────────────────────

def init_camera():
    """Initialises the camera. Call once at startup."""
    global _cam
    _cam = Camera()
    # Dummy capture to warm up the sensor — first frame is often incomplete
    print("[CAM] Warming up sensor...")
    try:
        _cam.capture_jpeg()
    except Exception:
        pass  # expected to fail or be incomplete
    time.sleep(0.5)
    print("[CAM] Camera initialised.")

def capture(filename: str = None, lcd=None) -> str:
    """
    Captures a photo and saves it as a JPEG.
    filename: optional path. Defaults to timestamped file in ~/captures/
    lcd: optional LCD object — shows status on display.
    Returns path to saved file.
    """
    global _cam
    if _cam is None:
        raise RuntimeError("[CAM] Camera not initialised. Call init_camera() first.")

    if filename is None:
        os.makedirs(os.path.expanduser("~/captures"), exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.expanduser("~/captures/{}.jpg".format(timestamp))

    if lcd is not None:
        from modules.lcd import lcd_show
        lcd_show(lcd, "Capturing...", "")

    print("[CAM] Capturing...")
    jpeg_bytes = _cam.capture_jpeg()

    with open(filename, "wb") as f:
        f.write(jpeg_bytes)

    print("[CAM] Saved → {}".format(filename))

    if lcd is not None:
        from modules.lcd import lcd_show
        lcd_show(lcd, "Photo saved!", os.path.basename(filename)[:16])

    return filename

def close_camera():
    """Closes the camera. Call on exit."""
    global _cam
    if _cam is not None:
        _cam.close()
        _cam = None
        print("[CAM] Camera closed.")

# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from modules.lcd import init_lcd, lcd_show, lcd_close

    print("=" * 40)
    print("  Arducam OV2640 — Camera Test")
    print("=" * 40)

    lcd = init_lcd()
    lcd_show(lcd, "  Camera Test", " Initialising...")

    try:
        init_camera()
        lcd_show(lcd, "Camera ready", "Press Enter...")
        input("Press Enter to capture a photo...")
        path = capture(lcd=lcd)
        print("[CAM] Photo saved to: {}".format(path))
        lcd_show(lcd, "Done!", path[-16:])
        time.sleep(2)

    except Exception as e:
        print("[CAM] Error: {}".format(e))
        lcd_show(lcd, "Camera error", str(e)[:16])

    finally:
        close_camera()
        lcd_close(lcd)