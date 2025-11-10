#!/usr/bin/env python

from pirc522 import RFID
import sys

# We will write to block 4, a common user data block.
BLOCK_ADDRESS = 4

# Create an RFID object
rdr = RFID()

try:
    # Get text input from the user
    text = input('New data (up to 16 chars):')

    print("Now place your tag to write")

    # Pad the text with spaces and truncate to 16 characters
    text_padded = text.ljust(16)[:16]
    
    # Convert the string to a list of ASCII values (bytes)
    data_to_write = [ord(c) for c in text_padded]

    # --- RFID Operations ---
    rdr.wait_for_tag()
    (error, tag_type) = rdr.request()
    if not error:
        (error, uid) = rdr.anticoll()
        if not error:
            print("Tag detected, UID:", uid)
            if not rdr.select_tag(uid):
                # Use the default key for MIFARE Classic cards
                if not rdr.card_auth(rdr.auth_a, BLOCK_ADDRESS, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], uid):
                    if not rdr.write(BLOCK_ADDRESS, data_to_write):
                        print("Written successfully!")
                    else:
                        print("Write error.")
                else:
                    print("Authentication error.")
            else:
                print("Failed to select tag.")

finally:
    # Always cleanup
    print("\nCleaning up.")
    rdr.cleanup()
