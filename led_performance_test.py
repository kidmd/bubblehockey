# NeoPixel LED Strip Final Test Script
# By Gemini
#
# Description:
# Controls a single, long NeoPixel strip divided into three functional segments,
# with independent animations running simultaneously.
#   - Base (0-199): User-selectable solid, chase, and RWB chase modes.
#   - Unused (200-299): Always remains off.
#   - Overhead (300-427): Animation is linked to the base mode.

import time
import board
import neopixel
import pygame
import sys
import math

# --- Configuration for the FINAL COMBINED LED strip ---
LED_PIN = board.D21  # GPIO 21 (PCM)
BASE_COUNT = 200
UNUSED_COUNT = 100
OVERHEAD_COUNT = 128
TOTAL_LED_COUNT = BASE_COUNT + UNUSED_COUNT + OVERHEAD_COUNT
LED_BRIGHTNESS = 0.5

# --- Segment Start Indices ---
BASE_START_INDEX = 0
UNUSED_START_INDEX = BASE_COUNT
OVERHEAD_START_INDEX = BASE_COUNT + UNUSED_COUNT

# --- Goal Animation Configuration ---
GOAL_1_CENTER_LED = 46
GOAL_2_CENTER_LED = 146
GOAL_ANIMATION_DURATION = 3
GOAL_ANIMATION_WIDTH = 40
GOAL_ANIMATION_COLOR = (255, 0, 0)

# --- Overhead Ring Configuration (from scoreboard.py) ---
RING_CONFIG = [8, 16, 24, 35, 45] # UPDATED: New ring LED counts
RING_CUMULATIVE = [sum(RING_CONFIG[:i]) for i in range(len(RING_CONFIG) + 1)]
OVERHEAD_ROTATION_SPEED = 120 # degrees per second

# --- Base Colors ---
BASE_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255),
    (255, 255, 0), (0, 255, 255), (255, 0, 255),
]

# --- Initialize Pygame & NeoPixels ---
pygame.init()
screen = pygame.display.set_mode((200, 200))
pygame.display.set_caption("LED Tester")

