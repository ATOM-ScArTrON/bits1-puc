def main():
    print("=" * 40)
    print("  PUC Device — Starting Up")
    print("=" * 40)

    # 1. Initialise LCD
    try:
        lcd = init_lcd()
        lcd_show(lcd, "  PUC Device", " Starting up...")
        time.sleep(1)
    except Exception as e:
        print("[MAIN] LCD init failed: {}".format(e))
        lcd = None  # The rest of the system will safely ignore LCD calls

    # 2. Connect Bluetooth
    lcd_show(lcd, "Connecting", "Bluetooth...")
    connected = bt_connect()

    if not connected:
        print("[MAIN] BT connect failed. Entering pairing mode.")
        lcd_show(lcd, "BT failed.", "Pairing mode...")
        speak("Bluetooth not found. Entering pairing mode.", lcd=lcd)
        paired = bt_pair()
        if not paired:
            print("[MAIN] Pairing failed. Continuing without audio.")
            lcd_show(lcd, "No audio.", "Continuing...")
            time.sleep(2)

    # 3. Initialise Heart Rate Sensor
    lcd_show(lcd, "Initialising", "sensors...")
    try:
        init_heart_rate()
    except Exception as e:
        print("[MAIN] Heart Rate init failed: {}".format(e))
        lcd_show(lcd, "HR failed", "Continuing...")
        time.sleep(1)

    # 4. Initialise Camera
    try:
        init_camera()
    except Exception as e:
        print("[MAIN] Camera init failed: {}".format(e))
        lcd_show(lcd, "Camera failed", "Continuing...")
        time.sleep(1)

    # 5. Initialise LoRa transceiver
    lcd_show(lcd, "Initialising", "LoRa...")
    transceiver = Transceiver(
        tts_callback=lambda text: speak(text, lcd=lcd),
        lcd_callback=lambda text: lcd_show(lcd, "LoRa:", text[:16]),
    )
    try:
        transceiver.setup()
        transceiver.start_listening()
        print("[MAIN] LoRa transceiver ready.")
        lcd_show(lcd, "LoRa ready", DEVICE_ID)
        time.sleep(1)
    except Exception as e:
        print("[MAIN] LoRa init failed: {}".format(e))
        lcd_show(lcd, "LoRa failed", str(e)[:16])
        speak("LoRa initialisation failed.", lcd=lcd)
        time.sleep(2)

    # Ready
    speak("PUC device ready.", lcd=lcd)
    lcd_show(lcd, "  PUC Device", "    Ready")
    print("\n[MAIN] Device ready. Listening for commands...")

    try:
        while True:
            transcript = listen(lcd=lcd)

            if not transcript:
                continue

            print("[MAIN] Command: {}".format(transcript))
            should_continue = handle_command(transcript, lcd, transceiver)

            if not should_continue:
                break

    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user.")

    finally:
        # Wrap all shutdown routines in try/except so one failing sensor
        # doesn't prevent the others from cleaning up properly.
        lcd_show(lcd, "  Shutting", "   down...")
        time.sleep(1)
        
        try: transceiver.teardown()
        except: pass
        
        try: close_camera()
        except: pass
        
        try: cleanup_heart_rate()
        except: pass
        
        try: lcd_close(lcd)
        except: pass
        
        print("[MAIN] Shutdown complete.")

if __name__ == "__main__":
    main()