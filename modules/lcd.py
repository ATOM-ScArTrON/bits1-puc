"""
modules/lcd.py
--------------
Shared LCD module for 1602 I2C LCD (HD44780 with PCF8574 I2C backpack).
Import this in any other module that needs to display text.

Hardware:
    - 1602 I2C LCD (address 0x27)
    - Connected via I2C (SDA: GPIO2, SCL: GPIO3)

Dependencies:
    RPLCD, smbus2

Usage (as module):
    from modules.lcd import init_lcd, lcd_show, lcd_clear, lcd_close, lcd_scroll

Usage (standalone test):
    python -m modules.lcd
"""

from RPLCD.i2c import CharLCD
import time

# ── Configuration ─────────────────────────────────────────────────────────────

LCD_ADDRESS = 0x27
I2C_BUS     = 1
LCD_COLS    = 16
LCD_ROWS    = 2

# ── Core Functions ─────────────────────────────────────────────────────────────

def init_lcd() -> CharLCD:
    """Initialises and returns the LCD object. Call once at startup."""
    lcd = CharLCD(
        i2c_expander='PCF8574',
        address=LCD_ADDRESS,
        port=I2C_BUS,
        cols=LCD_COLS,
        rows=LCD_ROWS,
        dotsize=8
    )
    lcd.clear()
    return lcd

def lcd_show(lcd: CharLCD, line1: str, line2: str = ""):
    """Display two lines on the LCD. Text is truncated to 16 chars per line."""
    lcd.clear()
    lcd.write_string(line1[:LCD_COLS].ljust(LCD_COLS))
    lcd.crlf()
    lcd.write_string(line2[:LCD_COLS].ljust(LCD_COLS))

def lcd_clear(lcd: CharLCD):
    """Clears the LCD screen."""
    lcd.clear()

def lcd_close(lcd: CharLCD):
    """Clears and closes the LCD. Call on script exit."""
    lcd.clear()
    lcd.close(clear=True)

def lcd_scroll(lcd: CharLCD, line1: str, line2: str = "", delay: float = 0.4):
    """
    Scrolls long text across the top row if it exceeds 16 characters.
    line2 stays static on the bottom row.
    """
    if len(line1) <= LCD_COLS:
        lcd_show(lcd, line1, line2)
        return

    padded = line1 + " " * LCD_COLS
    for i in range(len(padded) - LCD_COLS + 1):
        lcd.clear()
        lcd.write_string(padded[i:i + LCD_COLS].ljust(LCD_COLS))
        lcd.crlf()
        lcd.write_string(line2[:LCD_COLS].ljust(LCD_COLS))
        time.sleep(delay)

# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[LCD] Initialising...")
    lcd = init_lcd()

    lcd_show(lcd, "  PUC Device", " Initialising...")
    time.sleep(2)

    lcd_scroll(lcd, "This is a long scrolling message", "Scroll test")
    time.sleep(1)

    print("[LCD] Done.")
    lcd_close(lcd)
