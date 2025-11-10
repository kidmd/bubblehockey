# Raspberry Pi Hockey Scoreboard Controller
# By Gemini
#
# Description:
# This program runs on a Raspberry Pi to control a bubble hockey scoreboard.
# It uses a single, long NeoPixel strip for all lighting effects and loads
# custom color schemes from 'custom_colors.txt'.
#
# GPIO Pin Assignments (BCM Mode):
#   - USA Goal: GPIO 17
#   - USSR Goal: GPIO 27
#   - USA SOG: GPIO 22
#   - USSR SOG: GPIO 23
#   - Faceoff Sensor 1: GPIO 24 (Away)
#   - Faceoff Sensor 2: GPIO 26 (Home)
#   - Faceoff Motor Relay: GPIO 25
#   - Volume Encoder CLK: GPIO 5
#   - Volume Encoder DT: GPIO 6
#   - Volume Encoder SW (Button): GPIO 13
#   - Combined WS2812B LED Strip Data: GPIO 21
#   - RFID Home CS: GPIO 7 (SPI0 CE1)
#   - RFID Away CS: GPIO 8 (SPI0 CE0)

import pygame
import sys
import time
import math
import random
import subprocess
import os
import json

# --- Attempt to import Raspberry Pi specific libraries ---
IS_RASPBERRY_PI = True
try:
    from gpiozero import Button as GpioButton, OutputDevice, RotaryEncoder
    import board
    import neopixel
    # Add the current directory to the path for local libraries
    sys.path.append('.')
    from SimpleMFRC522 import SimpleMFRC522
except ImportError:
    IS_RASPBERRY_PI = False
    SimpleMFRC522 = None
    print("WARNING: Raspberry Pi specific libraries not found. Running in keyboard-only/no-RFID mode.")


# --- GPIO Pin Configuration ---
if IS_RASPBERRY_PI:
    USA_GOAL_PIN = 17
    USSR_GOAL_PIN = 27
    USA_SOG_PIN = 22
    USSR_SOG_PIN = 23
    FACEOFF_PIN_1 = 26 
    FACEOFF_PIN_2 = 24 
    MOTOR_PIN = 25
    VOLUME_CLK_PIN = 5
    VOLUME_DT_PIN = 6
    VOLUME_SW_PIN = 13
    LED_PIN = board.D21
    # SPI pins for RFID readers
    RFID_AWAY_CS_PIN = 8 # Corresponds to device=0
    RFID_HOME_CS_PIN = 7 # Corresponds to device=1


# --- LED Strip Configuration ---
BASE_COUNT = 201
UNUSED_COUNT = 0
OVERHEAD_COUNT = 128
TOTAL_LED_COUNT = BASE_COUNT + UNUSED_COUNT + OVERHEAD_COUNT
LED_BRIGHTNESS = 0.5
OVERHEAD_START_INDEX = BASE_COUNT + UNUSED_COUNT
RING_CONFIG = [8, 16, 24, 35, 45]
RING_CUMULATIVE = [sum(RING_CONFIG[:i]) for i in range(len(RING_CONFIG) + 1)]

# --- Game Configuration ---
BASE_WIDTH = 1920
BASE_HEIGHT = 1080
FPS = 60
MOTOR_RUN_TIME = 0.5
COLOR_FILE = "custom_colors.txt"
PLAYER_FILE = "players.json"

# Colors & Customization
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_YELLOW = (220, 220, 0)
COLOR_GRAY = (100, 100, 100)
COLOR_RED = (200, 0, 0)
COLOR_BLUE = (0, 0, 255)

PLAYER_NAMES = [
    "USSR", "USA", "Grandpa", "Oma", "Kristin", "Allie", "Mike", "Joe",
    "Megan", "Bobby", "Lauren", "Sammi", "Maria", "Becca", "Patrick",
    "Josie", "Andrew", "Emma", "Daniel", "Lizzie", "Twin A", "Twin B",
    "Tom", "Rachel", "Matt", "Ryan"
]
VISITOR_NAMES = [name for name in PLAYER_NAMES if name != "USA"]
HOME_NAMES = [name for name in PLAYER_NAMES if name != "USSR"]


# --- UI Classes ---
class Button:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = COLOR_GRAY
        self.text_color = COLOR_WHITE
        self.hover_color = (150, 150, 150)

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=15)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

