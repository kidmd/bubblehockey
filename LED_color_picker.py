# Advanced LED Color Picker with File Saving
# By Gemini
#
# Description:
# This script allows you to create and save custom colors for both a physical
# WS212B LED strip and an on-screen display. Each color name stores two
# distinct RGB values. Changes are saved to the file in real-time.
#
# Controls:
#   - UP/DOWN ARROWS: Select the Primary color.
#   - PAGE UP/PAGE DOWN: Select the Secondary color.
#   - TAB: Switch between editing the LED color and the DISPLAY color.
#
#   - R / F: Increase / Decrease RED value.
#   - T / G: Increase / Decrease GREEN value.
#   - Y / H: Increase / Decrease BLUE value.
#
#   - S key: Rename the currently selected Primary color.
#   - A key: Add a new blank color to the list.
#   - DELETE key: Delete the currently selected Primary color.
#   - SPACE key: Cycle between Solid and Chasing animation modes for the base strip.
#   - O key: Cycle overhead light patterns.
#
#   - ESC key: Quit the program.

import pygame
import sys
import os
import math

# --- Attempt to import Raspberry Pi specific libraries ---
IS_RASPBERRY_PI = True
try:
    import board
    import neopixel
except ImportError:
    IS_RASPBERRY_PI = False
    print("WARNING: RPi libraries not found. Running in UI-only mode.")

# --- Configuration ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
COLOR_FILE = "custom_colors.txt"

# --- LED Strip Configuration ---
BASE_LED_COUNT = 201
BLANK_LED_COUNT = 0
OVERHEAD_LED_COUNT = 128
TOTAL_LED_COUNT = BASE_LED_COUNT + BLANK_LED_COUNT + OVERHEAD_LED_COUNT
OVERHEAD_START_INDEX = BASE_LED_COUNT + BLANK_LED_COUNT
LED_BRIGHTNESS = 0.8
if IS_RASPBERRY_PI:
    LED_PIN = board.D21

# --- Colors ---
C_BLACK = (0, 0, 0)
C_WHITE = (255, 255, 255)
C_GRAY = (40, 40, 40)
C_LIGHT_GRAY = (100, 100, 100)
C_HIGHLIGHT_PRI = (255, 215, 0) # Gold for Primary
C_HIGHLIGHT_SEC = (173, 216, 230) # Light Blue for Secondary
C_RED = (200, 50, 50)
C_GREEN = (50, 200, 50)
C_BLUE = (50, 50, 200)

