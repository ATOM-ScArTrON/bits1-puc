#!/bin/bash
# setup.sh
# First-time setup script for PUC Device on Raspberry Pi 5.
# Safe to run multiple times — skips already installed dependencies.

echo "========================================"
echo "  PUC Device — Setup"
echo "========================================"

# ── System packages ───────────────────────────────────────────────────────────

if ! dpkg -l | grep -q libportaudio2; then
    echo "[SETUP] Installing libportaudio2..."
    sudo apt install libportaudio2 -y
else
    echo "[SETUP] libportaudio2 already installed, skipping."
fi

# ── Enable I2C ────────────────────────────────────────────────────────────────

if ! ls /dev/i2c* > /dev/null 2>&1; then
    echo "[SETUP] Enabling I2C..."
    sudo raspi-config nonint do_i2c 0
else
    echo "[SETUP] I2C already enabled, skipping."
fi

# ── Python packages ───────────────────────────────────────────────────────────

echo "[SETUP] Installing Python packages..."
sudo pip install -r requirements.txt --break-system-packages 2>&1 | grep -v "already satisfied"

echo ""
echo "========================================"
echo "  Setup complete."
echo "  Run: python main.py"
echo "========================================"