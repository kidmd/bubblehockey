# Raspberry Pi Hockey Scoreboard Controller
# By Gemini
#
# Description:
# This program runs on a Raspberry Pi to control a bubble hockey scoreboard.
# It uses the gpiozero library for sensors/buttons, a rotary encoder for volume,
# and the rpi_ws281x library to control a WS2812B addressable LED ring.
#
# GPIO Pin Assignments (BCM Mode):
#   - USA Goal: GPIO 17
#   - USSR Goal: GPIO 27 (Moved from 18 to avoid conflict with LEDs)
#   - USA SOG: GPIO 22
#   - USSR SOG: GPIO 23
#   - Faceoff Sensor 1: GPIO 24
#   - Faceoff Sensor 2: GPIO 26
#   - Faceoff Motor Relay: GPIO 25
#   - Volume Encoder CLK: GPIO 5
#   - Volume Encoder DT: GPIO 6
#   - Volume Encoder SW (Button): GPIO 13
#   - WS2812B LED Ring Data: GPIO 18
#
# Keyboard Controls are unchanged.

import pygame
import sys
from gpiozero import Button, OutputDevice, RotaryEncoder
import time
import board
import neopixel
import math
import random

# --- GPIO Pin Configuration ---
USA_GOAL_PIN = 17
USSR_GOAL_PIN = 27 # Moved from 18
USA_SOG_PIN = 22
USSR_SOG_PIN = 23
FACEOFF_PIN_1 = 24
FACEOFF_PIN_2 = 26
MOTOR_PIN = 25
VOLUME_CLK_PIN = 5
VOLUME_DT_PIN = 6
VOLUME_SW_PIN = 13
LED_PIN = board.D18

# --- LED Ring Configuration ---
LED_COUNT = 128
LED_BRIGHTNESS = 0.5
# Define the 5 concentric rings: (start_index, number_of_leds)
RING_DEFINITIONS = [
    (0, 8),    # Center ring
    (8, 16),   # Second ring
    (24, 24),  # Third ring
    (48, 35),  # Fourth ring
    (83, 45)   # Outer ring
]


# --- Game Configuration ---
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS = 60
MOTOR_RUN_TIME = 0.5

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (200, 0, 0)
COLOR_YELLOW = (220, 220, 0)
COLOR_BLUE = (0, 0, 200)

# --- Animation Classes ---
class Particle:
    def __init__(self, burst_x, burst_y, color):
        self.burst_x = burst_x
        self.burst_y = burst_y
        self.color = color
        
        # Position relative to burst center
        self.x, self.y, self.z = 0, 0, 0
        
        # 3D velocity for a spherical explosion
        angle1 = random.uniform(0, 2 * math.pi)
        angle2 = random.uniform(0, 2 * math.pi)
        # More uniform speed for a rounder burst
        speed = random.uniform(3.0, 3.2)
        
        self.vx = speed * math.sin(angle1) * math.cos(angle2)
        self.vy = speed * math.sin(angle1) * math.sin(angle2)
        self.vz = speed * math.cos(angle1)
        
        self.lifetime = random.randint(60, 90)
        # Reduced gravity for a slower fall
        self.gravity = 0.025
        # Perspective depth
        self.perspective = 300

    def update(self):
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        self.lifetime -= 1

    def draw(self, screen):
        if self.lifetime > 0:
            # Project 3D coordinates to 2D screen
            scale = self.perspective / (self.perspective + self.z)
            projected_x = self.x * scale + self.burst_x
            projected_y = self.y * scale + self.burst_y
            
            size = 5
            # Fade out particles as they die by shrinking them
            if self.lifetime < 20:
                size = int(size * (self.lifetime / 20))
            
            if size > 0:
                pygame.draw.circle(screen, self.color, (int(projected_x), int(projected_y)), size)

# Game State Class
class GameState:
    def __init__(self):
        self.volume = 0.5
        self.reset()

    def reset(self):
        pygame.mixer.stop()
        self.usa_score = 0
        self.ussr_score = 0
        self.usa_sog = 0
        self.ussr_sog = 0
        self.period = 1
        self.game_clock = 20 * 60 * 1000
        self.game_active = False
        self.time_multiplier = 10.0
        self.game_over = False
        self.goal_celebration_team = None
        self.intermission_active = False
        self.intermission_timer = 0
        self.overtime_active = False
        self.goal_celebration_timer = 0
        self.is_muted = False
        self.volume_before_mute = self.volume
        self.recent_sog_timer = 0
        self.goal_animation_active = False
        self.goal_animation_timer = 0
        self.goal_animation_color = (0,0,0)
        self.idle_animation_step = 0
        self.particles = []


    def update_clock(self, dt):
        if self.game_active and self.game_clock > 0:
            self.game_clock -= dt * self.time_multiplier
            if self.game_clock < 0:
                self.game_clock = 0