class ColorPicker:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Advanced LED Color Picker")
        self.clock = pygame.time.Clock()
        
        self.font_reg = pygame.font.SysFont('monospace', 20)
        self.font_bold = pygame.font.SysFont('monospace', 22, bold=True)
        self.font_title = pygame.font.SysFont('monospace', 28, bold=True)
        
        self.saved_colors = []
        self.primary_index = 0
        self.secondary_index = 1
        self.current_led_rgb = [0, 0, 0]
        self.current_display_rgb = [0, 0, 0]
        
        self.is_saving = False
        self.input_text = ""
        self.editing_mode = 'LED'
        self.animation_mode = 0 # Base strip animation
        self.overhead_mode = 0 # Overhead strip animation
        self.frame_counter = 0
        self.colors_changed = False

        self.key_hold_timers = {}
        self.key_repeat_timers = {}
        
        self.load_colors()
        if self.saved_colors:
            self.update_current_colors_from_selection()
        
        self.pixels = None
        if IS_RASPBERRY_PI:
            try:
                self.pixels = neopixel.NeoPixel(LED_PIN, TOTAL_LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
                print("NeoPixel strip initialized.")
            except Exception as e:
                print(f"ERROR: Could not initialize NeoPixel strip: {e}")

    def update_current_colors_from_selection(self):
        if self.saved_colors and self.primary_index < len(self.saved_colors):
            _, led_rgb, display_rgb = self.saved_colors[self.primary_index]
            self.current_led_rgb = list(led_rgb)
            self.current_display_rgb = list(display_rgb)

    def load_colors(self):
        if not os.path.exists(COLOR_FILE):
            self.saved_colors = [("Default Red", (255, 0, 0), (200, 0, 0)), ("Black", (0, 0, 0), (0, 0, 0)), ("Default White", (255, 255, 255), (255, 255, 255))]
            self.save_colors()
            return

        self.saved_colors = []
        converted_from_old = False
        try:
            with open(COLOR_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    parts = line.split(',')
                    name = parts[0]
                    if len(parts) == 4:
                        rgb = tuple(int(c) for c in parts[1:])
                        self.saved_colors.append((name, rgb, rgb))
                        converted_from_old = True
                    elif len(parts) == 7:
                        led_rgb = tuple(int(c) for c in parts[1:4])
                        display_rgb = tuple(int(c) for c in parts[4:7])
                        self.saved_colors.append((name, led_rgb, display_rgb))
            if converted_from_old: self.save_colors()
            if len(self.saved_colors) < 2: self.saved_colors.append(("Black", (0,0,0), (0,0,0)))
        except Exception as e:
            print(f"Error loading color file: {e}")
            self.saved_colors = [("Default Red", (255,0,0), (200,0,0)), ("Black", (0,0,0), (0,0,0)), ("White", (255,255,255), (255,255,255))]

    def save_colors(self):
        try:
            with open(COLOR_FILE, 'w') as f:
                for name, led_rgb, display_rgb in self.saved_colors:
                    f.write(f"{name},{led_rgb[0]},{led_rgb[1]},{led_rgb[2]},{display_rgb[0]},{display_rgb[1]},{display_rgb[2]}\n")
        except Exception as e: print(f"Error saving color file: {e}")

    def handle_input(self):
        rgb_key_map = {pygame.K_r: (0, 1), pygame.K_f: (0, -1), pygame.K_t: (1, 1), pygame.K_g: (1, -1), pygame.K_y: (2, 1), pygame.K_h: (2, -1)}
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYUP:
                if event.key in self.key_hold_timers: del self.key_hold_timers[event.key]
                if event.key in self.key_repeat_timers: del self.key_repeat_timers[event.key]
            if event.type == pygame.KEYDOWN:
                if self.is_saving:
                    if event.key == pygame.K_RETURN:
                        if self.input_text: self.saved_colors[self.primary_index] = (self.input_text, tuple(self.current_led_rgb), tuple(self.current_display_rgb)); self.save_colors(); self.is_saving = False; self.input_text = ""
                    elif event.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]
                    elif event.key == pygame.K_ESCAPE: self.is_saving = False; self.input_text = ""
                    else: self.input_text += event.unicode
                else:
                    if event.key == pygame.K_ESCAPE: return False
                    elif event.key == pygame.K_UP:
                        if self.saved_colors: self.primary_index = max(0, self.primary_index - 1); self.update_current_colors_from_selection()
                    elif event.key == pygame.K_DOWN:
                        if self.saved_colors: self.primary_index = min(len(self.saved_colors) - 1, self.primary_index + 1); self.update_current_colors_from_selection()
                    elif event.key == pygame.K_PAGEUP:
                        if self.saved_colors: self.secondary_index = max(0, self.secondary_index - 1)
                    elif event.key == pygame.K_PAGEDOWN:
                        if self.saved_colors: self.secondary_index = min(len(self.saved_colors) - 1, self.secondary_index + 1)
                    elif event.key == pygame.K_TAB: self.editing_mode = 'DISPLAY' if self.editing_mode == 'LED' else 'LED'
                    elif event.key == pygame.K_o: self.overhead_mode = (self.overhead_mode + 1) % 5
                    elif event.key == pygame.K_s:
                        if self.saved_colors: self.input_text = self.saved_colors[self.primary_index][0]; self.is_saving = True
                    elif event.key == pygame.K_a:
                        self.saved_colors.append(("New Color", (0,0,0), (0,0,0))); self.primary_index = len(self.saved_colors) - 1; self.update_current_colors_from_selection(); self.colors_changed = True
                    elif event.key == pygame.K_DELETE:
                        if self.saved_colors and len(self.saved_colors) > 1:
                            self.saved_colors.pop(self.primary_index); self.primary_index = min(self.primary_index, len(self.saved_colors) - 1); self.secondary_index = min(self.secondary_index, len(self.saved_colors) - 1); self.update_current_colors_from_selection(); self.save_colors()
                    elif event.key == pygame.K_SPACE: self.animation_mode = (self.animation_mode + 1) % 2
                    elif event.key in rgb_key_map:
                        rgb_to_edit = self.current_led_rgb if self.editing_mode == 'LED' else self.current_display_rgb
                        index, direction = rgb_key_map[event.key]
                        rgb_to_edit[index] = max(0, min(255, rgb_to_edit[index] + direction))
                        self.colors_changed = True; current_time = pygame.time.get_ticks(); self.key_hold_timers[event.key] = current_time; self.key_repeat_timers[event.key] = current_time
        return True

    def process_key_holds(self):
        if self.is_saving: return
        current_time = pygame.time.get_ticks(); keys = pygame.key.get_pressed(); INITIAL_DELAY, REPEAT_INTERVAL = 400, 30
        rgb_key_map = {pygame.K_r: (0, 2), pygame.K_f: (0, -2), pygame.K_t: (1, 2), pygame.K_g: (1, -2), pygame.K_y: (2, 2), pygame.K_h: (2, -2)}
        rgb_to_edit = self.current_led_rgb if self.editing_mode == 'LED' else self.current_display_rgb
        for key, (index, direction) in rgb_key_map.items():
            if keys[key] and key in self.key_hold_timers:
                if current_time - self.key_hold_timers[key] > INITIAL_DELAY:
                    if current_time - self.key_repeat_timers[key] > REPEAT_INTERVAL:
                        self.key_repeat_timers[key] = current_time; rgb_to_edit[index] = max(0, min(255, rgb_to_edit[index] + direction)); self.colors_changed = True

    def update_leds(self):
        if not self.pixels: return
        pri_led_color = tuple(self.current_led_rgb)
        sec_led_color = self.saved_colors[self.secondary_index][1] if self.saved_colors else C_BLACK

        # --- Base Strip Animation ---
        if self.animation_mode == 0:
            for i in range(BASE_LED_COUNT): self.pixels[i] = pri_led_color
        elif self.animation_mode == 1:
            chase_offset = self.frame_counter // 2
            for i in range(BASE_LED_COUNT):
                self.pixels[i] = pri_led_color if (i + chase_offset) % 10 < 5 else sec_led_color
        
        # --- Blank Strip Section ---
        for i in range(BASE_LED_COUNT, OVERHEAD_START_INDEX):
            self.pixels[i] = C_BLACK

        # --- Overhead Strip Animation ---
        if self.overhead_mode == 0: # Off
             for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT): self.pixels[i] = C_BLACK
        elif self.overhead_mode == 1: # Solid Primary
            for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT): self.pixels[i] = pri_led_color
        elif self.overhead_mode == 2: # Solid Secondary
            for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT): self.pixels[i] = sec_led_color
        elif self.overhead_mode == 3: # Alternating
            cycle_time = FPS # Switch every second
            color_to_show = pri_led_color if (self.frame_counter // cycle_time) % 2 == 0 else sec_led_color
            for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT):
                self.pixels[i] = color_to_show
        elif self.overhead_mode == 4: # Breathing
            pulse_duration = 2 * FPS
            target_color = pri_led_color if (self.frame_counter // pulse_duration) % 2 == 0 else sec_led_color
            progress = self.frame_counter % pulse_duration
            angle = (progress / pulse_duration) * math.pi
            brightness = math.sin(angle)
            breathe_color = tuple(int(c * brightness) for c in target_color)
            for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT): self.pixels[i] = breathe_color
            
        self.pixels.show()

    def draw(self):
        self.screen.fill(C_GRAY)
        list_panel_rect = pygame.Rect(20, 20, 450, SCREEN_HEIGHT - 40); pygame.draw.rect(self.screen, C_BLACK, list_panel_rect, border_radius=10)
        self.screen.blit(self.font_title.render("Saved Colors", True, C_WHITE), (list_panel_rect.x + 20, list_panel_rect.y + 20))
        y_offset = 70
        for i, (name, led_rgb, display_rgb) in enumerate(self.saved_colors):
            is_primary, is_secondary = (i == self.primary_index), (i == self.secondary_index)
            prefix = "[P] " if is_primary else "[S] " if is_secondary else ""
            text_color = C_HIGHLIGHT_PRI if is_primary else C_HIGHLIGHT_SEC if is_secondary else C_WHITE
            if is_primary: pygame.draw.rect(self.screen, C_LIGHT_GRAY, (list_panel_rect.x + 10, y_offset - 5, list_panel_rect.width - 20, 30), border_radius=5)
            self.screen.blit(self.font_bold.render(f"{prefix}{name}", True, text_color), (list_panel_rect.x + 20, y_offset))
            pygame.draw.rect(self.screen, display_rgb, (list_panel_rect.right - 80, y_offset, 20, 20)); pygame.draw.rect(self.screen, led_rgb, (list_panel_rect.right - 50, y_offset, 20, 20))
            y_offset += 35
        self.screen.blit(self.font_reg.render("DSP LED", True, C_WHITE), (list_panel_rect.right - 85, 45))

        rgb_to_edit, editing_label = (self.current_led_rgb, "LED") if self.editing_mode == 'LED' else (self.current_display_rgb, "DISPLAY")
        
        # Previews and Labels
        pygame.draw.rect(self.screen, tuple(self.current_display_rgb), (500, 20, SCREEN_WIDTH - 520, 80), border_radius=10)
        pygame.draw.rect(self.screen, C_HIGHLIGHT_PRI, (500, 20, SCREEN_WIDTH - 520, 80), width=(4 if self.editing_mode == 'DISPLAY' else 0), border_radius=10)
        self.screen.blit(self.font_bold.render("DISPLAY (Primary)", True, C_WHITE), (500, 105))
        pygame.draw.rect(self.screen, tuple(self.current_led_rgb), (500, 140, SCREEN_WIDTH - 520, 50), border_radius=10)
        pygame.draw.rect(self.screen, C_HIGHLIGHT_PRI, (500, 140, SCREEN_WIDTH - 520, 50), width=(4 if self.editing_mode == 'LED' else 0), border_radius=10)
        self.screen.blit(self.font_bold.render("LED (Primary)", True, C_WHITE), (500, 195))
        
        overhead_modes = ["Off", "Solid Primary", "Solid Secondary", "Alt. P/S", "Breathe P/S"]
        overhead_text = f"Overhead: {overhead_modes[self.overhead_mode]} (O)"
        self.screen.blit(self.font_bold.render(overhead_text, True, C_WHITE), (500, 225))
        
        mode_text = f"Base Mode: {'Solid' if self.animation_mode == 0 else 'Chasing'} (SPACE)"
        self.screen.blit(self.font_bold.render(mode_text, True, C_WHITE), (SCREEN_WIDTH - 20 - self.font_bold.size(mode_text)[0], 225))

        edit_mode_text = f"EDITING: {editing_label} (TAB to switch)"
        self.screen.blit(self.font_title.render(edit_mode_text, True, C_HIGHLIGHT_PRI), (500, 260))

        slider_y = 310
        for i, color_name, key_up, key_down in [(0, "RED", 'R', 'F'), (1, "GREEN", 'T', 'G'), (2, "BLUE", 'Y', 'H')]:
            label_text = f"{color_name} ({rgb_to_edit[i]}) - Keys: {key_up}/{key_down}"
            self.screen.blit(self.font_bold.render(label_text, True, C_WHITE), (500, slider_y))
            slider_bg = pygame.Rect(500, slider_y + 40, 255 * 2.5, 30); pygame.draw.rect(self.screen, C_BLACK, slider_bg, border_radius=15)
            slider_fg = pygame.Rect(500, slider_y + 40, rgb_to_edit[i] * 2.5, 30); pygame.draw.rect(self.screen, (C_RED, C_GREEN, C_BLUE)[i], slider_fg, border_radius=15)
            slider_y += 90

        if self.is_saving: self.draw_input_box()
        pygame.display.flip()

    def draw_input_box(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 180)); self.screen.blit(overlay, (0, 0))
        box_rect = pygame.Rect((SCREEN_WIDTH-600)/2, (SCREEN_HEIGHT-200)/2, 600, 200)
        pygame.draw.rect(self.screen, C_BLACK, box_rect, border_radius=15); pygame.draw.rect(self.screen, C_WHITE, box_rect, width=2, border_radius=15)
        self.screen.blit(self.font_bold.render("Enter color name:", True, C_WHITE), (box_rect.x + 20, box_rect.y + 30))
        input_rect = pygame.Rect(box_rect.x + 20, box_rect.y + 80, box_rect.width - 40, 50); pygame.draw.rect(self.screen, C_GRAY, input_rect, border_radius=10)
        self.screen.blit(self.font_title.render(self.input_text, True, C_WHITE), (input_rect.x + 15, input_rect.y + 10))

    def run(self):
        running = True
        while running:
            running = self.handle_input()
            self.process_key_holds()
            self.frame_counter += 1
            if self.colors_changed:
                if self.saved_colors and not self.is_saving:
                    name, _, _ = self.saved_colors[self.primary_index]
                    self.saved_colors[self.primary_index] = (name, tuple(self.current_led_rgb), tuple(self.current_display_rgb))
                    self.save_colors()
                    self.colors_changed = False
            self.update_leds()
            self.draw()
            self.clock.tick(FPS)
        if self.pixels: self.pixels.fill(C_BLACK); self.pixels.show()
        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    picker = ColorPicker()
    picker.run()

