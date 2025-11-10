# This script will test your RC522 RFID reader.
# Make sure the following files are in the same directory as this script:
#  - MFRC522.py
#  - SimpleMFRC522.py

from SimpleMFRC522 import SimpleMFRC522
import time

try:
    reader = SimpleMFRC522()
    print("RFID Reader Test Initialized")
    print("Hold a card or fob near the reader...")

    while True:
        # Call the read function and store the result in one variable
        result = reader.read()

        # --- THIS IS THE FIX ---
        # Only try to unpack and print the ID if the result is NOT None.
        # This prevents the script from crashing if no card is present.
        if result is not None:
            card_id, text_on_card = result

            print("-" * 20)
            print(f"Card Detected!")
            print(f"  ID: {card_id}")

            # Wait a couple of seconds to prevent reading the same card instantly.
            time.sleep(2)
            print("\nReady for next card...")
        
        # If result is None, the loop will just continue silently
        # and try to read again on the next iteration.
        time.sleep(0.1)


except KeyboardInterrupt:
    print("\nProgram terminated by user.")
except Exception as e:
    print(f"\nAn error occurred: {e}")
    print("\n--- TROUBLESHOOTING ---")
    print("1. Ensure SPI is enabled on your Raspberry Pi ('sudo raspi-config').")
    print("2. Make sure the Pi has been rebooted after enabling SPI.")
    print("3. Double-check the wiring between the Pi and the RC522 reader.")