# Main Scoreboard Class
class Scoreboard:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption("Vintage Hockey Scoreboard")
        self.clock = pygame.time.Clock()
        self.game_state = GameState()
        self.large_font = pygame.font.SysFont('monospace', 324, bold=True)
        self.medium_font = pygame.font.SysFont('monospace', 162, bold=True)
        self.small_font = pygame.font.SysFont('monospace', 108, bold=True)
        self.sudden_death_font = pygame.font.SysFont('monospace', 80, bold=True)
        self.tiny_font = pygame.font.SysFont('monospace', 54, bold=True)
        self.goal_font = pygame.font.SysFont('monospace', 350, bold=True)
        
        try:
            self.pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False)
            print("LED Ring initialized.")
        except Exception as e:
            print(f"Could not initialize LED Ring: {e}")
            self.pixels = None

        self.all_sounds = []
        self.load_sounds()
        self.motor = None
        self.volume_encoder = None
        self.volume_button = None
        self.setup_gpio()
        self.set_master_volume(self.game_state.volume)
        self.clear_leds()

    def set_master_volume(self, new_volume):
        self.game_state.volume = round(max(0.0, min(1.0, new_volume)), 1)
        if new_volume > 0: self.game_state.is_muted = False
        for sound in self.all_sounds:
            if sound:
                if sound == self.goal_horn_sound: sound.set_volume(self.game_state.volume * 0.5)
                else: sound.set_volume(self.game_state.volume)

    def increase_volume(self): self.set_master_volume(self.game_state.volume + 0.1)
    def decrease_volume(self): self.set_master_volume(self.game_state.volume - 0.1)

    def toggle_mute(self):
        self.game_state.is_muted = not self.game_state.is_muted
        if self.game_state.is_muted:
            self.game_state.volume_before_mute = self.game_state.volume
            self.set_master_volume(0)
        else:
            if self.game_state.volume_before_mute > 0: self.set_master_volume(self.game_state.volume_before_mute)
            else: self.set_master_volume(0.5)

    def handle_volume_button_press(self):
        if self.game_state.game_over:
            self.game_state.reset()
            self.clear_leds()
            self.set_master_volume(self.game_state.volume)
        else: self.toggle_mute()

    def clear_leds(self):
        if self.pixels:
            self.game_state.goal_animation_active = False
            self.pixels.brightness = LED_BRIGHTNESS
            self.pixels.fill((0, 0, 0))
            self.pixels.show()

    def update_goal_animation(self):
        if not self.pixels or not self.game_state.goal_animation_active:
            return
        
        self.game_state.goal_animation_timer -= 1
        if self.game_state.goal_animation_timer <= 0:
            self.game_state.goal_animation_active = False
            self.clear_leds()
            return

        total_duration_frames = 5 * FPS
        current_frame = total_duration_frames - self.game_state.goal_animation_timer
        half_second_in_frames = FPS // 2
        cycle_position = (current_frame % half_second_in_frames) / half_second_in_frames
        
        static_color = self.game_state.goal_animation_color

        self.pixels.fill((0, 0, 0))

        for start_index, num_leds in RING_DEFINITIONS:
            arc_length = num_leds // 3
            start_of_arc_offset = int(cycle_position * num_leds)
            
            for i in range(arc_length):
                led_offset = (start_of_arc_offset + i) % num_leds
                pixel_index = start_index + led_offset
                if 0 <= pixel_index < LED_COUNT:
                    self.pixels[pixel_index] = static_color
        
        self.pixels.show()

    def idle_effect(self):
        if not self.pixels or self.game_state.goal_animation_active or self.game_state.game_active:
            return
        
        brightness_multiplier = 0.75 + (math.sin(self.game_state.idle_animation_step * (2 * math.pi / FPS)) * 0.25)
        max_idle_brightness = 80 
        color_val = int(max_idle_brightness * brightness_multiplier)
        idle_color = (color_val, color_val, color_val)
        start_led, end_led = 0, 8
        self.pixels.fill((0, 0, 0))
        for i in range(start_led, end_led):
            self.pixels[i] = idle_color
        self.pixels.show()
        self.game_state.idle_animation_step = (self.game_state.idle_animation_step + 1) % FPS

    def game_active_effect(self):
        if not self.pixels: return
        active_color = (100, 100, 100)
        self.pixels.fill(active_color)
        self.pixels.show()

    def load_sounds(self):
        try: self.goal_horn_sound = pygame.mixer.Sound("goal_horn.wav"); self.all_sounds.append(self.goal_horn_sound)
        except pygame.error: self.goal_horn_sound = None
        try: self.shot_sound = pygame.mixer.Sound("shot.wav"); self.all_sounds.append(self.shot_sound)
        except pygame.error: self.shot_sound = None
        try: self.faceoff_sound = pygame.mixer.Sound("faceoff.wav"); self.all_sounds.append(self.faceoff_sound)
        except pygame.error: self.faceoff_sound = None
        try: self.buzzer_sound = pygame.mixer.Sound("buzzer.wav"); self.all_sounds.append(self.buzzer_sound)
        except pygame.error: self.buzzer_sound = None

    def setup_gpio(self):
        try:
            self.usa_goal_button = Button(USA_GOAL_PIN, pull_up=True, bounce_time=0.05)
            self.ussr_goal_button = Button(USSR_GOAL_PIN, pull_up=True, bounce_time=0.05)
            self.usa_sog_button = Button(USA_SOG_PIN, pull_up=True, bounce_time=0.05)
            self.ussr_sog_button = Button(USSR_SOG_PIN, pull_up=True, bounce_time=0.05)
            self.faceoff_button_1 = Button(FACEOFF_PIN_1, pull_up=True, bounce_time=0.05)
            self.faceoff_button_2 = Button(FACEOFF_PIN_2, pull_up=True, bounce_time=0.05)
            self.usa_goal_button.when_pressed = self.handle_usa_goal
            self.ussr_goal_button.when_pressed = self.handle_ussr_goal
            self.usa_sog_button.when_pressed = self.handle_usa_sog
            self.ussr_sog_button.when_pressed = self.handle_ussr_sog
            self.faceoff_button_1.when_pressed = self.handle_faceoff
            self.faceoff_button_2.when_pressed = self.handle_faceoff
            self.motor = OutputDevice(MOTOR_PIN, initial_value=False)
            self.volume_encoder = RotaryEncoder(VOLUME_CLK_PIN, VOLUME_DT_PIN, bounce_time=0.1)
            self.volume_encoder.when_rotated_clockwise = self.increase_volume
            self.volume_encoder.when_rotated_counter_clockwise = self.decrease_volume
            self.volume_button = Button(VOLUME_SW_PIN, pull_up=True, bounce_time=0.1)
            self.volume_button.when_pressed = self.handle_volume_button_press
            print("GPIO pins and Rotary Encoder initialized successfully.")
        except Exception as e:
            print(f"Could not initialize GPIO pins/Encoder: {e}"); print("Running in keyboard-only mode.")

    def create_firework_burst(self, color):
        burst_x = random.randint(200, SCREEN_WIDTH - 200)
        burst_y = random.randint(100, SCREEN_HEIGHT - 200)
        for _ in range(50):
            self.game_state.particles.append(Particle(burst_x, burst_y, color))

    def handle_usa_goal(self):
        if not self.game_state.game_over:
            if self.pixels: self.pixels.brightness = 1.0
            self.game_state.goal_animation_active = True
            self.game_state.goal_animation_timer = 5 * FPS
            self.game_state.goal_animation_color = (0, 0, 255)
            if self.goal_horn_sound: self.goal_horn_sound.play()
            if self.game_state.overtime_active:
                self.game_state.game_over = True; self.game_state.goal_celebration_timer = 5 * FPS
            self.game_state.usa_score += 1
            if self.game_state.recent_sog_timer <= 0: self.game_state.usa_sog += 1
            self.game_state.game_active = False
            self.game_state.goal_celebration_team = "USA"

    def handle_ussr_goal(self):
        if not self.game_state.game_over:
            if self.pixels: self.pixels.brightness = 1.0
            self.game_state.goal_animation_active = True
            self.game_state.goal_animation_timer = 5 * FPS
            self.game_state.goal_animation_color = (255, 0, 0)
            if self.goal_horn_sound: self.goal_horn_sound.play()
            if self.game_state.overtime_active:
                self.game_state.game_over = True; self.game_state.goal_celebration_timer = 5 * FPS
            self.game_state.ussr_score += 1
            if self.game_state.recent_sog_timer <= 0: self.game_state.ussr_sog += 1
            self.game_state.game_active = False
            self.game_state.goal_celebration_team = "USSR"

    def handle_usa_sog(self):
        if not self.game_state.game_over:
            if self.shot_sound: self.shot_sound.play()
            self.game_state.usa_sog += 1
            self.game_state.recent_sog_timer = 60

    def handle_ussr_sog(self):
        if not self.game_state.game_over:
            if self.shot_sound: self.shot_sound.play()
            self.game_state.ussr_sog += 1
            self.game_state.recent_sog_timer = 60

    def handle_faceoff(self):
        if not self.game_state.game_over:
            self.clear_leds()
            if self.faceoff_sound: self.faceoff_sound.play()
            if self.motor:
                self.motor.on(); time.sleep(MOTOR_RUN_TIME); self.motor.off()
            if not self.game_state.game_active: self.game_state.game_active = True
            self.game_state.goal_celebration_team = None

    def run(self):
        running = True
        try:
            while running:
                dt = self.clock.tick(FPS)
                running = self.handle_keyboard_input()
                self.game_state.update_clock(dt)
                self.check_period_end()
                self.update_intermission()
                self.update_goal_celebration_timer()
                self.update_sog_timer()
                self.update_goal_celebration_effects()
                
                if self.game_state.goal_animation_active:
                    self.update_goal_animation()
                elif self.game_state.game_over: self.clear_leds()
                elif self.game_state.game_active or self.game_state.overtime_active: self.game_active_effect()
                else: self.idle_effect()

                self.draw()
        finally:
            self.clear_leds()
            pygame.quit()
            sys.exit()

    def update_sog_timer(self):
        if self.game_state.recent_sog_timer > 0: self.game_state.recent_sog_timer -= 1

    def update_goal_celebration_effects(self):
        self.game_state.particles = [p for p in self.game_state.particles if p.lifetime > 0]
        for particle in self.game_state.particles:
            particle.update()
            
        if self.game_state.goal_celebration_team and random.randint(0, 20) == 0:
            color = COLOR_BLUE if self.game_state.goal_celebration_team == "USA" else COLOR_RED
            self.create_firework_burst(color)

    def draw_digital_text(self, text, font, color, center_pos):
        dark_color = tuple(c * 0.15 for c in color)
        placeholder = "8" * len(text)
        if ":" in text: placeholder = "88:88"
        text_surface_dark = font.render(placeholder, True, dark_color)
        text_rect_dark = text_surface_dark.get_rect(center=center_pos)
        self.screen.blit(text_surface_dark, text_rect_dark)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=center_pos)
        self.screen.blit(text_surface, text_rect)

    def draw_scoreboard(self):
        self.screen.fill(COLOR_BLACK)
        self.draw_digital_text("USSR", self.medium_font, COLOR_RED, (SCREEN_WIDTH * 0.25, 189))
        self.draw_digital_text("USA", self.medium_font, COLOR_BLUE, (SCREEN_WIDTH * 0.75, 189))
        self.draw_digital_text(f"{self.game_state.ussr_score:02}", self.large_font, COLOR_YELLOW, (SCREEN_WIDTH * 0.25, 486))
        self.draw_digital_text(f"{self.game_state.usa_score:02}", self.large_font, COLOR_YELLOW, (SCREEN_WIDTH * 0.75, 486))
        if self.game_state.game_over: period_label = "FINAL"; font = self.small_font
        elif self.game_state.overtime_active: period_label = "SUDDEN DEATH"; font = self.sudden_death_font
        else: period_label = "PERIOD"; font = self.small_font
        self.draw_digital_text(period_label, font, COLOR_WHITE, (SCREEN_WIDTH / 2, 135))
        if not self.game_state.game_over:
            if self.game_state.overtime_active: self.draw_digital_text("OT", self.medium_font, COLOR_RED, (SCREEN_WIDTH / 2, 297))
            else: self.draw_digital_text(str(self.game_state.period), self.medium_font, COLOR_RED, (SCREEN_WIDTH / 2, 297))
        if not self.game_state.overtime_active:
            minutes, seconds = divmod(int(self.game_state.game_clock / 1000), 60)
            self.draw_digital_text(f"{minutes:02}:{seconds:02}", self.medium_font, COLOR_RED, (SCREEN_WIDTH / 2, 540))
        self.draw_digital_text(f"SPEED x{self.game_state.time_multiplier:.1f}", self.tiny_font, COLOR_WHITE, (SCREEN_WIDTH * 0.35, 675))
        if self.game_state.is_muted: volume_text = "VOL MUTE"
        else: volume_text = f"VOL {int(self.game_state.volume * 100)}%"
        self.draw_digital_text(volume_text, self.tiny_font, COLOR_WHITE, (SCREEN_WIDTH * 0.65, 675))
        self.draw_digital_text("SHOTS ON GOAL", self.small_font, COLOR_WHITE, (SCREEN_WIDTH / 2, 810))
        self.draw_digital_text(f"{self.game_state.ussr_sog:02}", self.medium_font, COLOR_WHITE, (SCREEN_WIDTH * 0.25, 945))
        self.draw_digital_text(f"{self.game_state.usa_sog:02}", self.medium_font, COLOR_WHITE, (SCREEN_WIDTH * 0.75, 945))

    def draw_goal_celebration(self):
        self.screen.fill(COLOR_BLACK)

        for particle in self.game_state.particles:
            particle.draw(self.screen)
        
        team_name = self.game_state.goal_celebration_team
        team_color = COLOR_BLUE if team_name == "USA" else COLOR_RED
        text_surface = self.goal_font.render(f"GOAL {team_name}", True, team_color)
        self.screen.blit(text_surface, text_surface.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)))

    def draw_intermission_screen(self):
        self.screen.fill(COLOR_BLACK)
        if self.game_state.overtime_active: main_text, font = "SUDDEN DEATH!", self.medium_font
        else: main_text, font = f"PERIOD {self.game_state.period + 1}", self.large_font
        self.draw_digital_text(main_text, font, COLOR_WHITE, (SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.4))
        self.draw_digital_text("GET READY", self.medium_font, COLOR_RED, (SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.6))

    def draw(self):
        if self.game_state.intermission_active: self.draw_intermission_screen()
        elif self.game_state.goal_celebration_team: self.draw_goal_celebration()
        else: self.draw_scoreboard()
        pygame.display.flip()

    def handle_keyboard_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: return False
                if not self.game_state.game_over:
                    if event.key == pygame.K_u: self.handle_usa_goal()
                    if event.key == pygame.K_i: self.handle_ussr_goal()
                    if event.key == pygame.K_j: self.handle_usa_sog()
                    if event.key == pygame.K_k: self.handle_ussr_sog()
                    if event.key == pygame.K_f: self.handle_faceoff()
                if event.key == pygame.K_PERIOD: self.game_state.time_multiplier = min(20.0, self.game_state.time_multiplier + 0.5)
                if event.key == pygame.K_COMMA: self.game_state.time_multiplier = max(0.5, self.game_state.time_multiplier - 0.5)
                if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS: self.increase_volume()
                if event.key == pygame.K_MINUS: self.decrease_volume()
                if event.key == pygame.K_m: self.toggle_mute()
                if event.key == pygame.K_r: self.game_state.reset(); self.set_master_volume(self.game_state.volume); self.clear_leds()
        return True

    def check_period_end(self):
        if self.game_state.game_clock > 0 or self.game_state.game_over or self.game_state.intermission_active or self.game_state.overtime_active: return
        if self.buzzer_sound: self.buzzer_sound.play()
        self.game_state.game_active = False
        if self.game_state.period < 3:
            self.game_state.intermission_active = True; self.game_state.intermission_timer = 3 * FPS
        elif self.game_state.period == 3:
            if self.game_state.ussr_score == self.game_state.usa_score:
                self.game_state.overtime_active = True; self.game_state.intermission_active = True; self.game_state.intermission_timer = 3 * FPS
            else: 
                self.game_state.game_over = True
                self.clear_leds()

    def update_intermission(self):
        if not self.game_state.intermission_active: return
        self.game_state.intermission_timer -= 1
        if self.game_state.intermission_timer <= 0:
            self.game_state.intermission_active = False; self.clear_leds()
            if self.game_state.overtime_active: print("Sudden Death Overtime! Next goal wins.")
            else:
                self.game_state.period += 1; self.game_state.game_clock = 20 * 60 * 1000; self.game_state.game_active = True
                print(f"Period {self.game_state.period} starting automatically!")

    def update_goal_celebration_timer(self):
        if self.game_state.goal_celebration_timer > 0:
            self.game_state.goal_celebration_timer -= 1
            if self.game_state.goal_celebration_timer <= 0: 
                self.game_state.goal_celebration_team = None
                self.game_state.particles = []
                self.clear_leds()

if __name__ == '__main__':
    scoreboard = Scoreboard()
    scoreboard.run()