class Dropdown:
    def __init__(self, x, y, width, height, options, font, color=COLOR_GRAY):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.font = font
        self.selected_index = 0
        self.color = color
        self.option_rects = []
        self.option_surfs = [self.font.render(option, True, COLOR_WHITE) for option in options]

    def get_selected(self):
        return self.options[self.selected_index]

    def draw_main_box(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=10)
        selected_surf = self.option_surfs[self.selected_index]
        screen.blit(selected_surf, (self.rect.x + 15, self.rect.y + (self.rect.height - selected_surf.get_height()) // 2))

    def draw_expanded_list(self, screen, boundary_y):
        self.option_rects = []
        available_height = boundary_y - (self.rect.y + self.rect.height) - 20
        max_per_col = max(1, available_height // self.rect.height)
        if len(self.options) == 0: return
        num_cols = (len(self.options) + max_per_col - 1) // max_per_col
        draw_left = self.rect.centerx > screen.get_width() / 2
        item_index = 0
        for col in range(num_cols):
            col_x = self.rect.x - (col * self.rect.width) if draw_left else self.rect.x + (col * self.rect.width)
            for row in range(max_per_col):
                if item_index >= len(self.options): break
                option_surf = self.option_surfs[item_index]
                y_pos = self.rect.y + (row + 1) * self.rect.height
                option_rect = pygame.Rect(col_x, y_pos, self.rect.width, self.rect.height)
                if option_rect.right > screen.get_width(): option_rect.right = screen.get_width()
                if option_rect.left < 0: option_rect.left = 0
                self.option_rects.append(option_rect)
                pygame.draw.rect(screen, self.color, option_rect, border_radius=10)
                screen.blit(option_surf, (option_rect.x + 15, option_rect.y + (option_rect.height - option_surf.get_height()) // 2))
                item_index += 1


# --- Animation Classes ---
class Particle:
    def __init__(self, burst_x, burst_y, color):
        self.burst_x, self.burst_y, self.color = burst_x, burst_y, color
        self.x, self.y, self.z = 0, 0, 0
        angle1, angle2 = random.uniform(0, 2 * math.pi), random.uniform(0, 2 * math.pi)
        speed = random.uniform(3.0, 3.2)
        self.vx = speed * math.sin(angle1) * math.cos(angle2)
        self.vy = speed * math.sin(angle1) * math.sin(angle2)
        self.vz = speed * math.cos(angle1)
        self.lifetime = random.randint(60, 90)
        self.gravity = 0.025
        self.perspective = 300

    def update(self):
        self.vy += self.gravity; self.x += self.vx; self.y += self.vy; self.z += self.vz; self.lifetime -= 1

    def draw(self, screen):
        if self.lifetime > 0:
            scale = self.perspective / (self.perspective + self.z)
            projected_x = self.x * scale + self.burst_x
            projected_y = self.y * scale + self.burst_y
            size = 5
            if self.lifetime < 20: size = int(size * (self.lifetime / 20))
            if size > 0: pygame.draw.circle(screen, self.color, (int(projected_x), int(projected_y)), size)


# Game State Class
class GameState:
    def __init__(self):
        self.volume = 0.5
        self.game_mode = 'SETUP'
        self.player1_name = "USSR"
        self.player2_name = "USA"
        self.player1_primary_color = None
        self.player1_secondary_color = None
        self.player2_primary_color = None
        self.player2_secondary_color = None
        self.player1_ready = False
        self.player2_ready = False
        self.show_rfid_popup_for_player = None
        self.rfid_save_message = ""
        self.rfid_save_message_end_time = 0
        self.rfid_save_message_player = None
        self.rfid_load_message = ""
        self.rfid_load_message_end_time = 0
        self.rfid_load_message_player = None
        self.rfid_welcome_message = ""
        self.rfid_welcome_message_end_time = 0
        self.rfid_welcome_message_player = None
        self.rfid_welcome_message_color = COLOR_WHITE
        self.rfid_away_cooldown_end_time = 0
        self.rfid_home_cooldown_end_time = 0
        self.rfid_scan_animation_active = False
        self.rfid_scan_animation_player = None
        self.rfid_scan_animation_start_time = 0
        self.rfid_scan_animation_end_time = 0
        self.rfid_scan_animation_pri_color = (0,0,0)
        self.rfid_scan_animation_sec_color = (0,0,0)
        self.reset()

    def reset(self):
        pygame.mixer.stop()
        self.usa_score, self.ussr_score, self.usa_sog, self.ussr_sog = 0, 0, 0, 0
        self.period = 1
        self.game_clock = 20 * 60 * 1000
        self.game_active, self.game_over = False, False
        self.time_multiplier = 10.0
        self.goal_celebration_team = None
        self.intermission_active, self.overtime_active = False, False
        self.intermission_timer, self.goal_celebration_timer = 0, 0
        self.is_muted = False
        self.volume_before_mute = self.volume
        self.recent_sog_timer = 0
        self.goal_animation_active = False
        self.goal_animation_timer = 0
        self.goal_animation_frame_counter = 0
        self.goal_animation_color = (0,0,0)
        self.goal_animation_color_sec = (0,0,0)
        self.idle_animation_step = 0
        self.particles = []
        self.game_end_celebration_active = False
        self.winner_name = ""
        self.motor_active = False
        self.motor_stop_time = 0
        self.goal_expand_step = 0
        self.goal_expand_direction = 1
        self.goal_expand_center = 0
        self.player1_ready, self.player2_ready = False, False
        self.usa_special_celebration = False
        self.usa_special_colors = None
        self.ussr_special_celebration = False
        self.ussr_special_colors = None
        self.game_lights_set = False # Flag to prevent constant LED updates

    def update_clock(self, dt):
        if self.game_active and self.game_clock > 0:
            self.game_clock -= dt * self.time_multiplier
            if self.game_clock < 0: self.game_clock = 0

# Main Scoreboard Class
class Scoreboard:
    def __init__(self):
        pygame.init()
        display_info = pygame.display.Info()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = display_info.current_w, display_info.current_h
        self.scale_factor = self.SCREEN_HEIGHT / BASE_HEIGHT
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.game_state = GameState()
        self.custom_colors = []
        self.players = {}
        self.load_custom_colors()
        self.load_player_data()
        self.setup_fonts()
        self.setup_logo = self.load_setup_logo()
        self.video_process, self.video_interrupt_requested = None, False
        self.volume_display_timer = 0
        self.pixels = None
        
        # Custom Pygame events for GPIO
        self.P1_FACEOFF_EVENT = pygame.USEREVENT + 1
        self.P2_FACEOFF_EVENT = pygame.USEREVENT + 2
        
        self.reader_home, self.reader_away = None, None
        if IS_RASPBERRY_PI and SimpleMFRC522:
            try:
                # NOTE: With LED updates paused during gameplay, we can safely increase
                # the SPI speed back to 1MHz for faster, smoother reads.
                self.reader_away = SimpleMFRC522(bus=0, device=0, spd=1000000) # CE0 is device 0 (GPIO 8)
                self.reader_home = SimpleMFRC522(bus=0, device=1, spd=1000000) # CE1 is device 1 (GPIO 7)
                print("RFID readers initialized.")
            except Exception as e:
                print(f"Could not initialize RFID readers: {e}")

        if IS_RASPBERRY_PI:
            try:
                self.pixels = neopixel.NeoPixel(LED_PIN, TOTAL_LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
                print("Unified LED Strip initialized.")
            except Exception as e:
                print(f"Could not initialize LED Strip: {e}"); self.pixels = None
        self.all_sounds = []
        self.load_sounds()
        self.motor, self.volume_encoder, self.volume_button = None, None, None
        self.setup_gpio()
        self.set_master_volume(self.game_state.volume)
        self._set_system_volume('unmute')
        self.game_state.is_muted = False
        self.clear_leds()

    def load_player_data(self):
        if os.path.exists(PLAYER_FILE):
            try:
                with open(PLAYER_FILE, 'r') as f:
                    self.players = json.load(f)
                    print("Player data loaded.")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading player file: {e}")
                self.players = {}
        else:
            self.players = {}
    
    def save_player_data(self):
        try:
            with open(PLAYER_FILE, 'w') as f:
                json.dump(self.players, f, indent=2)
                print("Player data saved.")
        except IOError as e:
            print(f"Error saving player data: {e}")

    def load_custom_colors(self):
        if not os.path.exists(COLOR_FILE):
            default_colors = [("Default Red",(255,0,0),(200,0,0)), ("Black",(0,0,0),(0,0,0)), ("Default White",(255,255,255),(255,255,255))]
            try:
                with open(COLOR_FILE, 'w') as f:
                    for name, led_rgb, display_rgb in default_colors:
                        f.write(f"{name},{led_rgb[0]},{led_rgb[1]},{led_rgb[2]},{display_rgb[0]},{display_rgb[1]},{display_rgb[2]}\n")
            except Exception as e: print(f"Could not create default color file: {e}")
        self.custom_colors = []
        try:
            with open(COLOR_FILE, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    parts = line.split(',')
                    if len(parts) == 7:
                        name, led_rgb, display_rgb = parts[0], tuple(int(c) for c in parts[1:4]), tuple(int(c) for c in parts[4:7])
                        self.custom_colors.append({'name': name, 'led': led_rgb, 'display': display_rgb})
        except Exception as e: print(f"Error loading color file: {e}")
        if not self.custom_colors: self.custom_colors.append({'name': 'Default', 'led': (255,255,255), 'display': (255,255,255)})

    def setup_fonts(self):
        self.large_font = pygame.font.SysFont('monospace', int(324 * self.scale_factor), bold=True)
        self.medium_font = pygame.font.SysFont('monospace', int(162 * self.scale_factor), bold=True)
        self.small_font = pygame.font.SysFont('monospace', int(60 * self.scale_factor), bold=True)
        self.sudden_death_font = pygame.font.SysFont('monospace', int(50 * self.scale_factor), bold=True)
        self.tiny_font = pygame.font.SysFont('monospace', int(54 * self.scale_factor), bold=True)
        self.goal_font = pygame.font.SysFont('monospace', int(220 * self.scale_factor), bold=True)
        self.setup_header_font = pygame.font.SysFont('monospace', int(100 * self.scale_factor), bold=True)
        self.setup_label_font = pygame.font.SysFont('monospace', int(60 * self.scale_factor), bold=True)
        self.setup_dropdown_font = pygame.font.SysFont('monospace', int(40 * self.scale_factor), bold=True)
        self.setup_button_font = pygame.font.SysFont('monospace', int(60 * self.scale_factor), bold=True)

    def load_setup_logo(self):
        try:
            logo = pygame.image.load("lake_placid_logo.png").convert_alpha()
            logo_height = int(self.SCREEN_HEIGHT * 0.8)
            logo_width = int(logo.get_width() * (logo_height / logo.get_height()))
            logo = pygame.transform.smoothscale(logo, (logo_width, logo_height)); logo.set_alpha(128)
            return logo
        except pygame.error: print("WARNING: Could not load 'lake_placid_logo.png'."); return None

    def play_video_hardware(self, video_path):
        if not IS_RASPBERRY_PI: self.stop_video(); return
        try:
            self.video_process = subprocess.Popen(['cvlc', '--fullscreen', '--no-video-title-show', '--play-and-exit', video_path])
            self.game_state.game_mode = 'VIDEO'; pygame.mixer.stop()
        except (FileNotFoundError, Exception) as e: print(f"Error launching video: {e}"); self.stop_video()

    def stop_video(self):
        if self.video_process:
            if self.video_process.poll() is None: self.video_process.terminate(); self.video_process.wait()
            self.video_process = None
        self.game_state.game_mode = 'GAME'
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT), pygame.FULLSCREEN)
        self.draw_game_screen(); pygame.display.flip(); pygame.event.clear()

    def _set_system_volume(self, value):
        if not IS_RASPBERRY_PI: return
        try: subprocess.run(['amixer', 'set', 'Master', str(value)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError) as e: print(f"Could not set system volume: {e}")

    def set_master_volume(self, new_volume):
        self.game_state.volume = round(max(0.0, min(1.0, new_volume)), 1)
        if new_volume > 0: self.game_state.is_muted = False
        adjusted_volume = self.game_state.volume ** 0.5
        for sound in self.all_sounds:
            if sound: sound.set_volume(adjusted_volume * (0.5 if sound == self.goal_horn_sound else 1.0))
        self._set_system_volume(f"{int(adjusted_volume * 100)}%"); self.volume_display_timer = 3 * FPS
    
    def increase_volume(self): self.set_master_volume(self.game_state.volume + 0.1)
    def decrease_volume(self): self.set_master_volume(self.game_state.volume - 0.1)
    def toggle_mute(self):
        self.game_state.is_muted = not self.game_state.is_muted
        self._set_system_volume('mute' if self.game_state.is_muted else 'unmute'); self.volume_display_timer = 3 * FPS
    def handle_volume_button_press(self):
        if self.game_state.game_over: self.game_state.game_mode = 'SETUP'; self.game_state.reset(); self.set_master_volume(self.game_state.volume)
        else: self.toggle_mute()

    def clear_leds(self):
        if self.pixels: self.pixels.brightness = LED_BRIGHTNESS; self.pixels.fill((0,0,0)); self.pixels.show(); self.game_state.goal_animation_active = False

    def update_goal_animation(self):
        if not self.pixels or not self.game_state.goal_animation_active: return
        self.game_state.goal_animation_frame_counter += 1
        current_frame = self.game_state.goal_animation_frame_counter
        if self.game_state.goal_animation_timer > 0: self.game_state.goal_animation_timer -= 1
        
        if current_frame < 3 * FPS: # Stage 1: Expanding Red Line
            self.game_state.goal_expand_step += self.game_state.goal_expand_direction * 2
            max_half_width = 15
            if self.game_state.goal_expand_step >= max_half_width or self.game_state.goal_expand_step <= 0:
                self.game_state.goal_expand_direction *= -1
            for i in range(BASE_COUNT): self.pixels[i] = (0, 0, 0)
            start_led = max(0, self.game_state.goal_expand_center - self.game_state.goal_expand_step)
            end_led = min(BASE_COUNT, self.game_state.goal_expand_center + self.game_state.goal_expand_step + 1)
            for i in range(start_led, end_led): self.pixels[i] = (255, 0, 0)
        else: # Stage 2: Chasing Pattern
            chase_offset = int(current_frame * 0.67)
            if self.game_state.usa_special_celebration and self.game_state.usa_special_colors:
                red, white, blue = self.game_state.usa_special_colors
                for i in range(BASE_COUNT):
                    pattern_pos = (i + chase_offset) % 15
                    if pattern_pos < 5:
                        self.pixels[i] = red
                    elif pattern_pos < 10:
                        self.pixels[i] = white
                    else:
                        self.pixels[i] = blue
            elif self.game_state.ussr_special_celebration and self.game_state.ussr_special_colors:
                red, white = self.game_state.ussr_special_colors
                for i in range(BASE_COUNT):
                    self.pixels[i] = red if (i + chase_offset) % 10 < 5 else white
            else:
                secondary_color = self.game_state.goal_animation_color_sec if self.game_state.goal_animation_color_sec else (0,0,0)
                for i in range(BASE_COUNT):
                    self.pixels[i] = self.game_state.goal_animation_color if (i + chase_offset) % 10 < 5 else secondary_color
        
        for i in range(BASE_COUNT, OVERHEAD_START_INDEX): self.pixels[i] = (0, 0, 0)
        
        cycle_position = (current_frame % (FPS // 2)) / (FPS // 2)
        for i in range(OVERHEAD_COUNT):
            ring_index = -1;
            for r_idx in range(len(RING_CONFIG)):
                if i < RING_CUMULATIVE[r_idx+1]: ring_index = r_idx; break
            num_leds_in_ring, arc_length = RING_CONFIG[ring_index], RING_CONFIG[ring_index] // 3
            start_of_arc_offset, led_num_on_ring = int(cycle_position*num_leds_in_ring), i-RING_CUMULATIVE[ring_index]
            is_in_arc = any((start_of_arc_offset + arc_pos) % num_leds_in_ring == led_num_on_ring for arc_pos in range(arc_length))
            self.pixels[OVERHEAD_START_INDEX + i] = self.game_state.goal_animation_color if is_in_arc else (0,0,0)
        self.pixels.show()

    def update_rfid_scan_animation(self):
        if not self.pixels or not self.game_state.rfid_scan_animation_active:
            return

        current_time = pygame.time.get_ticks()
        if current_time > self.game_state.rfid_scan_animation_end_time:
            self.game_state.rfid_scan_animation_active = False
            return

        elapsed_time = current_time - self.game_state.rfid_scan_animation_start_time
        
        is_away_player = self.game_state.rfid_scan_animation_player == 1
        origin = 49 if is_away_player else 150
        
        if is_away_player:
            for i in range(100, BASE_COUNT): self.pixels[i] = (0,0,0)
        else:
            for i in range(100): self.pixels[i] = (0,0,0)
        
        max_expand_dist = 50.0
        current_expand_dist = 0.0

        if elapsed_time <= 500:
            progress = elapsed_time / 500.0
            eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
            current_expand_dist = max_expand_dist * eased_progress
        elif elapsed_time <= 2500:
            current_expand_dist = max_expand_dist
        else:
            progress = (elapsed_time - 2500) / 500.0
            eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
            current_expand_dist = max_expand_dist * (1.0 - eased_progress)

        pri_color = self.game_state.rfid_scan_animation_pri_color
        sec_color = self.game_state.rfid_scan_animation_sec_color

        player_start_led = 0 if is_away_player else 100
        player_end_led = 100 if is_away_player else BASE_COUNT

        for i in range(player_start_led, player_end_led):
            dist = abs(i - origin)
            
            # Determine the base color
            pattern_index = (int(dist) // 5) % 2
            base_color = pri_color if pattern_index == 0 else sec_color

            # Calculate brightness (anti-aliasing)
            brightness = 0.0
            if dist < current_expand_dist - 1:
                brightness = 1.0 # Fully lit
            elif dist < current_expand_dist:
                brightness = current_expand_dist - dist # Fading edge
            
            # Apply brightness and set color
            final_color = tuple(int(c * brightness) for c in base_color)
            self.pixels[i] = final_color

        self.pixels.show()


    def idle_effect(self):
        if not self.pixels or self.game_state.goal_animation_active or self.game_state.game_active or self.game_state.rfid_scan_animation_active: return
        brightness = 0.75 + (math.sin(self.game_state.idle_animation_step * (2 * math.pi / FPS)) * 0.25)
        color_val = int(80 * brightness)
        for i in range(TOTAL_LED_COUNT): self.pixels[i] = (0,0,0)
        for i in range(RING_CONFIG[0]): self.pixels[OVERHEAD_START_INDEX + i] = (color_val, color_val, color_val)
        self.pixels.show(); self.game_state.idle_animation_step = (self.game_state.idle_animation_step + 1) % FPS
        
    def game_active_effect(self):
        if not self.pixels or self.game_state.game_lights_set:
            return
        for i in range(BASE_COUNT): self.pixels[i] = (5, 5, 5)
        for i in range(BASE_COUNT, OVERHEAD_START_INDEX): self.pixels[i] = (0, 0, 0)
        for i in range(OVERHEAD_START_INDEX, TOTAL_LED_COUNT): self.pixels[i] = (191, 191, 191)
        self.pixels.show()
        self.game_state.game_lights_set = True

    def load_sounds(self):
        if not IS_RASPBERRY_PI: self.goal_horn_sound,self.shot_sound,self.faceoff_sound,self.buzzer_sound,self.rfid_sound = None,None,None,None,None; return
        try: self.goal_horn_sound = pygame.mixer.Sound("goal_horn.wav"); self.all_sounds.append(self.goal_horn_sound)
        except pygame.error as e: self.goal_horn_sound=None; print(f"ERROR: {e}")
        try: self.shot_sound = pygame.mixer.Sound("shot.wav"); self.all_sounds.append(self.shot_sound)
        except pygame.error as e: self.shot_sound=None; print(f"ERROR: {e}")
        try: self.faceoff_sound = pygame.mixer.Sound("faceoff.wav"); self.all_sounds.append(self.faceoff_sound)
        except pygame.error as e: self.faceoff_sound=None; print(f"ERROR: {e}")
        try: self.buzzer_sound = pygame.mixer.Sound("buzzer.wav"); self.all_sounds.append(self.buzzer_sound)
        except pygame.error as e: self.buzzer_sound=None; print(f"ERROR: {e}")
        try: self.rfid_sound = pygame.mixer.Sound("magicband.wav"); self.all_sounds.append(self.rfid_sound)
        except pygame.error as e: self.rfid_sound=None; print(f"ERROR: {e}")
    
    def post_player1_faceoff_event(self):
        pygame.event.post(pygame.event.Event(self.P1_FACEOFF_EVENT))

    def post_player2_faceoff_event(self):
        pygame.event.post(pygame.event.Event(self.P2_FACEOFF_EVENT))

    def setup_gpio(self):
        if not IS_RASPBERRY_PI: return
        try:
            self.usa_goal_button = GpioButton(USA_GOAL_PIN, pull_up=True, bounce_time=0.05); self.usa_goal_button.when_pressed = self.handle_usa_goal
            self.ussr_goal_button = GpioButton(USSR_GOAL_PIN, pull_up=True, bounce_time=0.05); self.ussr_goal_button.when_pressed = self.handle_ussr_goal
            self.usa_sog_button = GpioButton(USA_SOG_PIN, pull_up=True, bounce_time=0.05); self.usa_sog_button.when_pressed = self.handle_usa_sog
            self.ussr_sog_button = GpioButton(USSR_SOG_PIN, pull_up=True, bounce_time=0.05); self.ussr_sog_button.when_pressed = self.handle_ussr_sog
            self.faceoff_button_1 = GpioButton(FACEOFF_PIN_1, pull_up=True, bounce_time=0.05); self.faceoff_button_1.when_pressed = self.post_player1_faceoff_event
            self.faceoff_button_2 = GpioButton(FACEOFF_PIN_2, pull_up=True, bounce_time=0.05); self.faceoff_button_2.when_pressed = self.post_player2_faceoff_event
            self.motor = OutputDevice(MOTOR_PIN, initial_value=False)
            self.volume_encoder = RotaryEncoder(VOLUME_CLK_PIN, VOLUME_DT_PIN, bounce_time=0.1); self.volume_encoder.when_rotated_clockwise, self.volume_encoder.when_rotated_counter_clockwise = self.increase_volume, self.decrease_volume
            self.volume_button = GpioButton(VOLUME_SW_PIN, pull_up=True, bounce_time=0.1); self.volume_button.when_pressed = self.handle_volume_button_press
            print("GPIO pins initialized.")
        except Exception as e: print(f"Could not initialize GPIO: {e}"); print("Running in keyboard-only mode.")

    def create_firework_burst(self, color):
        burst_x, burst_y = random.randint(200, self.SCREEN_WIDTH - 200), random.randint(100, self.SCREEN_HEIGHT - 200)
        for _ in range(50): self.game_state.particles.append(Particle(burst_x, burst_y, color))
    
    def handle_usa_goal(self):
        if not self.game_state.game_over and not self.game_state.goal_celebration_team:
            self.game_state.usa_score += 1;
            if self.game_state.recent_sog_timer <= 0: self.game_state.usa_sog += 1
            self.game_state.goal_expand_center, self.game_state.goal_expand_step, self.game_state.goal_expand_direction, self.game_state.goal_animation_frame_counter = 46, 0, 1, 0
            
            # Reset other team's special celebration to prevent state bleed
            self.game_state.ussr_special_celebration = False
            self.game_state.ussr_special_colors = None

            if self.game_state.player2_name == "USA" and self.game_state.player2_primary_color and self.game_state.player2_primary_color.get('name') == "Blue" and self.game_state.player2_secondary_color is None:
                self.game_state.usa_special_celebration = True
                red = next((c['led'] for c in self.custom_colors if c['name'] == 'Default Red'), (200, 0, 0))
                white = next((c['led'] for c in self.custom_colors if c['name'] == 'Default White'), (255, 255, 255))
                blue = next((c['led'] for c in self.custom_colors if c['name'] == 'Blue'), (0, 0, 200))
                self.game_state.usa_special_colors = [red, white, blue]
            else:
                self.game_state.usa_special_celebration = False
                self.game_state.usa_special_colors = None

            if self.game_state.overtime_active: self.trigger_game_end("player2")
            else:
                if self.pixels: self.pixels.brightness = 1.0
                self.game_state.goal_animation_active, self.game_state.goal_animation_timer = True, 5 * FPS
                self.game_state.goal_animation_color = self.game_state.player2_primary_color['led']
                self.game_state.goal_animation_color_sec = self.game_state.player2_secondary_color['led'] if self.game_state.player2_secondary_color else COLOR_BLACK
                if self.goal_horn_sound: self.goal_horn_sound.play()
                self.game_state.game_active, self.game_state.goal_celebration_team = False, self.game_state.player2_name

    def handle_ussr_goal(self):
        if not self.game_state.game_over and not self.game_state.goal_celebration_team:
            self.game_state.ussr_score += 1
            if self.game_state.recent_sog_timer <= 0: self.game_state.ussr_sog += 1
            self.game_state.goal_expand_center, self.game_state.goal_expand_step, self.game_state.goal_expand_direction, self.game_state.goal_animation_frame_counter = 146, 0, 1, 0
            if self.game_state.overtime_active: self.trigger_game_end("player1")
            else:
                if self.pixels: self.pixels.brightness = 1.0
                self.game_state.goal_animation_active, self.game_state.goal_animation_timer = True, 5 * FPS
                
                # Reset other team's special celebration to prevent state bleed
                self.game_state.usa_special_celebration = False
                self.game_state.usa_special_colors = None

                # Special USSR default celebration
                if self.game_state.player1_name == "USSR" and self.game_state.player1_primary_color and self.game_state.player1_primary_color.get('name') == "Default Red" and self.game_state.player1_secondary_color is None:
                    self.game_state.ussr_special_celebration = True
                    red = next((c['led'] for c in self.custom_colors if c['name'] == 'Default Red'), (200, 0, 0))
                    white = next((c['led'] for c in self.custom_colors if c['name'] == 'Default White'), (255, 255, 255))
                    self.game_state.ussr_special_colors = [red, white]
                else: # Default for other visitor teams or custom USSR
                    self.game_state.ussr_special_celebration = False
                    self.game_state.ussr_special_colors = None
                    self.game_state.goal_animation_color = self.game_state.player1_primary_color['led']
                    self.game_state.goal_animation_color_sec = self.game_state.player1_secondary_color['led'] if self.game_state.player1_secondary_color else COLOR_BLACK
                
                if self.goal_horn_sound: self.goal_horn_sound.play()
                self.game_state.game_active, self.game_state.goal_celebration_team = False, self.game_state.player1_name

    def handle_usa_sog(self):
        if not self.game_state.game_over and not self.game_state.goal_celebration_team:
            if self.shot_sound: self.shot_sound.play()
            self.game_state.usa_sog += 1; self.game_state.recent_sog_timer = 60
    def handle_ussr_sog(self):
        if not self.game_state.game_over and not self.game_state.goal_celebration_team:
            if self.shot_sound: self.shot_sound.play()
            self.game_state.ussr_sog += 1; self.game_state.recent_sog_timer = 60
    def _start_faceoff_sequence(self):
        if not self.game_state.game_over and not self.game_state.motor_active:
            self.clear_leds()
            if self.faceoff_sound: self.faceoff_sound.play()
            if self.motor: self.motor.on(); self.game_state.motor_active = True; self.game_state.motor_stop_time = pygame.time.get_ticks() + (MOTOR_RUN_TIME * 1000)
            if not self.game_state.game_active: self.game_state.game_active = True
            self.game_state.goal_celebration_team = None
            self.game_state.game_lights_set = False
    
    def handle_player1_faceoff(self):
        """Handles all inputs for player 1's faceoff button (GPIO or Keyboard 'F')."""
        if self.game_state.game_mode == 'SETUP':
            self.game_state.player1_ready = not self.game_state.player1_ready
        elif self.game_state.game_mode == 'VIDEO':
            self.video_interrupt_requested = True
        else: # 'GAME' mode
            self._start_faceoff_sequence()

    def handle_player2_faceoff(self):
        """Handles all inputs for player 2's faceoff button (GPIO or Keyboard 'G')."""
        if self.game_state.game_mode == 'SETUP':
            self.game_state.player2_ready = not self.game_state.player2_ready
        elif self.game_state.game_mode == 'VIDEO':
            self.video_interrupt_requested = True
        else: # 'GAME' mode
            self._start_faceoff_sequence()

    def update_motor(self):
        if self.game_state.motor_active and self.motor and pygame.time.get_ticks() >= self.game_state.motor_stop_time:
            self.motor.off(); self.game_state.motor_active = False; self.game_state.motor_stop_time = 0
    def trigger_game_end(self, winner_id):
        self.game_state.game_over, self.game_state.game_end_celebration_active, self.game_state.goal_celebration_timer = True, True, 5 * FPS
        winner_color_info = self.game_state.player1_primary_color if winner_id == "player1" else self.game_state.player2_primary_color
        self.game_state.winner_name = self.game_state.player1_name if winner_id == "player1" else self.game_state.player2_name
        if self.goal_horn_sound: self.goal_horn_sound.play()
        if self.faceoff_sound: self.faceoff_sound.play()
        if self.pixels:
            self.pixels.brightness = 1.0; self.game_state.goal_animation_active = True; self.game_state.goal_animation_timer = 5 * FPS; self.game_state.goal_animation_color = winner_color_info['led']
    
    def trigger_scan_animation(self, player_num, pri_color_dict, sec_color_dict):
        """Helper function to start the RFID scan/color change LED animation."""
        if not pri_color_dict:
            return

        self.game_state.rfid_scan_animation_active = True
        self.game_state.rfid_scan_animation_player = player_num
        self.game_state.rfid_scan_animation_start_time = pygame.time.get_ticks()
        self.game_state.rfid_scan_animation_end_time = self.game_state.rfid_scan_animation_start_time + 3000
        self.game_state.rfid_scan_animation_pri_color = pri_color_dict['led']
        
        if sec_color_dict:
            self.game_state.rfid_scan_animation_sec_color = sec_color_dict['led']
        else:
            # Default to a dimmed version of the primary color if no secondary is chosen
            self.game_state.rfid_scan_animation_sec_color = tuple(c // 2 for c in pri_color_dict['led'])

    def load_player_profile(self, card_id, player_num, name_dd, pri_color_dd, sec_color_dd, player_names_list, color_names_list, sec_color_names_list):
        card_id_str = str(card_id)
        if card_id_str in self.players:
            player_data = self.players[card_id_str]
            
            try: name_dd.selected_index = player_names_list.index(player_data['name'])
            except ValueError: print(f"Warning: Saved name '{player_data['name']}' not found.")
            try: pri_color_dd.selected_index = color_names_list.index(player_data['primary_color'])
            except ValueError: print(f"Warning: Saved primary color '{player_data['primary_color']}' not found.")
            try: sec_color_dd.selected_index = sec_color_names_list.index(player_data['secondary_color'])
            except ValueError: print(f"Warning: Saved secondary color '{player_data['secondary_color']}' not found.")
            
            pri_color_name = player_data.get('primary_color')
            sec_color_name = player_data.get('secondary_color')
            pri_color_dict = next((c for c in self.custom_colors if c['name'] == pri_color_name), None)
            sec_color_dict = next((c for c in self.custom_colors if c['name'] == sec_color_name), None)

            self.trigger_scan_animation(player_num, pri_color_dict, sec_color_dict)

            self.game_state.rfid_welcome_message = f"Welcome {player_data['name']}"
            self.game_state.rfid_welcome_message_end_time = pygame.time.get_ticks() + 2000
            self.game_state.rfid_welcome_message_player = player_num
            if pri_color_dict:
                self.game_state.rfid_welcome_message_color = pri_color_dict['display']
            else:
                self.game_state.rfid_welcome_message_color = COLOR_WHITE
            
            print(f"Loaded profile for player {player_num} from card {card_id_str}")
        else:
            self.game_state.rfid_load_message = "No data on card"
            self.game_state.rfid_load_message_end_time = pygame.time.get_ticks() + 2000
            self.game_state.rfid_load_message_player = player_num
            print(f"Card {card_id_str} not found in database for player {player_num}.")

    def run(self):
        # --- UI Initialization (runs once) ---
        color_names = [c['name'] for c in self.custom_colors]
        secondary_color_names = ["None"] + color_names
        dd_name_width, dd_color_width = 450 * self.scale_factor, 300 * self.scale_factor
        p1_name_dd = Dropdown(self.SCREEN_WIDTH*0.1, 250*self.scale_factor, dd_name_width, 60*self.scale_factor, VISITOR_NAMES, self.setup_dropdown_font, COLOR_RED)
        p1_pri_color_dd = Dropdown(self.SCREEN_WIDTH*0.1, 450*self.scale_factor, dd_color_width, 60*self.scale_factor, color_names, self.setup_dropdown_font, COLOR_RED)
        p1_sec_color_dd = Dropdown(self.SCREEN_WIDTH*0.1, 650*self.scale_factor, dd_color_width, 60*self.scale_factor, secondary_color_names, self.setup_dropdown_font, COLOR_RED)
        p2_name_dd = Dropdown(self.SCREEN_WIDTH*0.9 - dd_name_width, 250*self.scale_factor, dd_name_width, 60*self.scale_factor, HOME_NAMES, self.setup_dropdown_font, COLOR_BLUE)
        p2_pri_color_dd = Dropdown(self.SCREEN_WIDTH*0.9 - dd_color_width, 450*self.scale_factor, dd_color_width, 60*self.scale_factor, color_names, self.setup_dropdown_font, COLOR_BLUE)
        p2_sec_color_dd = Dropdown(self.SCREEN_WIDTH*0.9 - dd_color_width, 650*self.scale_factor, dd_color_width, 60*self.scale_factor, secondary_color_names, self.setup_dropdown_font, COLOR_BLUE)
        p1_name_dd.selected_index = VISITOR_NAMES.index("USSR") if "USSR" in VISITOR_NAMES else 0
        p2_name_dd.selected_index = HOME_NAMES.index("USA") if "USA" in HOME_NAMES else 0
        try: p1_pri_color_dd.selected_index = color_names.index("Default Red")
        except ValueError: p1_pri_color_dd.selected_index = 0
        try: p2_pri_color_dd.selected_index = color_names.index("Blue")
        except ValueError: p2_pri_color_dd.selected_index = 0
        p1_sec_color_dd.selected_index, p2_sec_color_dd.selected_index = 0, 0
        
        button_width = 300 * self.scale_factor
        button_height = 80 * self.scale_factor
        p1_ready_button = Button(self.SCREEN_WIDTH*0.1, self.SCREEN_HEIGHT - 150*self.scale_factor, button_width, button_height, "P1 READY", self.setup_button_font)
        p2_ready_button = Button(self.SCREEN_WIDTH*0.9 - button_width, self.SCREEN_HEIGHT - 150*self.scale_factor, button_width, button_height, "P2 READY", self.setup_button_font)
        
        button_spacing = 20 * self.scale_factor
        p1_save_button = Button(p1_ready_button.rect.right + button_spacing, p1_ready_button.rect.y, button_width, button_height, "Save", self.setup_button_font)
        p2_save_button = Button(p2_ready_button.rect.left - button_width - button_spacing, p2_ready_button.rect.y, button_width, button_height, "Save", self.setup_button_font)
        
        dropdowns = [p1_name_dd, p1_pri_color_dd, p1_sec_color_dd, p2_name_dd, p2_pri_color_dd, p2_sec_color_dd]
        expanded_dropdown = None
        
        running = True
        frame_counter = 0
        while running:
            dt = self.clock.tick(FPS)
            current_time = pygame.time.get_ticks()
            frame_counter += 1
            if self.volume_display_timer > 0: self.volume_display_timer -= 1
            
            if self.game_state.rfid_save_message and current_time > self.game_state.rfid_save_message_end_time:
                self.game_state.rfid_save_message = ""
            if self.game_state.rfid_load_message and current_time > self.game_state.rfid_load_message_end_time:
                self.game_state.rfid_load_message = ""
            if self.game_state.rfid_welcome_message and current_time > self.game_state.rfid_welcome_message_end_time:
                self.game_state.rfid_welcome_message = ""

            # Store old indices before event loop to detect changes
            old_p1_pri_idx = p1_pri_color_dd.selected_index
            old_p1_sec_idx = p1_sec_color_dd.selected_index
            old_p2_pri_idx = p2_pri_color_dd.selected_index
            old_p2_sec_idx = p2_sec_color_dd.selected_index
            
            # --- Unified Event Handling ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                    break
                
                # --- Custom GPIO Events ---
                if event.type == self.P1_FACEOFF_EVENT:
                    self.handle_player1_faceoff()
                if event.type == self.P2_FACEOFF_EVENT:
                    self.handle_player2_faceoff()

                # --- MOUSE CLICKS (SETUP ONLY) ---
                if self.game_state.game_mode == 'SETUP':
                    if self.game_state.show_rfid_popup_for_player is None:
                        if p1_ready_button.is_clicked(event): self.handle_player1_faceoff()
                        if p2_ready_button.is_clicked(event): self.handle_player2_faceoff()
                        if p1_save_button.is_clicked(event): self.game_state.show_rfid_popup_for_player = 1
                        if p2_save_button.is_clicked(event): self.game_state.show_rfid_popup_for_player = 2

                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            clicked_a_box = False
                            if expanded_dropdown:
                                for i, rect in enumerate(expanded_dropdown.option_rects):
                                    if rect.collidepoint(event.pos):
                                        expanded_dropdown.selected_index = i
                                        expanded_dropdown = None
                                        clicked_a_box = True
                                        break
                            if not clicked_a_box:
                                expanded_dropdown = None
                                for dd in dropdowns:
                                    if dd.rect.collidepoint(event.pos): expanded_dropdown = dd; break
                
                # --- KEYBOARD PRESSES (ALL MODES) ---
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.game_state.show_rfid_popup_for_player is not None:
                            self.game_state.show_rfid_popup_for_player = None
                        else:
                            running = False
                    
                    if event.key == pygame.K_f: self.handle_player1_faceoff()
                    if event.key == pygame.K_g: self.handle_player2_faceoff()
                    if event.key in (pygame.K_PLUS, pygame.K_EQUALS): self.increase_volume()
                    if event.key == pygame.K_MINUS: self.decrease_volume()
                    if event.key == pygame.K_m: self.toggle_mute()

                    if self.game_state.game_mode == 'GAME':
                        if not self.game_state.game_over:
                            if event.key == pygame.K_u: self.handle_usa_goal()
                            if event.key == pygame.K_i: self.handle_ussr_goal()
                            if event.key == pygame.K_j: self.handle_usa_sog()
                            if event.key == pygame.K_k: self.handle_ussr_sog()
                        if event.key == pygame.K_PERIOD: self.game_state.time_multiplier = min(20.0, self.game_state.time_multiplier + 1.0)
                        if event.key == pygame.K_COMMA: self.game_state.time_multiplier = max(1.0, self.game_state.time_multiplier - 1.0)
                        if event.key == pygame.K_r: self.game_state.game_mode = 'SETUP'; self.game_state.reset()

            if not running: break
            
            # --- State Updates ---
            if self.game_state.game_mode == 'VIDEO':
                if self.video_interrupt_requested or (self.video_process and self.video_process.poll() is not None):
                    self.stop_video(); self.video_interrupt_requested = False
            elif self.game_state.game_mode == 'GAME':
                self.game_state.update_clock(dt); self.update_motor(); self.check_period_end(); self.update_intermission(); self.update_goal_celebration_timer(); self.update_sog_timer(); self.update_goal_celebration_effects()

                # --- Staggered RFID Polling (Final Implementation) ---
                if self.game_state.goal_celebration_team is None:
                    # Poll away reader roughly once per second
                    if frame_counter % 60 == 0:
                        # BRUTE-FORCE FIX: Re-initialize the reader to clear any SPI bus conflicts.
                        try:
                            self.reader_away = SimpleMFRC522(bus=0, device=0, spd=1000000)
                            if self.reader_away and current_time > self.game_state.rfid_away_cooldown_end_time:
                                card_id = self.reader_away.read_id_no_block()
                                if card_id:
                                    if self.faceoff_sound: self.faceoff_sound.play()
                                    self.game_state.rfid_away_cooldown_end_time = current_time + 2000
                        except Exception as e:
                            print(f"Error re-initializing away RFID reader: {e}")
                            self.reader_away = None
                    
                    # Poll home reader roughly once per second, offset by half a second
                    if frame_counter % 60 == 30:
                        # BRUTE-FORCE FIX: Re-initialize the reader to clear any SPI bus conflicts.
                        try:
                            self.reader_home = SimpleMFRC522(bus=0, device=1, spd=1000000)
                            if self.reader_home and current_time > self.game_state.rfid_home_cooldown_end_time:
                                card_id = self.reader_home.read_id_no_block()
                                if card_id:
                                    if self.faceoff_sound: self.faceoff_sound.play()
                                    self.game_state.rfid_home_cooldown_end_time = current_time + 2000
                        except Exception as e:
                            # If re-init fails, print an error but don't crash
                            print(f"Error re-initializing home RFID reader: {e}")
                            self.reader_home = None


                if self.game_state.goal_animation_active: self.update_goal_animation()
                elif self.game_state.game_over: self.clear_leds()
                elif self.game_state.game_active or self.game_state.overtime_active: self.game_active_effect()
                else: self.idle_effect()
            elif self.game_state.game_mode == 'SETUP':
                p1_ready_button.color = (0, 150, 0) if self.game_state.player1_ready else COLOR_GRAY
                p2_ready_button.color = (0, 150, 0) if self.game_state.player2_ready else COLOR_GRAY
                
                # Check for manual color changes to trigger animation
                if p1_pri_color_dd.selected_index != old_p1_pri_idx or p1_sec_color_dd.selected_index != old_p1_sec_idx:
                    pri_color_dict = self.custom_colors[p1_pri_color_dd.selected_index]
                    sec_color_dict = None
                    if p1_sec_color_dd.selected_index > 0:
                        sec_color_dict = self.custom_colors[p1_sec_color_dd.selected_index - 1]
                    self.trigger_scan_animation(1, pri_color_dict, sec_color_dict)
                
                if p2_pri_color_dd.selected_index != old_p2_pri_idx or p2_sec_color_dd.selected_index != old_p2_sec_idx:
                    pri_color_dict = self.custom_colors[p2_pri_color_dd.selected_index]
                    sec_color_dict = None
                    if p2_sec_color_dd.selected_index > 0:
                        sec_color_dict = self.custom_colors[p2_sec_color_dd.selected_index - 1]
                    self.trigger_scan_animation(2, pri_color_dict, sec_color_dict)

                # --- Throttled RFID Polling ---
                if frame_counter % 15 == 0:
                    if self.game_state.show_rfid_popup_for_player is None:
                        if self.reader_away and current_time > self.game_state.rfid_away_cooldown_end_time:
                            card_id = self.reader_away.read_id_no_block()
                            if card_id:
                                if self.rfid_sound: self.rfid_sound.play()
                                self.load_player_profile(card_id, 1, p1_name_dd, p1_pri_color_dd, p1_sec_color_dd, VISITOR_NAMES, color_names, secondary_color_names)
                                self.game_state.rfid_away_cooldown_end_time = current_time + 2000
                        if self.reader_home and current_time > self.game_state.rfid_home_cooldown_end_time:
                            card_id = self.reader_home.read_id_no_block()
                            if card_id:
                                if self.rfid_sound: self.rfid_sound.play()
                                self.load_player_profile(card_id, 2, p2_name_dd, p2_pri_color_dd, p2_sec_color_dd, HOME_NAMES, color_names, secondary_color_names)
                                self.game_state.rfid_home_cooldown_end_time = current_time + 2000
                    else: # A save dialog is open
                        player_num = self.game_state.show_rfid_popup_for_player
                        reader = self.reader_away if player_num == 1 else self.reader_home
                        if reader:
                            card_id = reader.read_id_no_block()
                            if card_id:
                                if self.rfid_sound: self.rfid_sound.play()
                                name_dd = p1_name_dd if player_num == 1 else p2_name_dd
                                pri_color_dd = p1_pri_color_dd if player_num == 1 else p2_pri_color_dd
                                sec_color_dd = p1_sec_color_dd if player_num == 1 else p2_sec_color_dd

                                player_data = {
                                    "name": name_dd.get_selected(),
                                    "primary_color": self.custom_colors[pri_color_dd.selected_index]['name'],
                                    "secondary_color": sec_color_dd.get_selected()
                                }
                                self.players[str(card_id)] = player_data
                                self.save_player_data()
                                
                                self.game_state.rfid_save_message = "Settings Saved!"
                                self.game_state.rfid_save_message_end_time = current_time + 2000
                                self.game_state.rfid_save_message_player = player_num
                                self.game_state.show_rfid_popup_for_player = None
                                if player_num == 1:
                                    self.game_state.rfid_away_cooldown_end_time = current_time + 2000
                                else:
                                    self.game_state.rfid_home_cooldown_end_time = current_time + 2000
                
                if self.game_state.player1_ready and self.game_state.player2_ready:
                    self.game_state.player1_name, self.game_state.player2_name = p1_name_dd.get_selected(), p2_name_dd.get_selected()
                    self.game_state.player1_primary_color, self.game_state.player2_primary_color = self.custom_colors[p1_pri_color_dd.selected_index], self.custom_colors[p2_pri_color_dd.selected_index]
                    self.game_state.player1_secondary_color = None if p1_sec_color_dd.get_selected() == "None" else self.custom_colors[p1_sec_color_dd.selected_index - 1]
                    self.game_state.player2_secondary_color = None if p2_sec_color_dd.get_selected() == "None" else self.custom_colors[p2_sec_color_dd.selected_index - 1]
                    self.play_video_hardware('MOI_Intro.mp4'); continue
                
                if self.game_state.rfid_scan_animation_active:
                    self.update_rfid_scan_animation()
                else:
                    self.idle_effect()

            # --- Drawing ---
            self.screen.fill(COLOR_BLACK)
            if self.game_state.game_mode == 'SETUP':
                self.screen.fill(COLOR_BLUE)
                if self.setup_logo: self.screen.blit(self.setup_logo, self.setup_logo.get_rect(center=(self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT/2)))
                p1_title = self.setup_header_font.render("Visitor", True, COLOR_RED); self.screen.blit(p1_title, p1_title.get_rect(center=(self.SCREEN_WIDTH*0.25, 100*self.scale_factor)))
                p2_title = self.setup_header_font.render("Home", True, COLOR_WHITE); self.screen.blit(p2_title, p2_title.get_rect(center=(self.SCREEN_WIDTH*0.75, 100*self.scale_factor)))
                self.screen.blit(self.setup_label_font.render("Name:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.1, 190*self.scale_factor)); self.screen.blit(self.setup_label_font.render("Primary Color:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.1, 390*self.scale_factor)); self.screen.blit(self.setup_label_font.render("Secondary Color:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.1, 590*self.scale_factor))
                self.screen.blit(self.setup_label_font.render("Name:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.9 - dd_name_width, 190*self.scale_factor)); self.screen.blit(self.setup_label_font.render("Primary Color:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.9 - dd_color_width, 390*self.scale_factor)); self.screen.blit(self.setup_label_font.render("Secondary Color:", True, COLOR_BLACK), (self.SCREEN_WIDTH*0.9 - dd_color_width, 590*self.scale_factor))
                
                p1_ready_button.draw(self.screen); p2_ready_button.draw(self.screen)
                p1_save_button.draw(self.screen); p2_save_button.draw(self.screen)

                if self.volume_display_timer > 0:
                    volume_text = "VOL MUTE" if self.game_state.is_muted else f"VOL {int(self.game_state.volume * 100)}%"; text_surf = self.tiny_font.render(volume_text, True, COLOR_WHITE); self.screen.blit(text_surf, text_surf.get_rect(center=(self.SCREEN_WIDTH*0.5, self.SCREEN_HEIGHT-50*self.scale_factor)))
                
                for dd in dropdowns:
                    if dd != expanded_dropdown:
                        dd.draw_main_box(self.screen)

                if expanded_dropdown:
                    expanded_dropdown.draw_main_box(self.screen)
                    expanded_dropdown.draw_expanded_list(self.screen, p1_ready_button.rect.y)

                if self.game_state.show_rfid_popup_for_player is not None:
                    player_num = self.game_state.show_rfid_popup_for_player
                    overlay = pygame.Surface((self.SCREEN_WIDTH / 2, self.SCREEN_HEIGHT), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 180))
                    overlay_x_pos = 0 if player_num == 1 else self.SCREEN_WIDTH / 2
                    self.screen.blit(overlay, (overlay_x_pos, 0))
                    
                    popup_text = self.setup_label_font.render("Tap card to save...", True, COLOR_WHITE)
                    popup_center_x = self.SCREEN_WIDTH * 0.25 if player_num == 1 else self.SCREEN_WIDTH * 0.75
                    self.screen.blit(popup_text, popup_text.get_rect(center=(popup_center_x, self.SCREEN_HEIGHT/2)))

                if self.game_state.rfid_save_message or self.game_state.rfid_load_message or self.game_state.rfid_welcome_message:
                    player_num = None
                    message_to_display = ""
                    message_color = COLOR_WHITE

                    if self.game_state.rfid_welcome_message:
                        player_num = self.game_state.rfid_welcome_message_player
                        message_to_display = self.game_state.rfid_welcome_message
                        message_color = self.game_state.rfid_welcome_message_color
                    elif self.game_state.rfid_save_message:
                        player_num = self.game_state.rfid_save_message_player
                        message_to_display = self.game_state.rfid_save_message
                        message_color = COLOR_YELLOW
                    elif self.game_state.rfid_load_message:
                        player_num = self.game_state.rfid_load_message_player
                        message_to_display = self.game_state.rfid_load_message
                        message_color = COLOR_RED
                    
                    if player_num is not None:
                        overlay = pygame.Surface((self.SCREEN_WIDTH / 2, self.SCREEN_HEIGHT), pygame.SRCALPHA)
                        overlay.fill((0, 0, 0, 180))
                        overlay_x_pos = 0 if player_num == 1 else self.SCREEN_WIDTH / 2
                        self.screen.blit(overlay, (overlay_x_pos, 0))
                        
                        msg_surf = self.setup_label_font.render(message_to_display, True, message_color)
                        msg_center_x = self.SCREEN_WIDTH * 0.25 if player_num == 1 else self.SCREEN_WIDTH * 0.75
                        self.screen.blit(msg_surf, msg_surf.get_rect(center=(msg_center_x, self.SCREEN_HEIGHT/2)))

            elif self.game_state.game_mode == 'GAME': self.draw_game_screen()
            
            if self.game_state.game_mode != 'VIDEO':
                pygame.display.flip()
        
        if self.video_process and self.video_process.poll() is None: self.video_process.terminate()
        self.clear_leds(); pygame.quit(); sys.exit()
    
    def update_sog_timer(self):
        if self.game_state.recent_sog_timer > 0: self.game_state.recent_sog_timer -= 1

    def update_goal_celebration_effects(self):
        self.game_state.particles = [p for p in self.game_state.particles if p.lifetime > 0]
        for p in self.game_state.particles: p.update()
        if (self.game_state.goal_celebration_team or self.game_state.game_end_celebration_active) and random.randint(0, 20) == 0:
            if self.game_state.usa_special_celebration and self.game_state.goal_celebration_team == "USA":
                red_disp = next((c['display'] for c in self.custom_colors if c['name'] == 'Default Red'), COLOR_RED)
                white_disp = next((c['display'] for c in self.custom_colors if c['name'] == 'Default White'), COLOR_WHITE)
                blue_disp = next((c['display'] for c in self.custom_colors if c['name'] == 'Blue'), COLOR_BLUE)
                colors = [red_disp, white_disp, blue_disp]
                self.create_firework_burst(random.choice(colors))
            elif self.game_state.goal_celebration_team == "USSR" and self.game_state.player1_name == "USSR" and self.game_state.player1_primary_color and self.game_state.player1_primary_color.get('name') == 'Default Red' and self.game_state.player1_secondary_color is None:
                red_disp = next((c['display'] for c in self.custom_colors if c['name'] == 'Default Red'), COLOR_RED)
                white_disp = next((c['display'] for c in self.custom_colors if c['name'] == 'Default White'), COLOR_WHITE)
                colors = [red_disp, white_disp]
                self.create_firework_burst(random.choice(colors))
            else:
                primary_color = self.game_state.player1_primary_color if self.game_state.goal_celebration_team == self.game_state.player1_name else self.game_state.player2_primary_color
                secondary_color = self.game_state.player1_secondary_color if self.game_state.goal_celebration_team == self.game_state.player1_name else self.game_state.player2_secondary_color
                firework_color = secondary_color['display'] if secondary_color else primary_color['display']
                self.create_firework_burst(firework_color)

    def draw_digital_text(self, text, font, color, center_pos):
        dark_color = tuple(c * 0.15 for c in color)
        placeholder = "8" * len(text)
        if ":" in text: placeholder = "88:88"
        dark_surf = font.render(placeholder, True, dark_color); self.screen.blit(dark_surf, dark_surf.get_rect(center=center_pos))
        text_surf = font.render(text, True, color); self.screen.blit(text_surf, text_surf.get_rect(center=center_pos))

    def draw_outlined_text(self, text, font, primary_color, secondary_color, center_pos):
        offset = int(8 * self.scale_factor)
        positions = [(center_pos[0]-offset, center_pos[1]-offset), (center_pos[0]+offset, center_pos[1]-offset), (center_pos[0]-offset, center_pos[1]+offset), (center_pos[0]+offset, center_pos[1]+offset)]
        for pos in positions: self.screen.blit(font.render(text, True, secondary_color), font.render(text, True, secondary_color).get_rect(center=pos))
        self.screen.blit(font.render(text, True, primary_color), font.render(text, True, primary_color).get_rect(center=pos))

    def draw_scoreboard(self):
        if self.game_state.player1_secondary_color: self.draw_outlined_text(self.game_state.player1_name, self.medium_font, self.game_state.player1_primary_color['display'], self.game_state.player1_secondary_color['display'], (self.SCREEN_WIDTH*0.25, int(189*self.scale_factor)))
        else: self.draw_digital_text(self.game_state.player1_name, self.medium_font, self.game_state.player1_primary_color['display'], (self.SCREEN_WIDTH*0.25, int(189*self.scale_factor)))
        if self.game_state.player2_secondary_color: self.draw_outlined_text(self.game_state.player2_name, self.medium_font, self.game_state.player2_primary_color['display'], self.game_state.player2_secondary_color['display'], (self.SCREEN_WIDTH*0.75, int(189*self.scale_factor)))
        else: self.draw_digital_text(self.game_state.player2_name, self.medium_font, self.game_state.player2_primary_color['display'], (self.SCREEN_WIDTH*0.75, int(189*self.scale_factor)))
        self.draw_digital_text(f"{self.game_state.ussr_score:02}", self.large_font, COLOR_YELLOW, (self.SCREEN_WIDTH*0.25, int(486*self.scale_factor)))
        self.draw_digital_text(f"{self.game_state.usa_score:02}", self.large_font, COLOR_YELLOW, (self.SCREEN_WIDTH*0.75, int(486*self.scale_factor)))
        if self.game_state.game_over: period_label, font = "FINAL", self.small_font
        elif self.game_state.overtime_active: period_label, font = "SUDDEN", self.sudden_death_font
        else: period_label, font = "PERIOD", self.small_font
        if self.game_state.overtime_active and not self.game_state.game_over: self.draw_digital_text("SUDDEN", self.sudden_death_font, COLOR_WHITE, (self.SCREEN_WIDTH/2, int(120*self.scale_factor))); self.draw_digital_text("DEATH", self.sudden_death_font, COLOR_WHITE, (self.SCREEN_WIDTH/2, int(180*self.scale_factor)))
        else: self.draw_digital_text(period_label, font, COLOR_WHITE, (self.SCREEN_WIDTH/2, int(135*self.scale_factor)))
        if not self.game_state.game_over:
            if self.game_state.overtime_active: self.draw_digital_text("OT", self.medium_font, COLOR_RED, (self.SCREEN_WIDTH/2, int(297*self.scale_factor)))
            else: self.draw_digital_text(str(self.game_state.period), self.medium_font, COLOR_RED, (self.SCREEN_WIDTH/2, int(297*self.scale_factor)))
        if not self.game_state.overtime_active:
            minutes, seconds = divmod(int(self.game_state.game_clock / 1000), 60); self.draw_digital_text(f"{minutes:02}:{seconds:02}", self.medium_font, COLOR_RED, (self.SCREEN_WIDTH / 2, int(540 * self.scale_factor)))
        self.draw_digital_text(f"SPEED x{int(self.game_state.time_multiplier)}", self.tiny_font, COLOR_WHITE, (self.SCREEN_WIDTH*0.35, int(675*self.scale_factor)))
        volume_text = "VOL MUTE" if self.game_state.is_muted else f"VOL {int(self.game_state.volume * 100)}%"; self.draw_digital_text(volume_text, self.tiny_font, COLOR_WHITE, (self.SCREEN_WIDTH*0.65, int(675*self.scale_factor)))
        self.draw_digital_text("SHOTS ON GOAL", self.small_font, COLOR_WHITE, (self.SCREEN_WIDTH/2, int(810*self.scale_factor)))
        self.draw_digital_text(f"{self.game_state.ussr_sog:02}", self.medium_font, COLOR_WHITE, (self.SCREEN_WIDTH*0.25, int(945*self.scale_factor)))
        self.draw_digital_text(f"{self.game_state.usa_sog:02}", self.medium_font, COLOR_WHITE, (self.SCREEN_WIDTH*0.75, int(945*self.scale_factor)))

    def draw_goal_celebration(self):
        for p in self.game_state.particles: p.draw(self.screen)
        team_name = self.game_state.goal_celebration_team
        color_info = self.game_state.player1_primary_color if team_name == self.game_state.player1_name else self.game_state.player2_primary_color
        text_surf = self.goal_font.render(f"GOAL {team_name}", True, color_info['display']); self.screen.blit(text_surf, text_surf.get_rect(center=(self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT/2)))
    def draw_game_end_celebration(self):
        self.screen.fill(COLOR_BLACK)
        for p in self.game_state.particles: p.draw(self.screen)
        winner_name = self.game_state.winner_name
        color_info = self.game_state.player1_primary_color if winner_name == self.game_state.player1_name else self.game_state.player2_primary_color
        text_surf = self.goal_font.render(f"{winner_name} WINS!", True, color_info['display']); self.screen.blit(text_surf, text_surf.get_rect(center=(self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT/2)))

    def draw_intermission_screen(self):
        if self.game_state.overtime_active: self.draw_digital_text("SUDDEN DEATH!", self.medium_font, COLOR_WHITE, (self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT*0.4))
        else: self.draw_digital_text(f"PERIOD {self.game_state.period + 1}", self.large_font, COLOR_WHITE, (self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT*0.4))
        self.draw_digital_text("GET READY", self.medium_font, COLOR_RED, (self.SCREEN_WIDTH/2, self.SCREEN_HEIGHT*0.7))
    def draw_game_screen(self):
        self.screen.fill(COLOR_BLACK)
        if self.game_state.game_end_celebration_active: self.draw_game_end_celebration()
        elif self.game_state.intermission_active: self.draw_intermission_screen()
        elif self.game_state.goal_celebration_team: self.draw_goal_celebration()
        else: self.draw_scoreboard()
    def check_period_end(self):
        if self.game_state.game_clock > 0 or self.game_state.game_over or self.game_state.intermission_active or self.game_state.overtime_active: return
        if self.buzzer_sound: self.buzzer_sound.play()
        self.game_state.game_active = False
        if self.game_state.period < 3: self.game_state.intermission_active, self.game_state.intermission_timer = True, 3 * FPS
        elif self.game_state.period == 3:
            if self.game_state.ussr_score == self.game_state.usa_score: self.game_state.overtime_active, self.game_state.intermission_active, self.game_state.intermission_timer = True, True, 3 * FPS
            else: self.trigger_game_end("player1" if self.game_state.ussr_score > self.game_state.usa_score else "player2")
    def update_intermission(self):
        if not self.game_state.intermission_active: return
        self.game_state.intermission_timer -= 1
        if self.game_state.intermission_timer <= 0:
            self.game_state.intermission_active = False; self.clear_leds()
            self.game_state.game_lights_set = False # Reset the flag
            if self.game_state.overtime_active: print("Sudden Death Overtime! Next goal wins.")
            else: self.game_state.period += 1; self.game_state.game_clock = 20 * 60 * 1000; self.game_state.game_active = True; print(f"Period {self.game_state.period} starting automatically!")
    def update_goal_celebration_timer(self):
        if self.game_state.goal_celebration_timer > 0:
            self.game_state.goal_celebration_timer -= 1
            if self.game_state.goal_celebration_timer <= 0:
                self.game_state.goal_celebration_team = None; self.game_state.particles = []
                if self.game_state.game_end_celebration_active: self.game_state.game_end_celebration_active = False; self.game_state.overtime_active = False
                else: self.game_state.game_over = False

if __name__ == '__main__':
    scoreboard = Scoreboard()
    scoreboard.run()














