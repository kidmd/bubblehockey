# WS2812B LED Ring Test Script
# By Gemini
#
# Description:
# A simple script to test an addressable LED ring connected to a Raspberry Pi.
# This uses Pygame to create a small window and listen for keyboard input
# to trigger different lighting effects.
#
# Make sure you have installed the necessary libraries:
# sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel --break-system-packages
#
# Wiring:
# - LED DIN -> Raspberry Pi GPIO 18
# - LED 5V  -> External 5V Power Supply (+)
# - LED GND -> External 5V Power Supply (-)
# - Pi GND  -> External 5V Power Supply (-) (Common Ground)
#
# Keyboard Controls:
#   - R: Turn all LEDs Red
#   - G: Turn all LEDs Green
#   - B: Turn all LEDs Blue
#   - W: Turn all LEDs White
#   - C: Start a rainbow cycle animation
#   - O: Turn all LEDs Off (clear)
#   - ESC: Quit the program

import time
import board
import neopixel
import pygame
import sys

# --- LED Configuration ---
LED_PIN = board.D18  # GPIO 18
LED_COUNT = 128
# Set brightness to a safe level for testing (0.0 to 1.0)
# WARNING: Setting this to 1.0 will draw a lot of current!
LED_BRIGHTNESS = 0.3

# --- Pygame Setup for Keyboard Input ---
pygame.init()
screen = pygame.display.set_mode((200, 200))
pygame.display.set_caption("LED Test")

# --- LED Initialization ---
try:
    pixels = neopixel.NeoPixel(
        LED_PIN, LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False
    )
    print("LED Ring initialized successfully.")
    print("Press keyboard keys to test effects.")
except Exception as e:
    print(f"ERROR: Could not initialize LED Ring: {e}")
    print("Please check wiring and ensure the script is run with 'sudo'.")
    sys.exit()

# --- Helper Functions for Animations ---

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def rainbow_cycle(wait):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(255):
        for i in range(LED_COUNT):
            pixel_index = (i * 256 // LED_COUNT) + j
            pixels[i] = wheel(pixel_index & 255)
        pixels.show()
        time.sleep(wait)

# --- Main Test Loop ---
running = True
animation_mode = None

while running:
    # Check for keyboard events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            animation_mode = None # Stop any running animation on a new key press
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_r:
                print("Setting color to RED")
                pixels.fill((255, 0, 0))
                pixels.show()
            if event.key == pygame.K_g:
                print("Setting color to GREEN")
                pixels.fill((0, 255, 0))
                pixels.show()
            if event.key == pygame.K_b:
                print("Setting color to BLUE")
                pixels.fill((0, 0, 255))
                pixels.show()
            if event.key == pygame.K_w:
                print("Setting color to WHITE")
                pixels.fill((255, 255, 255))
                pixels.show()
            if event.key == pygame.K_o:
                print("Turning LEDs OFF")
                pixels.fill((0, 0, 0))
                pixels.show()
            if event.key == pygame.K_c:
                print("Starting RAINBOW animation (press another key to stop)")
                animation_mode = 'rainbow'

    # If an animation is active, run one step of it
    if animation_mode == 'rainbow':
        rainbow_cycle(0.001)

# --- Cleanup ---
print("Exiting and turning off LEDs.")
pixels.fill((0, 0, 0))
pixels.show()
pygame.quit()
sys.exit()
