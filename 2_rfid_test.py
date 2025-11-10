# This script will test two RC522 RFID readers connected to the same SPI bus.
# Make sure the following files are in the same directory as this script:
#  - MFRC522.py
#  - SimpleMFRC522.py

import time
import sys

# Add the current directory to the path to help find the local libraries
# in case the script is run from another directory.
sys.path.append('.')

from SimpleMFRC522 import SimpleMFRC522

try:
    # Initialize the two readers on their unique Chip Select (CS) pins.
    # The 'device' parameter corresponds to the CE pin (0 for CE0/GPIO8, 1 for CE1/GPIO7).
    # -- Readers have been REVERSED as requested --
    reader_home = SimpleMFRC522(bus=0, device=1, spd=1000000)
    reader_away = SimpleMFRC522(bus=0, device=0, spd=1000000)

    print("Dual RFID Reader Test Initialized")
    print("Hold a card or fob near either reader...")

    while True:
        # --- Check the HOME reader ---
        # read_id_no_block() is non-blocking and returns None if no card is present.
        home_card_id = reader_home.read_id_no_block()
        
        if home_card_id:
            print("-" * 20)
            print("Card Detected on HOME Reader!")
            print(f"  ID: {home_card_id}")
            # Wait a moment to prevent reading the same card multiple times instantly
            time.sleep(2)
            print("\nReady for next card...")

        # --- Check the AWAY reader ---
        away_card_id = reader_away.read_id_no_block()

        if away_card_id:
            print("-" * 20)
            print("Card Detected on AWAY Reader!")
            print(f"  ID: {away_card_id}")
            # Wait a moment to prevent reading the same card multiple times instantly
            time.sleep(2)
            print("\nReady for next card...")

        # A small delay to prevent the loop from consuming 100% CPU
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nProgram terminated by user.")
except Exception as e:
    print(f"\nAn error occurred: {e}")
    print("\n--- TROUBLESHOOTING ---")
    print("1. Ensure SPI is enabled on your Raspberry Pi ('sudo raspi-config').")
    print("2. Make sure the Pi has been rebooted after enabling SPI.")
    print("3. Double-check the wiring for BOTH readers.")
    print("4. Confirm each reader is connected to a unique CS pin (HOME=GPIO7, AWAY=GPIO8).")

