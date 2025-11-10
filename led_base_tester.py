# NeoPixel LED Strip Test Script
# By Gemini
#
# Description:
# A simple script to test a newly wired NeoPixel LED strip on a Raspberry Pi.
# This allows for testing colors, animations, and speed independently from the
# main scoreboard application.
#
# Assumes the new strip is connected to GPIO 12.
import time
import board
import neopixel
import pygame
import sys
# --- Configuration for the NEW LED strip ---
LED_PIN = board.D12 # GPIO 12
LED_COUNT = 200 # The number of LEDs in your new strip
LED_BRIGHTNESS = 0.5 # Start at 50% brightness to be safe
# --- Goal Animation Configuration ---
GOAL_1_CENTER_LED = 46
GOAL_2_CENTER_LED = 146
GOAL_ANIMATION_DURATION = 3 # seconds
GOAL_ANIMATION_WIDTH = 40 # total width (20 LEDs on each side of center)
GOAL_ANIMATION_COLOR = (255, 0, 0) # Red
# --- Test Colors ---
COLORS = [
(255, 0, 0), # Red
(0, 255, 0), # Green
(0, 0, 255), # Blue
(255, 255, 255),# White
(255, 255, 0), # Yellow
(0, 255, 255), # Cyan
(255, 0, 255), # Magenta
]
# --- Initialize Pygame for Keyboard Input ---
pygame.init()
screen = pygame.display.set_mode((200, 200))
pygame.display.set_caption("LED Tester")
# --- Initialize NeoPixel Strip ---

try:
pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=LED_BRIGHTNESS,
auto_write=False)
print("NeoPixel strip initialized successfully on GPIO 12.")
print("Press 'M' to toggle mode, 'C' to change color, Up/Down to change
speed.")
print("Press '1' or '2' to trigger goal animations.")
print("Press 'Q' or ESC to quit.")
except Exception as e:
print(f"ERROR: Could not initialize NeoPixel strip. Please check wiring and
run with 'sudo'.")
print(f"Details: {e}")
pygame.quit()
sys.exit()
# --- Main Program State ---
mode = 'solid' # Can be 'solid' or 'chase'
color_index = 0
chase_offset = 0
chase_speed_delay = 0.02
# --- Goal Animation State ---
goal_animation_active = False
goal_animation_end_time = 0
goal_animation_center = 0
goal_animation_step = 0
goal_animation_direction = 1 # 1 for growing, -1 for shrinking
# --- Main Loop ---
running = True
while running:
# --- Check for Keyboard Input ---
for event in pygame.event.get():
if event.type == pygame.QUIT:
running = False
if event.type == pygame.KEYDOWN:
if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
running = False
# M key: Toggle mode
if event.key == pygame.K_m:
goal_animation_active = False # Stop any goal animation
if mode == 'solid':
mode = 'chase'
print("Mode: Chase")

else:
mode = 'solid'
print("Mode: Solid")
# C key: Cycle color
if event.key == pygame.K_c:
color_index = (color_index + 1) % len(COLORS)
print(f"Color changed.")
# Up/Down Arrows for speed
if event.key == pygame.K_UP:
chase_speed_delay = max(0.0, chase_speed_delay - 0.005)
print(f"Chase speed delay: {chase_speed_delay:.3f}s")
if event.key == pygame.K_DOWN:
chase_speed_delay += 0.005
print(f"Chase speed delay: {chase_speed_delay:.3f}s")
# --- Goal Triggers ---
def start_goal_animation(center_led):
global goal_animation_active, goal_animation_end_time,
goal_animation_center
goal_animation_active = True
goal_animation_end_time = time.time() + GOAL_ANIMATION_DURATION
goal_animation_center = center_led
print(f"Goal animation started at LED {center_led}!")
if event.key == pygame.K_1:
start_goal_animation(GOAL_1_CENTER_LED)
if event.key == pygame.K_2:
start_goal_animation(GOAL_2_CENTER_LED)
# --- Update LED Strip Based on State ---
if goal_animation_active:
# Check if the 3-second timer has expired
if time.time() > goal_animation_end_time:
goal_animation_active = False
mode = 'chase' # Switch to chase mode after animation
print("Goal animation finished. Switching to chase mode.")
continue # Skip the rest of this loop iteration
# Update animation step
goal_animation_step += goal_animation_direction
# Reverse direction at the boundaries

max_half_width = GOAL_ANIMATION_WIDTH // 2
if goal_animation_step >= max_half_width:
goal_animation_direction = -1
elif goal_animation_step <= 0:
goal_animation_direction = 1
# Calculate which LEDs to light up
pixels.fill((0, 0, 0)) # Clear all pixels first
start_led = max(0, goal_animation_center - goal_animation_step)
end_led = min(LED_COUNT, goal_animation_center + goal_animation_step + 1)
for i in range(start_led, end_led):
pixels[i] = GOAL_ANIMATION_COLOR
pixels.show()
time.sleep(0.01) # A short delay to control the expand/contract speed
elif mode == 'solid':
current_color = COLORS[color_index]
pixels.fill(current_color)
pixels.show()
elif mode == 'chase':
current_color = COLORS[color_index]
for i in range(LED_COUNT):
if (i + chase_offset) % 10 < 5:
pixels[i] = current_color
else:
pixels[i] = (0, 0, 0)
pixels.show()
chase_offset += 1
time.sleep(chase_speed_delay)
# --- Cleanup ---
print("Turning off LEDs and exiting.")
pixels.fill((0, 0, 0))
pixels.show()
pygame.quit()
sys.exit()