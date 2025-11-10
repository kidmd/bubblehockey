# Simple RPi.GPIO Diagnostic Script
# By Gemini
#
# Description:
# This script performs the most basic possible operation with the RPi.GPIO
# library to check if it can communicate with the Pi's hardware.
# It will try to set up GPIO 16 as an output and then clean up.
# If this script fails, the issue is with the RPi.GPIO library installation
# or its compatibility with the OS/hardware.

import RPi.GPIO as GPIO
import time

# Use any free GPIO pin. We used 16 in our previous wiring plan.
TEST_PIN = 16 

print("Attempting to initialize RPi.GPIO...")

try:
    # Set the pin numbering mode
    GPIO.setmode(GPIO.BCM)
    
    # Set up the pin as an output
    print(f"Setting up GPIO {TEST_PIN} as an output...")
    GPIO.setup(TEST_PIN, GPIO.OUT)
    
    print("\n---------------------------------")
    print("SUCCESS! RPi.GPIO is working.")
    print("---------------------------------")
    
    # Blink the pin a few times if an LED is connected
    print("Toggling the pin high and low...")
    GPIO.output(TEST_PIN, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(TEST_PIN, GPIO.LOW)

except Exception as e:
    print("\n---------------------------------")
    print("FAILURE. The error is with RPi.GPIO itself.")
    print(f"Error Details: {e}")
    print("---------------------------------")

finally:
    # Always clean up the GPIO pins
    print("Cleaning up GPIO pins.")
    GPIO.cleanup()
