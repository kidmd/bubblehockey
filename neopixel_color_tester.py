# This script is an interactive NeoPixel color tester.
# It uses Pygame to create a display and allows you to
# adjust the RGB color of the LED strip in real-time.
#
# Must be run with sudo:
# sudo .venv/bin/python neopixel_color_tester.py
#
# --- CONTROLS ---
# Q: Quit
# R / E: Red up / down
# G / F: Green up / down
# B / V: Blue up / down
# (Hold the key to change the value)

import pygame
import board
import neopixel
import sys
import os    # <-- Added this import
import time  # <-- Added this import

# --- Configuration ---
PIXEL_COUNT = 45       # The number of LEDs we want to light
# This pin matches your scoreboard.py setup (BCM 21)
PIXEL_PIN = board.D21
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 400

# --- Initialize NeoPixels ---
try:
    pixels = neopixel.NeoPixel(PIXEL_PIN, PIXEL_COUNT, brightness=0.5, auto_write=False)
    print(f"NeoPixel strip initialized on {PIXEL_PIN} with {PIXEL_COUNT} LEDs.")
except Exception as e:
    print(f"Error initializing NeoPixel strip: {e}")
    print("NOTE: This script must be run with 'sudo' and a virtual environment:")
    print("sudo .venv/bin/python neopixel_color_tester.py")
    sys.exit()

def clear_leds():
    """Turns off all LEDs."""
    print("\nTurning off all LEDs...")
    if pixels:
        pixels.fill((0, 0, 0))
        pixels.show()

def main():
    # --- Initialize Pygame ---
    pygame.init()
    # Set the display driver to something simple (avoids some access errors with sudo)
    os.environ['SDL_VIDEODRIVER'] = 'x11' 
    # Try to set the display, may fail if not connected to monitor
    try:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("NeoPixel Color Tester")
        font = pygame.font.SysFont('monospace', 30, bold=True)
        small_font = pygame.font.SysFont('monospace', 20)
        print("Pygame UI initialized.")
    except pygame.error as e:
        print(f"Could not initialize Pygame display. {e}")
        print("Falling back to command-line only (no UI).")
        print("Press Ctrl+C to exit.")
        # Simple loop to keep LEDs on if UI fails
        try:
            pixels.fill((0, 0, 100)) # Default to Blue
            pixels.show()
            while True: time.sleep(1)
        except KeyboardInterrupt:
            return # This will trigger the 'finally' block

    clock = pygame.time.Clock()

    # --- Color State ---
    r, g, b = 0, 0, 100  # Start with blue
    change_speed = 5  # How fast to change color per key press

    running = True
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False

        # --- Held Key Handling (for smooth color changes) ---
        keys = pygame.key.get_pressed()
        
        # Red controls
        if keys[pygame.K_r]:
            r = min(255, r + change_speed)
        if keys[pygame.K_e]:
            r = max(0, r - change_speed)
            
        # Green controls
        if keys[pygame.K_g]:
            g = min(255, g + change_speed)
        if keys[pygame.K_f]:
            g = max(0, g - change_speed)
            
        # Blue controls
        if keys[pygame.K_b]:
            b = min(255, b + change_speed)
        if keys[pygame.K_v]:
            b = max(0, b - change_speed)

        current_color = (int(r), int(g), int(b))

        # --- Update Hardware ---
        pixels.fill(current_color)
        pixels.show()

        # --- Update Pygame UI ---
        screen.fill((30, 30, 30)) # Dark grey background

        # Draw the color swatch
        pygame.draw.rect(screen, current_color, (50, 50, SCREEN_WIDTH - 100, 150))

        # Draw the text labels
        rgb_text = f"RGB: {r}, {g}, {b}"
        r_text = f"[R] / [E] = RED ({r})"
        g_text = f"[G] / [F] = GREEN ({g})"
        b_text = f"[B] / [V] = BLUE ({b})"
        q_text = "[Q] to QUlT"

        screen.blit(font.render(rgb_text, True, (255, 255, 255)), (50, 220))
        screen.blit(small_font.render(r_text, True, (255, 100, 100)), (50, 280))
        screen.blit(small_font.render(g_text, True, (100, 255, 100)), (50, 310))
        screen.blit(small_font.render(b_text, True, (100, 100, 255)), (50, 340))
        screen.blit(small_font.render(q_text, True, (200, 200, 200)), (SCREEN_WIDTH - 150, 340))

        pygame.display.flip()
        clock.tick(30) # Run at 30 FPS

# --- Main execution ---
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # This catches Ctrl+C
        print("\nCtrl+C detected. Exiting.")
    except Exception as e:
        # Catch any other errors
        print(f"An error occurred: {e}")
    finally:
        # This block runs NO MATTER WHAT
        clear_leds()
        pygame.quit()
        print("Cleanup complete. Exiting program.")