pixels = None
try:
    pixels = neopixel.NeoPixel(LED_PIN, TOTAL_LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
    print(f"Single NeoPixel strip initialized on GPIO 21 with {TOTAL_LED_COUNT} LEDs.")
except Exception as e:
    print(f"ERROR: Could not initialize NeoPixel strip. Check wiring/sudo. Details: {e}")
    pygame.quit()
    sys.exit()

# --- Main Program State ---
base_mode = 'solid' # 'solid', 'chase', 'rwb_chase'
color_index = 0
chase_offset = 0
overhead_angle = 0
chase_speed_delay = 0.05
goal_animation_active = False
goal_animation_end_time = 0
goal_animation_center = 0
goal_animation_step = 0
goal_animation_direction = 1
last_chase_update = time.time()
last_frame_time = time.time()

# --- Helper Function for Goal Animation ---
def start_goal_animation(center_led):
    global goal_animation_active, goal_animation_end_time, goal_animation_center
    goal_animation_active = True
    goal_animation_end_time = time.time() + GOAL_ANIMATION_DURATION
    goal_animation_center = center_led
    print(f"Goal animation started!")

# --- Main Loop ---
running = True
TARGET_FPS = 60
FRAME_DURATION = 1.0 / TARGET_FPS

while running:
    frame_start_time = time.time()
    delta_time = frame_start_time - last_frame_time
    last_frame_time = frame_start_time

    # --- Check for Keyboard Input ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and (event.key == pygame.K_q or event.key == pygame.K_ESCAPE)):
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m: # Cycle through base modes
                goal_animation_active = False
                if base_mode == 'solid': base_mode = 'chase'
                elif base_mode == 'chase': base_mode = 'rwb_chase'
                else: base_mode = 'solid'
                print(f"Base Mode: {base_mode}")
            if event.key == pygame.K_c: # Change color for solid/chase modes
                color_index = (color_index + 1) % len(BASE_COLORS)
            if event.key == pygame.K_UP: 
                chase_speed_delay = max(0.0, chase_speed_delay - 0.005)
                print(f"Chase speed delay: {chase_speed_delay:.3f}s")
            if event.key == pygame.K_DOWN: 
                chase_speed_delay += 0.005
                print(f"Chase speed delay: {chase_speed_delay:.3f}s")
            if event.key == pygame.K_1: start_goal_animation(GOAL_1_CENTER_LED)
            if event.key == pygame.K_2: start_goal_animation(GOAL_2_CENTER_LED)

    # --- Update LED States ---
    now = time.time()

    if goal_animation_active:
        if now > goal_animation_end_time:
            goal_animation_active = False
        else:
            goal_animation_step += goal_animation_direction
            max_half = GOAL_ANIMATION_WIDTH // 2
            if goal_animation_step >= max_half or goal_animation_step <= 0:
                goal_animation_direction *= -1
            pixels.fill((0, 0, 0)) # Clear whole strip for goal effect
            start = max(0, goal_animation_center - goal_animation_step)
            end = min(TOTAL_LED_COUNT, goal_animation_center + goal_animation_step + 1)
            for i in range(start, end): pixels[i] = GOAL_ANIMATION_COLOR
    else:
        # --- Update Base Lights (LEDs 0-199) ---
        if base_mode == 'solid':
            for i in range(BASE_COUNT): pixels[i] = BASE_COLORS[color_index]
        elif base_mode == 'chase':
            if now - last_chase_update > chase_speed_delay:
                chase_offset += 1; last_chase_update = now
            for i in range(BASE_COUNT):
                pixels[i] = BASE_COLORS[color_index] if (i + chase_offset) % 10 < 5 else (0, 0, 0)
        elif base_mode == 'rwb_chase':
            if now - last_chase_update > chase_speed_delay:
                chase_offset += 1; last_chase_update = now
            chase_r = (255,0,0); chase_w = (255,255,255); chase_b = (0,0,255)
            for i in range(BASE_COUNT):
                pos = (i + chase_offset) % 15
                if pos < 5: pixels[i] = chase_r
                elif pos < 10: pixels[i] = chase_w
                else: pixels[i] = chase_b
        
        # --- Update Unused Area (LEDs 200-299) ---
        for i in range(UNUSED_START_INDEX, OVERHEAD_START_INDEX):
            pixels[i] = (0, 0, 0)

        # --- Update Overhead Lights (LEDs 300-427) ---
        if base_mode == 'rwb_chase':
            # Pulsing red/white/blue "breathing" effect over 6 seconds
            cycle_duration = 6.0
            cycle_time = now % cycle_duration
            
            color = (0, 0, 0)
            if cycle_time < 2.0:
                # Red pulse for the first 2 seconds
                progress = cycle_time / 2.0
                brightness = math.sin(progress * math.pi)
                color = (int(255 * brightness), 0, 0)
            elif cycle_time < 4.0:
                # White pulse for the next 2 seconds
                progress = (cycle_time - 2.0) / 2.0
                brightness = math.sin(progress * math.pi)
                color = (int(255 * brightness), int(255 * brightness), int(255 * brightness))
            else:
                # Blue pulse for the final 2 seconds
                progress = (cycle_time - 4.0) / 2.0
                brightness = math.sin(progress * math.pi)
                color = (0, 0, int(255 * brightness))

            for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT):
                pixels[i] = color
        else:
            # Rotating arc with color matching the base
            overhead_angle = (overhead_angle + OVERHEAD_ROTATION_SPEED * delta_time) % 360
            arc_color = BASE_COLORS[color_index]
            arc_width = 120
            for i in range(OVERHEAD_COUNT):
                ring_index = -1
                for r_idx in range(len(RING_CONFIG)):
                    if i < RING_CUMULATIVE[r_idx+1]:
                        ring_index = r_idx; break
                led_num_on_ring = i - RING_CUMULATIVE[ring_index]
                angle_per_led = 360.0 / RING_CONFIG[ring_index]
                led_angle = led_num_on_ring * angle_per_led
                diff = (led_angle - overhead_angle + 180) % 360 - 180
                if -arc_width / 2 <= diff <= arc_width / 2:
                    pixels[OVERHEAD_START_INDEX + i] = arc_color
                else:
                    pixels[OVERHEAD_START_INDEX + i] = (0, 0, 0)

    # --- Render All Changes to the Strip ---
    pixels.show()
    
    # --- Frame Rate Limiter ---
    elapsed_time = time.time() - frame_start_time
    sleep_time = FRAME_DURATION - elapsed_time
    if sleep_time > 0:
        time.sleep(sleep_time)

# --- Cleanup ---
print("Turning off all LEDs and exiting.")
if pixels: pixels.fill((0, 0, 0)); pixels.show()
pygame.quit()
sys.exit()

