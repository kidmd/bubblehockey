# LED Ring Light Tester for Bubble Hockey Dome
# By Gemini
#
# Description:
# This script allows you to fine-tune a specific color for your WS2812B LED ring.
# It displays the current RGB values on the screen and updates the spinning
# LED arc in real-time. A reference list of preset colors is shown on the left.
#
# Controls:
#   - 'R' / 'T' : Increase / Decrease RED value
#   - 'G' / 'H' : Increase / Decrease GREEN value
#   - 'B' / 'N' : Increase / Decrease BLUE value
#   - 'S'         : Toggle between Rotating Arc and Steady On mode.
#   - A single press changes the value by 1.
#   - Hold a key down to scroll through values quickly.
#   - 'ESC'       : Quit the program.
#
# ** IMPORTANT **
# To run this script, you MUST use sudo:
# sudo python3 led_light_tester.py

import pygame
import sys
import time
import board
import neopixel

# --- LED Ring Configuration (Must match scoreboard.py) ---
LED_COUNT = 128
LED_BRIGHTNESS = 1.0 # Use max brightness for testing
LED_PIN = board.D18
RING_DEFINITIONS = [
    (0, 8), (8, 16), (24, 24), (48, 35), (83, 45)
]

# --- Display Configuration ---
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS = 60

# --- Color Definitions ---
# A list of tuples, where each tuple is (Name, (R, G, B))
COLORS = [
    ("Red", (255, 0, 0)),
    ("Green", (0, 255, 0)),
    ("Blue", (0, 0, 255)),
    ("Yellow", (255, 255, 0)),
    ("Cyan", (0, 255, 255)),
    ("Magenta", (255, 0, 255)),
    ("White", (255, 255, 255)),
    ("Orange", (255, 165, 0)),
    ("Lime", (50, 205, 50)),
    ("Pink", (255, 105, 180)),
    ("Gold", (255, 215, 0)),
    ("Teal", (0, 128, 128)),
    ("Purple", (128, 0, 128)),
    ("Sky Blue", (135, 206, 235)),
    ("Crimson", (220, 20, 60)),
    ("Lavender", (230, 230, 250))
]

def main():
    # --- Pygame & NeoPixel Setup ---
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    pygame.display.set_caption("LED RGB Value Tuner")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('monospace', 150, bold=True)
    small_font = pygame.font.SysFont('monospace', 50, bold=True)
    reference_font = pygame.font.SysFont('monospace', 30, bold=True)
    
    try:
        pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
        print("LED Ring initialized successfully.")
    except Exception as e:
        print(f"ERROR: Could not initialize LED Ring: {e}")
        print("Please make sure the library is installed and you are running with 'sudo'.")
        pygame.quit()
        sys.exit()

    # --- Main Loop Variables ---
    running = True
    frame_counter = 0
    # Start with white color
    red_val, green_val, blue_val = 255, 255, 255
    
    is_rotating_mode = True
    
    key_hold_timers = {}
    FAST_SCROLL_DELAY = 30 

    while running:
        # --- Event Handling for SINGLE press ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            
            if event.type == pygame.KEYDOWN:
                key_hold_timers[event.key] = 0 
                if event.key == pygame.K_r: red_val = min(255, red_val + 1)
                if event.key == pygame.K_t: red_val = max(0, red_val - 1)
                if event.key == pygame.K_g: green_val = min(255, green_val + 1)
                if event.key == pygame.K_h: green_val = max(0, green_val - 1)
                if event.key == pygame.K_b: blue_val = min(255, blue_val + 1)
                if event.key == pygame.K_n: blue_val = max(0, blue_val - 1)
                if event.key == pygame.K_s:
                    is_rotating_mode = not is_rotating_mode
        
            if event.type == pygame.KEYUP:
                if event.key in key_hold_timers:
                    del key_hold_timers[event.key]

        # --- Handle Held-Down Keys for FAST scrolling ---
        keys = pygame.key.get_pressed()
        for key_code in key_hold_timers:
            if keys[key_code]:
                key_hold_timers[key_code] += 1
                if key_hold_timers[key_code] > FAST_SCROLL_DELAY:
                    if key_code == pygame.K_r: red_val = min(255, red_val + 5)
                    if key_code == pygame.K_t: red_val = max(0, red_val - 5)
                    if key_code == pygame.K_g: green_val = min(255, green_val + 5)
                    if key_code == pygame.K_h: green_val = max(0, green_val - 5)
                    if key_code == pygame.K_b: blue_val = min(255, blue_val + 5)
                    if key_code == pygame.K_n: blue_val = max(0, blue_val - 5)

        # Clamp values
        red_val = max(0, min(255, red_val))
        green_val = max(0, min(255, green_val))
        blue_val = max(0, min(255, blue_val))

        active_color = (int(red_val), int(green_val), int(blue_val))

        # --- LED Animation Logic ---
        if is_rotating_mode:
            half_second_in_frames = FPS // 2
            cycle_position = (frame_counter % half_second_in_frames) / half_second_in_frames
            
            pixels.fill((0, 0, 0))

            for start_index, num_leds in RING_DEFINITIONS:
                arc_length = num_leds // 3
                start_of_arc_offset = int(cycle_position * num_leds)
                
                for i in range(arc_length):
                    led_offset = (start_of_arc_offset + i) % num_leds
                    pixel_index = start_index + led_offset
                    if 0 <= pixel_index < LED_COUNT:
                        pixels[pixel_index] = active_color
        else:
            pixels.fill(active_color)
        
        pixels.show()
        frame_counter += 1

        # --- Screen Drawing Logic ---
        screen.fill((0, 0, 0))
        
        # --- Draw Reference Colors on the left ---
        ref_x = 50
        ref_y = 50
        for name, color in COLORS:
            ref_text_str = f"{name:<10} R:{color[0]:<3} G:{color[1]:<3} B:{color[2]:<3}"
            ref_text = reference_font.render(ref_text_str, True, color)
            screen.blit(ref_text, (ref_x, ref_y))
            ref_y += 40

        # --- Draw Adjustable Color Values on the right ---
        red_text = font.render(f"RED:   {red_val}", True, (255, 60, 60))
        screen.blit(red_text, red_text.get_rect(center=(SCREEN_WIDTH / 2 + 300, SCREEN_HEIGHT / 2 - 200)))
        
        green_text = font.render(f"GREEN: {green_val}", True, (60, 255, 60))
        screen.blit(green_text, green_text.get_rect(center=(SCREEN_WIDTH / 2 + 300, SCREEN_HEIGHT / 2)))
        
        blue_text = font.render(f"BLUE:  {blue_val}", True, (60, 60, 255))
        screen.blit(blue_text, blue_text.get_rect(center=(SCREEN_WIDTH / 2 + 300, SCREEN_HEIGHT / 2 + 200)))

        mode_text_str = "Mode: Rotating" if is_rotating_mode else "Mode: Steady"
        mode_text = small_font.render(mode_text_str, True, (200, 200, 200))
        screen.blit(mode_text, mode_text.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100)))
        
        pygame.display.flip()
        
        clock.tick(FPS)

    # --- Cleanup ---
    print("Exiting...")
    pixels.fill((0, 0, 0))
    pixels.show()
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()

