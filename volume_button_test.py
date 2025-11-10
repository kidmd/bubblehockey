from gpiozero import Button
from signal import pause

# Use the same GPIO pin as in the main script for the Switch (SW)
# --- Switched to GPIO 19 for testing ---
BUTTON_PIN = 13

def button_pressed():
    """This function is called when the button is pressed."""
    print("SUCCESS: Button press was detected!")

print(f"Listening for a button press on GPIO {BUTTON_PIN}...")
print("Press the volume knob down to test.")
print("Press Ctrl+C to exit the test.")

try:
    # Setup the button exactly as it is in the scoreboard script
    test_button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.3)

    # Assign the function to the event
    test_button.when_pressed = button_pressed

    # This keeps the script running to listen for the press
    pause()

except Exception as e:
    print(f"An error occurred: {e}")

