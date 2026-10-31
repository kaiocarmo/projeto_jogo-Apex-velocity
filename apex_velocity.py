"""Apex Velocity 3.0 — Motorsport (Oficina, Carros e Motos)

Jogo de corrida arcade em Python/Tkinter, sem dependências externas.

Controles:
  W / seta para cima: acelerar
  S / seta para baixo: frear
  A / D ou setas esquerda/direita: esterçar
  Espaço: freio de mão
  N + W ou SHIFT + W: nitro (Neymar 10 e Conguitos XL)
  ESC: pausar / continuar
  M: voltar ao menu quando pausado

Na garagem, escolha Carros/Motos, personalize aparência e desempenho, circuito e dificuldade.
Execute com: python apex_velocity.py
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Dict, List, Tuple

WIDTH, HEIGHT = 1280, 800
SEGMENTS = 240
SEGMENT_LENGTH = 20.0
TRACK_LENGTH = SEGMENTS * SEGMENT_LENGTH
LAPS = 3
DRAW_DISTANCE = 150


@dataclass(frozen=True)
class Car:
    name: str
    description: str
    color: str
    max_speed: float
    acceleration: float
    handling: float
    has_nitro: bool = False
    normal_speed: float | None = None
    nitro_seconds: float = 0.0
    nitro_acceleration: float = 620.0
    vehicle_type: str = "car"


CARS = [
    Car("NOVA GT", "Esportivo equilibrado · Tração traseira", "#16b9e5", 290, 85, 82),
    Car("VORTEX R", "Superesportivo leve · Resposta agressiva", "#ff5b42", 315, 94, 76),
    Car("FALCON X", "Cupê de pista · Estabilidade nas curvas", "#a58cff", 282, 80, 94),
    Car("NEYMAR 10", "Edição Brasil · Nitro até 1.000 km/h", "#078b45", 1000, 145, 86, True, 430, 5.0, 620.0),
    Car("CONGUITOS XL", "SUV gigante · Nitro até 10.000 km/h", "#542b1b", 10000, 520, 72, True, 4300, 8.0, 6200.0),
]

# Cada perfil descreve a direção da pista em 12 pontos ao longo de uma volta.
# Valores positivos e negativos criam curvas longas para os dois lados.
TRACKS = [
    {
        "name": "COSTA AZUL GP", "short": "COSTA", "kind": "coast",
        "subtitle": "Litoral · sol e mar", "sky": ["#4e9dd0", "#81bbd1", "#c9d9ce"],
        "ground": "#688b4e", "hill": "#47786d", "mountain": "#789ba0", "road": "#303940",
        "accent": "#45d7ed", "curve_scale": 1.0,
        "profile": [0.0, 0.25, 0.85, 0.95, 0.3, -0.55, -1.0, -0.55, 0.25, 0.8, 0.45, 0.0, 0.0],
    },
    {
        "name": "SERRA NEVADA", "short": "NEVADA", "kind": "snow",
        "subtitle": "Montanhas · clima gelado", "sky": ["#557b9b", "#9ebccc", "#e1e6e4"],
        "ground": "#b7c8c8", "hill": "#809ca5", "mountain": "#e2eceb", "road": "#303b47",
        "accent": "#b9e9ff", "curve_scale": 1.25,
        "profile": [0.0, -0.55, -1.0, -0.65, 0.2, 0.9, 1.0, 0.35, -0.65, -0.95, -0.25, 0.4, 0.0],
    },
    {
        "name": "NEON CITY GP", "short": "NEON", "kind": "city",
        "subtitle": "Metrópole · corrida noturna", "sky": ["#090d27", "#171d43", "#34254f"],
        "ground": "#20283b", "hill": "#252747", "mountain": "#303454", "road": "#252a34",
        "accent": "#ff4fd8", "curve_scale": 1.15,
        "profile": [0.0, 0.7, 1.0, 0.35, -0.55, -0.9, -0.25, 0.7, 1.0, 0.35, -0.6, -0.25, 0.0],
    },
    {
        "name": "DESERTO CANYON", "short": "DESERTO", "kind": "desert",
        "subtitle": "Cânions · calor e areia", "sky": ["#bd7650", "#e3a36d", "#f1d2a0"],
        "ground": "#c29157", "hill": "#a96843", "mountain": "#b77e5d", "road": "#393536",
        "accent": "#ffc16b", "curve_scale": 1.35,
        "profile": [0.0, 0.6, 1.0, 0.75, -0.2, -0.95, -1.0, -0.2, 0.75, 1.0, 0.2, -0.5, 0.0],
    },
    {
        "name": "FLORESTA TROPICAL", "short": "FLORE", "kind": "forest",
        "subtitle": "Mata fechada · curvas técnicas", "sky": ["#477e83", "#80a99a", "#bed0ab"],
        "ground": "#315d3d", "hill": "#28523e", "mountain": "#527a69", "road": "#303a39",
        "accent": "#9dea88", "curve_scale": 1.3,
        "profile": [0.0, -0.7, -0.25, 0.85, 1.0, 0.2, -0.85, -1.0, -0.2, 0.8, 0.55, -0.35, 0.0],
    },
]

DIFFICULTIES = [
    {"name": "FÁCIL", "short": "FÁCIL", "speed": 0.82, "aggression": 0.35, "description": "Adversários mais lentos"},
    {"name": "NORMAL", "short": "NORMAL", "speed": 0.96, "aggression": 0.60, "description": "Desafio equilibrado"},
    {"name": "DIFÍCIL", "short": "DIFÍCIL", "speed": 1.08, "aggression": 0.82, "description": "Rivais rápidos e competitivos"},
    {"name": "PRO", "short": "PRO", "speed": 1.20, "aggression": 1.0, "description": "Adversários muito rápidos"},
]

OPPONENT_COLORS = ["#e74c3c", "#f0b33e", "#f1f4f7", "#55c78b", "#ba8cff", "#40a4ff", "#ff7ab5"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    rest = seconds % 60
    return f"{minutes:02d}:{rest:05.2f}"


def ordinal(number: int) -> str:
    return f"{number}º"


class ApexVelocity:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Apex Velocity — Motorsport")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.minsize(960, 650)
        self.root.configure(bg="#06101d")
        self.canvas = tk.Canvas(self.root, bg="#06101d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # Garante que Tk calcule o tamanho real do Canvas antes do primeiro desenho.
        self.root.update_idletasks()

        self.keys: Dict[str, bool] = {}
        self.selected_car = 0
        self.selected_track = 0
        self.selected_difficulty = 1
        self.state = "menu"
        self.last_tick = time.perf_counter()
        self.elapsed = 0.0
        self.player_distance = 0.0
        self.player_x = 0.0
        self.speed = 0.0
        self.steering = 0.0
        self.shake = 0.0
        self.nitro_remaining = 0.0
        self.nitro_active = False
        self.impact_flash = 0.0
        self.impact_message = ""
        self.opponents: List[dict] = []
        self.finish_position = 1
        self.menu_buttons: List[tuple] = []
        self.road_centers: List[float] = [0.0] * (DRAW_DISTANCE + 2)
        self.road_widths: List[float] = [0.0] * (DRAW_DISTANCE + 2)
        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.draw_menu()
        self.tick()

    def size(self) -> tuple[int, int]:
        return max(960, self.canvas.winfo_width()), max(650, self.canvas.winfo_height())

    def on_key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys[key] = True
        if key == "escape":
            if self.state == "race":
                self.state = "paused"
                self.draw_pause()
            elif self.state == "paused":
                self.state = "race"
                self.last_tick = time.perf_counter()
        elif self.state == "paused" and key == "m":
            self.draw_menu()
        elif self.state == "menu" and key in ("1", "2", "3", "4", "5"):
            self.select_car(int(key) - 1)

    def on_key_up(self, event: tk.Event) -> None:
        self.keys[event.keysym.lower()] = False

    def on_focus_out(self, _event: tk.Event) -> None:
        self.keys.clear()
        if self.state == "race":
            self.state = "paused"
            self.draw_pause()

    def on_click(self, event: tk.Event) -> None:
        for bounds, action in self.menu_buttons:
            x1, y1, x2, y2 = bounds
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                action()
                return

    def select_car(self, index: int) -> None:
        self.selected_car = int(clamp(index, 0, len(CARS) - 1))
        self.draw_menu()

    def select_track(self, index: int) -> None:
        self.selected_track = int(clamp(index, 0, len(TRACKS) - 1))
        self.draw_menu()

    def select_difficulty(self, index: int) -> None:
        self.selected_difficulty = int(clamp(index, 0, len(DIFFICULTIES) - 1))
        self.draw_menu()

    def text(self, x: float, y: float, value: str, size: int = 16,
             color: str = "#f3f7ff", weight: str = "normal", anchor: str = "center",
             font: str = "Segoe UI") -> None:
        self.canvas.create_text(x, y, text=value, fill=color,
                                font=(font, size, weight), anchor=anchor)

    def rounded_panel(self, x1: int, y1: int, x2: int, y2: int,
                      fill: str = "#0b1929", outline: str = "#26394d") -> None:
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=1)

    def button(self, x1: int, y1: int, x2: int, y2: int, label: str,
               action, primary: bool = False, accent: str | None = None) -> None:
        fill = accent or ("#52dafa" if primary else "#172b40")
        outline = "#d8f8ff" if primary else (accent or "#39536c")
        text_color = "#061522" if primary else "#e7f3ff"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)
        self.text((x1 + x2) / 2, (y1 + y2) / 2, label, 10, text_color, "bold")
        self.menu_buttons.append(((x1, y1, x2, y2), action))

    def draw_menu(self) -> None:
        self.state = "menu"
        self.menu_buttons = []
        self.canvas.delete("all")
        w, h = self.size()
        self.draw_background(w, h, menu=True)
        self.canvas.create_rectangle(0, 0, w, h, fill="#04101c", stipple="gray50", outline="")
        self.rounded_panel(35, 35, w - 35, h - 35, "#081827", "#28445a")
        self.text(76, 83, "APEX VELOCITY  ·  MOTORSPORT", 13, "#52e5ff", "bold", "w")
        self.text(72, 150, "FEEL THE", 47, "#f4f8ff", "bold", "w")
        self.text(68, 207, "RACING.", 57, "#52e5ff", "bold", "w")
        self.text(76, 270, "Cinco circuitos, curvas de verdade e", 15, "#c1d0df", anchor="w")
        self.text(76, 295, "adversários com quatro níveis de IA.", 15, "#c1d0df", anchor="w")
        self.text(76, 365, "8 PILOTOS   ·   3 VOLTAS   ·   COLISÕES", 11, "#9fb4c8", "bold", "w")

        selected = CARS[self.selected_car]
        preview_w, preview_h = (230, 207) if selected.name == "CONGUITOS XL" else (172, 155)
        self.draw_car(w * 0.32, h * 0.68, preview_w, preview_h, selected.color,
                      True, selected.name == "NEYMAR 10", False, selected.name == "CONGUITOS XL")
        self.text(w * 0.32, h * 0.78, TRACKS[self.selected_track]["name"], 12,
                  "#d2e1ef", "bold")
        self.text(76, h - 110, "A / D ou ← / →  esterçam", 11, "#b5c8d9", anchor="w")
        self.text(76, h - 86, "W acelera  ·  S freia  ·  ESPAÇO freio de mão", 11, "#b5c8d9", anchor="w")
        self.text(76, h - 62, "N + W ativa o nitro dos carros especiais", 11, "#f3d77a", "bold", "w")
        self.text(76, h - 31, "Projeto independente em Python + Tkinter", 9, "#8399ae", anchor="w")

        px = int(w * 0.56)
        self.rounded_panel(px, 62, w - 62, h - 62, "#0b1b2b", "#29465e")
        self.text(px + 25, 88, "SELECIONE SEU VEÍCULO", 11, "#a9bfd2", "bold", "w")
        self.text(px + 25, 126, selected.name, 25, "#ffffff", "bold", "w")
        self.text(px + 25, 151, selected.description, 10, "#9db2c6", anchor="w")

        bx = px + 25
        right = w - 87
        gap = 5
        bw = (right - bx - gap * 4) / 5
        car_short = ["NOVA", "VORTEX", "FALCON", "NEYMAR", "CONGUI"]
        for i, label in enumerate(car_short):
            x1, x2 = int(bx + i * (bw + gap)), int(bx + i * (bw + gap) + bw)
            active = i == self.selected_car
            accent = "#624126" if i == 4 and active else ("#164052" if active else "#142638")
            self.button(x1, 174, x2, 207, label, lambda n=i: self.select_car(n), False,
                        "#624126" if i == 4 and active else ("#164052" if active else "#142638"))
            if active:
                self.canvas.create_rectangle(x1, 174, x2, 207, outline="#e7bd50" if i == 4 else "#52e5ff", width=2)

        max_text = f"{int(selected.max_speed):,}".replace(",", ".")
        self.draw_stat(px + 25, 231, "VELOCIDADE MÁXIMA", f"{max_text} km/h", selected.max_speed / 10000 if selected.name == "CONGUITOS XL" else selected.max_speed / 1000 if selected.has_nitro else selected.max_speed / 330)
        self.draw_stat(px + 25, 270, "ACELERAÇÃO", f"{selected.acceleration} / 100", selected.acceleration / 520)
        self.draw_stat(px + 25, 309, "DIRIGIBILIDADE", f"{selected.handling} / 100", selected.handling / 100)
        if selected.has_nitro:
            self.text(px + 25, 348, f"NITRO: {selected.nitro_seconds:.0f}s  ·  N + W", 9, "#ffd85a", "bold", "w")
        else:
            self.text(px + 25, 348, "VEÍCULO DE PISTA  ·  SEM NITRO", 9, "#a9bfd2", "bold", "w")

        self.text(px + 25, 378, "ESCOLHA O CIRCUITO", 10, "#a9bfd2", "bold", "w")
        map_gap = 5
        map_bw = (right - bx - map_gap * 4) / 5
        for i, track in enumerate(TRACKS):
            x1, x2 = int(bx + i * (map_bw + map_gap)), int(bx + i * (map_bw + map_gap) + map_bw)
            active = i == self.selected_track
            self.button(x1, 392, x2, 426, track["short"], lambda n=i: self.select_track(n), False,
                        "#164052" if active else "#142638")
            if active:
                self.canvas.create_rectangle(x1, 392, x2, 426, outline=track["accent"], width=2)

        self.text(px + 25, 451, "DIFICULDADE", 10, "#a9bfd2", "bold", "w")
        diff_gap = 6
        diff_bw = (right - bx - diff_gap * 3) / 4
        for i, item in enumerate(DIFFICULTIES):
            x1, x2 = int(bx + i * (diff_bw + diff_gap)), int(bx + i * (diff_bw + diff_gap) + diff_bw)
            active = i == self.selected_difficulty
            self.button(x1, 465, x2, 499, item["short"], lambda n=i: self.select_difficulty(n), False,
                        "#31533f" if active else "#142638")
            if active:
                self.canvas.create_rectangle(x1, 465, x2, 499, outline="#89e2a2", width=2)
        self.text(px + 25, 516, DIFFICULTIES[self.selected_difficulty]["description"], 9,
                  "#a9c9b1", anchor="w")
        self.button(px + 25, 535, right, 582, "INICIAR CORRIDA  →", self.start_race, True)
        if h >= 720:
            self.text(px + 25, 615, "W/↑ acelerar · S/↓ frear · A/D esterçar · ESC pausar", 9,
                      "#c0cedc", anchor="w")
            self.text(px + 25, 638, "Colisões físicas entre carros e saída de pista", 9,
                      "#91a9bf", anchor="w")

    def draw_stat(self, x: int, y: int, label: str, value: str, fraction: float) -> None:
        width = max(220, int(self.size()[0] - x - 87))
        self.text(x, y, label, 9, "#9fb2c5", "bold", "w")
        self.text(x + width, y, value, 10, "#f0f6fc", "bold", "e")
        self.canvas.create_rectangle(x, y + 14, x + width, y + 19, fill="#203348", outline="")
        self.canvas.create_rectangle(x, y + 14, x + width * clamp(fraction, 0, 1), y + 19,
                                     fill="#35c9ee", outline="")

    def start_race(self) -> None:
        self.menu_buttons = []
        self.elapsed = self.player_distance = self.player_x = self.speed = self.steering = self.shake = 0.0
        self.nitro_remaining = CARS[self.selected_car].nitro_seconds
        self.nitro_active = False
        self.impact_flash = 0.0
        self.impact_message = ""
        self.opponents = []
        car = CARS[self.selected_car]
        difficulty = DIFFICULTIES[self.selected_difficulty]
        base_speed = car.normal_speed if car.has_nitro else car.max_speed
        ai_base = clamp(base_speed * 0.72, 175, 315)
        for i in range(7):
            self.opponents.append({
                "distance": 55 + i * 65 + random.uniform(-8, 8),
                "lane": (-0.48 if i % 2 == 0 else 0.48) + random.uniform(-0.04, 0.04),
                "speed": ai_base * difficulty["speed"] * random.uniform(0.93, 1.045),
                "color": OPPONENT_COLORS[i],
                "collision_cd": random.uniform(0.0, 0.25),
                "id": i,
                "flash": 0.0,
            })
        self.state = "race"
        self.last_tick = time.perf_counter()
        self.draw_race()

    def finish_race(self) -> None:
        self.player_distance = TRACK_LENGTH * LAPS
        self.finish_position = 1 + sum(o["distance"] > self.player_distance for o in self.opponents)
        self.state = "finished"
        self.draw_finish()

    def curve_at(self, index: int) -> float:
        profile = TRACKS[self.selected_track]["profile"]
        p = (index % SEGMENTS) / SEGMENTS * (len(profile) - 1)
        lo = int(p)
        hi = (lo + 1) % len(profile)
        f = p - lo
        smooth = (1.0 - math.cos(f * math.pi)) * 0.5
        val = profile[lo] * (1 - smooth) + profile[hi] * smooth
        return val * 0.012 * TRACKS[self.selected_track]["curve_scale"]

    def update(self, dt: float) -> None:
        if self.state != "race":
            return
        self.elapsed += dt
        car = CARS[self.selected_car]
        difficulty = DIFFICULTIES[self.selected_difficulty]
        throttle = self.keys.get("w", False) or self.keys.get("up", False)
        brake = self.keys.get("s", False) or self.keys.get("down", False)
        left = self.keys.get("a", False) or self.keys.get("left", False)
        right = self.keys.get("d", False) or self.keys.get("right", False)
        handbrake = self.keys.get("space", False)
        nitro_key = self.keys.get("n", False) or self.keys.get("shift_l", False) or self.keys.get("shift_r", False)
        self.nitro_active = bool(car.has_nitro and nitro_key and throttle and self.nitro_remaining > 0)

        if self.nitro_active:
            self.nitro_remaining = max(0.0, self.nitro_remaining - dt)
            self.speed += car.nitro_acceleration * dt
        elif car.has_nitro:
            normal_limit = car.normal_speed or 430
            if throttle and self.speed < normal_limit:
                self.speed += car.acceleration * 1.02 * dt
            elif self.speed > normal_limit:
                self.speed = max(normal_limit, self.speed - 115 * dt)
            else:
                self.speed = max(0.0, self.speed - 8.5 * dt)
        elif throttle:
            self.speed += car.acceleration * 1.02 * dt
        else:
            self.speed = max(0.0, self.speed - 8.5 * dt)
        if brake:
            self.speed -= 190 * dt
        if handbrake:
            self.speed -= 125 * dt
        speed_limit = car.max_speed if (not car.has_nitro or self.nitro_active) else (car.normal_speed or 430)
        self.speed = clamp(self.speed, 0, speed_limit)

        self.steering = float(right) - float(left)
        steer_rate = (1.30 + min(self.speed, 450) / 450 * 0.80) * (car.handling / 85)
        self.player_x += self.steering * steer_rate * dt
        current_curve = self.curve_at(int(self.player_distance / SEGMENT_LENGTH))
        # Pequeno efeito de transferência lateral em curvas rápidas.
        self.player_x -= current_curve * (min(self.speed, 500) / 250) * dt * 0.34
        if handbrake and self.speed > 30:
            self.player_x += self.steering * 0.16 * dt
        offroad = abs(self.player_x) > 0.92
        if offroad:
            self.speed = max(45, self.speed - (100 if self.selected_track == 1 else 78) * dt)
            self.shake = min(7, self.shake + dt * 22)
            if self.impact_flash <= 0:
                self.impact_message = "FORA DA PISTA!"
                self.impact_flash = 0.35
        else:
            self.shake = max(0, self.shake - dt * 14)
        self.player_x = clamp(self.player_x, -1.30, 1.30)

        self.player_distance += self.speed / 3.6 * dt
        for opponent in self.opponents:
            opponent["collision_cd"] = max(0.0, opponent["collision_cd"] - dt)
            opponent["flash"] = max(0.0, opponent["flash"] - dt)
            opponent["distance"] += opponent["speed"] / 3.6 * dt
            # IA varia de faixa e tenta evitar o jogador; no PRO, arrisca mais.
            relative = opponent["distance"] - self.player_distance
            sway = math.sin(self.elapsed * (0.65 + difficulty["aggression"] * 0.35) + opponent["id"] * 1.8) * 0.055
            target_lane = clamp(opponent["lane"] + sway * dt * 4.0, -0.62, 0.62)
            if abs(relative) < 58 and abs(opponent["lane"] - self.player_x) < 0.43:
                avoid_side = -1 if opponent["lane"] > self.player_x else 1
                target_lane = clamp(opponent["lane"] + avoid_side * (0.12 * (1.0 - difficulty["aggression"] * 0.6)), -0.62, 0.62)
            opponent["lane"] += (target_lane - opponent["lane"]) * min(1.0, dt * (0.9 + difficulty["aggression"]))

        # Colisão jogador x adversário: exige proximidade longitudinal e lateral.
        for opponent in self.opponents:
            gap = opponent["distance"] - self.player_distance
            lane_gap = opponent["lane"] - self.player_x
            if abs(gap) < 7.5 and abs(lane_gap) < 0.30 and opponent["collision_cd"] <= 0:
                side = -1.0 if lane_gap > 0 else 1.0
                if abs(lane_gap) < 0.035:
                    side = -1.0 if opponent["id"] % 2 == 0 else 1.0
                relative_impact = abs(self.speed - opponent["speed"]) / 260.0
                penalty = clamp(0.48 + relative_impact * 0.13, 0.48, 0.78)
                self.speed *= penalty
                self.player_x += side * 0.20
                opponent["lane"] = clamp(opponent["lane"] - side * 0.24, -0.68, 0.68)
                opponent["speed"] *= 0.84
                opponent["distance"] += -2.5 if gap > 0 else 2.5
                opponent["collision_cd"] = 0.85
                opponent["flash"] = 0.35
                self.shake = max(self.shake, 5.5)
                self.impact_flash = 0.55
                self.impact_message = "COLISÃO!"

        # Também há batidas entre os próprios rivais.
        for i in range(len(self.opponents)):
            a = self.opponents[i]
            for j in range(i + 1, len(self.opponents)):
                b = self.opponents[j]
                if abs(a["distance"] - b["distance"]) < 5.5 and abs(a["lane"] - b["lane"]) < 0.27:
                    if a["collision_cd"] <= 0 and b["collision_cd"] <= 0:
                        side = -1 if a["lane"] >= b["lane"] else 1
                        a["lane"] = clamp(a["lane"] + side * 0.15, -0.68, 0.68)
                        b["lane"] = clamp(b["lane"] - side * 0.15, -0.68, 0.68)
                        a["speed"] *= 0.93
                        b["speed"] *= 0.93
                        a["collision_cd"] = b["collision_cd"] = 0.7
                        a["flash"] = b["flash"] = 0.25

        self.impact_flash = max(0.0, self.impact_flash - dt)
        self.player_x = clamp(self.player_x, -1.30, 1.30)
        if self.player_distance >= TRACK_LENGTH * LAPS:
            self.finish_race()

    def tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.035, max(0.0, now - self.last_tick))
        self.last_tick = now
        if self.state == "race":
            self.update(dt)
            if self.state == "race":
                self.draw_race()
        self.root.after(16, self.tick)

    def draw_background(self, w: int, h: int, menu: bool = False) -> None:
        track = TRACKS[self.selected_track]
        sky = track["sky"]
        for i, color in enumerate(sky):
            y1 = int(h * 0.50 * i / len(sky))
            y2 = int(h * 0.50 * (i + 1) / len(sky)) + 1
            self.canvas.create_rectangle(0, y1, w, y2, fill=color, outline="")
        kind = track["kind"]
        if kind == "city":
            rng = random.Random(73)
            for n in range(52):
                x = n * w / 50 - 10
                bw = rng.randint(18, 50)
                bh = rng.randint(int(h * 0.10), int(h * 0.31))
                y = h * 0.49 - bh
                self.canvas.create_rectangle(x, y, x + bw, h * 0.52,
                                             fill=rng.choice(["#171b36", "#202342", "#292747", "#202b42"]), outline="")
                for wy in range(int(y + 8), int(h * 0.49), 13):
                    for wx in range(int(x + 5), int(x + bw - 4), 10):
                        if rng.random() > 0.38:
                            self.canvas.create_rectangle(wx, wy, wx + 3, wy + 5,
                                                         fill=rng.choice(["#ffcf69", "#65dff2", "#fb75d7"]), outline="")
            for n in range(45):
                x = (n * 173) % w
                y = (n * 47) % int(h * 0.38)
                self.canvas.create_oval(x, y, x + 2, y + 2, fill="#e3ddff", outline="")
        else:
            sun_color = "#fff0c4" if kind != "snow" else "#f4fbff"
            self.canvas.create_oval(w * 0.75, h * 0.08, w * 0.83, h * 0.21, fill=sun_color, outline="")
            mountain_points = [(0, h * 0.48)]
            for x in range(0, w + 41, 40):
                yy = h * (0.33 + 0.075 * math.sin(x * 0.008) + 0.035 * math.sin(x * 0.021 + 1.7))
                mountain_points.append((x, yy))
            mountain_points.extend([(w, h * 0.62), (0, h * 0.62)])
            self.poly(mountain_points, track["mountain"])
            hills = [(0, h * 0.54)]
            for x in range(0, w + 31, 30):
                yy = h * (0.43 + 0.05 * math.sin(x * 0.011 + 1) + 0.025 * math.sin(x * 0.027))
                hills.append((x, yy))
            hills.extend([(w, h * 0.68), (0, h * 0.68)])
            self.poly(hills, track["hill"])
            if kind == "coast":
                self.canvas.create_rectangle(0, h * 0.54, w, h * 0.63, fill="#367f9a", outline="")
                for k in range(10):
                    yy = h * (0.55 + k * 0.008)
                    self.canvas.create_line(0, yy, w, yy, fill="#76b9c5", width=1)
            if kind == "snow":
                for x in range(0, w, 150):
                    self.poly([(x, h * 0.43), (x + 65, h * 0.27), (x + 125, h * 0.43)], "#ecf4f5")
            if kind == "desert":
                for x in range(20, w, 180):
                    self.poly([(x, h * 0.57), (x + 40, h * 0.40), (x + 95, h * 0.57)], "#925b43")
            if kind == "forest":
                for x in range(0, w, 85):
                    self.poly([(x, h * 0.60), (x + 35, h * 0.34), (x + 70, h * 0.60)], "#1d4d3b")
        self.canvas.create_rectangle(0, h * 0.62, w, h, fill=track["ground"], outline="")
        if kind == "city":
            self.canvas.create_line(0, h * 0.63, w, h * 0.63, fill="#b33c9f", width=2)

    def poly(self, points: list[tuple[float, float]], color: str, outline: str = "") -> None:
        flat = [coord for point in points for coord in point]
        self.canvas.create_polygon(*flat, fill=color, outline=outline)

    def draw_tree(self, x: float, y: float, size: float, variant: int) -> None:
        kind = TRACKS[self.selected_track]["kind"]
        if kind == "desert":
            self.canvas.create_rectangle(x - size * 0.07, y - size, x + size * 0.07, y,
                                         fill="#39734d", outline="")
            self.canvas.create_arc(x - size * 0.35, y - size * 0.85, x + size * 0.02, y - size * 0.25,
                                  start=265, extent=180, style="arc", outline="#39734d", width=max(3, int(size * 0.11)))
            self.canvas.create_arc(x - size * 0.02, y - size * 0.72, x + size * 0.35, y - size * 0.15,
                                  start=85, extent=180, style="arc", outline="#39734d", width=max(3, int(size * 0.11)))
            return
        trunk_w, trunk_h = size * 0.13, size * 0.42
        self.canvas.create_rectangle(x - trunk_w / 2, y - trunk_h, x + trunk_w / 2, y,
                                     fill="#594333", outline="")
        if kind == "snow":
            greens = ["#1e3f48", "#315f69", "#e5f0ef"]
        elif kind == "city":
            greens = ["#252b48", "#36375e", "#53436e"]
        elif kind == "forest":
            greens = ["#103a2d", "#1c573d", "#34734b"]
        else:
            greens = ["#173f37", "#23624b", "#2d7653"]
        self.poly([(x, y - size * 1.7), (x - size * 0.58, y - size * 0.55),
                   (x + size * 0.58, y - size * 0.55)], greens[0])
        self.poly([(x, y - size * 1.42), (x - size * 0.49, y - size * 0.27),
                   (x + size * 0.49, y - size * 0.27)], greens[1])
        self.poly([(x, y - size * 1.12), (x - size * 0.39, y),
                   (x + size * 0.39, y)], greens[2])

    def draw_road(self) -> float:
        w, h = self.size()
        self.draw_background(w, h)
        horizon = h * 0.43
        curve_sum = 0.0
        base = int(self.player_distance / SEGMENT_LENGTH)
        # Centro da estrada muda progressivamente para formar curvas visíveis no horizonte.
        for i in range(DRAW_DISTANCE + 1):
            idx = (base + i) % SEGMENTS
            curve_sum += self.curve_at(idx) * 0.98
            t = i / DRAW_DISTANCE
            perspective = (1 - t) ** 1.55
            shift = curve_sum * w * 0.155 * (t ** 0.82)
            self.road_centers[i] = w * 0.5 - shift
            self.road_widths[i] = w * (0.065 + 0.385 * perspective)

        track = TRACKS[self.selected_track]
        for i in range(DRAW_DISTANCE - 1, -1, -1):
            t = i / DRAW_DISTANCE
            y_far = horizon + (h - horizon) * (1 - (i + 1) / DRAW_DISTANCE) ** 2.05
            y_near = horizon + (h - horizon) * (1 - i / DRAW_DISTANCE) ** 2.05
            c_far, c_near = self.road_centers[i + 1], self.road_centers[i]
            w_far, w_near = self.road_widths[i + 1], self.road_widths[i]
            seg = base + i
            band = (seg // 3) % 2
            side_color = track["ground"] if band else track["hill"]
            self.poly([(0, y_far), (w, y_far), (w, y_near), (0, y_near)], side_color)
            curb_far, curb_near = w_far * 0.095, w_near * 0.095
            curb_color = "#f4f1e7" if band else "#d84b42"
            self.poly([(c_far - w_far - curb_far, y_far), (c_far - w_far, y_far),
                       (c_near - w_near, y_near), (c_near - w_near - curb_near, y_near)], curb_color)
            self.poly([(c_far + w_far, y_far), (c_far + w_far + curb_far, y_far),
                       (c_near + w_near + curb_near, y_near), (c_near + w_near, y_near)], curb_color)
            asphalt = track["road"] if band else ("#2b3039" if track["kind"] == "city" else "#343b42")
            self.poly([(c_far - w_far, y_far), (c_far + w_far, y_far),
                       (c_near + w_near, y_near), (c_near - w_near, y_near)], asphalt)
            # Linhas laterais refletivas.
            edge_far, edge_near = max(1, w_far * 0.018), max(1, w_near * 0.018)
            self.poly([(c_far - w_far + edge_far, y_far), (c_far - w_far + edge_far * 2, y_far),
                       (c_near - w_near + edge_near * 2, y_near), (c_near - w_near + edge_near, y_near)], "#d9e0e1")
            self.poly([(c_far + w_far - edge_far * 2, y_far), (c_far + w_far - edge_far, y_far),
                       (c_near + w_near - edge_near, y_near), (c_near + w_near - edge_near * 2, y_near)], "#d9e0e1")
            # Tracejado central, que acentua a perspectiva e a leitura das curvas.
            if (seg // 7) % 2 == 0:
                mwf, mwn = max(1, w_far * 0.010), max(1, w_near * 0.010)
                self.poly([(c_far - mwf, y_far), (c_far + mwf, y_far),
                           (c_near + mwn, y_near), (c_near - mwn, y_near)], "#d2d7d9")
            # Placas, arquibancadas, árvores e postes nas laterais.
            if i % 7 == 0 and i > 2:
                tree_size = 10 + (1 - t) * 68
                rng = random.Random(seg * 19 + self.selected_track * 101)
                shift = (rng.random() - 0.5) * 0.12 * w
                if track["kind"] == "city":
                    for sign in (-1, 1):
                        bx = c_near + sign * (w_near + tree_size * 0.85 + abs(shift))
                        self.canvas.create_rectangle(bx - tree_size * 0.20, y_near - tree_size * 2.3,
                                                     bx + tree_size * 0.20, y_near,
                                                     fill="#343b55", outline="#6d6c95")
                        self.canvas.create_rectangle(bx - tree_size * 0.13, y_near - tree_size * 1.8,
                                                     bx + tree_size * 0.13, y_near - tree_size * 1.65,
                                                     fill=track["accent"], outline="")
                else:
                    self.draw_tree(c_near - w_near - tree_size * 0.55 - shift, y_near, tree_size, 0)
                    self.draw_tree(c_near + w_near + tree_size * 0.55 + shift, y_near, tree_size, 1)
            if i % 43 == 0 and t < 0.84:
                stand_w = 30 + (1 - t) * 145
                stand_h = 10 + (1 - t) * 32
                gx = c_near - w_near - stand_w * 0.7
                self.canvas.create_rectangle(gx, y_near - stand_h, gx + stand_w, y_near,
                                             fill="#65717a", outline="")
                for k in range(7):
                    colors = ["#e34e49", "#f5cf5a", "#edf0ed"]
                    self.canvas.create_rectangle(gx + stand_w * k / 7, y_near - stand_h * 0.8,
                                                 gx + stand_w * k / 7 + max(1, stand_w / 16),
                                                 y_near - stand_h * 0.32,
                                                 fill=colors[k % 3], outline="")
        # Linha de largada quadriculada sempre visível no início de cada volta.
        distance_into_lap = self.player_distance % TRACK_LENGTH
        if distance_into_lap < 115:
            y = h * 0.91
            center = self.road_centers[0]
            road_w = self.road_widths[0]
            tile = max(5, road_w * 0.055)
            for n in range(12):
                for side in range(2):
                    x1 = center - road_w * 0.90 + n * tile * 2 + side * tile
                    self.canvas.create_rectangle(x1, y, x1 + tile, y + 8,
                                                 fill="#f3f4f5" if (n + side) % 2 == 0 else "#20252b", outline="")
        return horizon

    def draw_car(self, x: float, y: float, width: float, height: float,
                 color: str, player: bool = False, neymar_livery: bool = False,
                 nitro: bool = False, conguitos_livery: bool = False,
                 hit: bool = False) -> None:
        c = self.canvas
        if nitro:
            self.poly([(x - width * 0.28, y + height * 0.10),
                       (x - width * 0.16, y + height * 0.58), (x, y + height * 0.22),
                       (x + width * 0.16, y + height * 0.58), (x + width * 0.28, y + height * 0.10)], "#28c9ff")
            self.poly([(x - width * 0.12, y + height * 0.13), (x, y + height * 0.48),
                       (x + width * 0.12, y + height * 0.13)], "#fff29a")
        if hit:
            c.create_oval(x - width * 0.62, y - height * 0.55, x + width * 0.62, y + height * 0.28,
                          outline="#fff29a", width=3)
        c.create_oval(x - width * 0.58, y + height * 0.02, x + width * 0.58,
                      y + height * 0.24, fill="#101820", outline="")
        # Pneus e para-choques com sombra.
        for side in (-1, 1):
            c.create_rectangle(x + side * width * 0.31 - width * 0.08, y - height * 0.12,
                               x + side * width * 0.31 + width * 0.08, y + height * 0.35,
                               fill="#101419", outline="#39434b")
            c.create_rectangle(x + side * width * 0.31 - width * 0.08, y - height * 0.66,
                               x + side * width * 0.31 + width * 0.08, y - height * 0.32,
                               fill="#101419", outline="#39434b")
        body = [(x - width * 0.4, y + height * 0.18), (x - width * 0.5, y - height * 0.08),
                (x - width * 0.43, y - height * 0.62), (x - width * 0.27, y - height * 0.88),
                (x + width * 0.27, y - height * 0.88), (x + width * 0.43, y - height * 0.62),
                (x + width * 0.5, y - height * 0.08), (x + width * 0.4, y + height * 0.18)]
        c.create_polygon(*[a for p in body for a in p], fill=color,
                          outline="#eafaff" if player else "#303a43", width=2 if player else 1)
        # Laterais iluminadas para dar volume.
        c.create_polygon(x - width * 0.43, y - height * 0.62, x - width * 0.27, y - height * 0.88,
                         x - width * 0.19, y - height * 0.32, x - width * 0.40, y + height * 0.12,
                         fill="#ffffff", stipple="gray75", outline="")
        c.create_polygon(x + width * 0.43, y - height * 0.62, x + width * 0.27, y - height * 0.88,
                         x + width * 0.19, y - height * 0.32, x + width * 0.40, y + height * 0.12,
                         fill="#000000", stipple="gray75", outline="")
        roof = [(x - width * 0.29, y - height * 0.56), (x - width * 0.2, y - height * 0.82),
                (x + width * 0.2, y - height * 0.82), (x + width * 0.29, y - height * 0.56),
                (x + width * 0.23, y - height * 0.34), (x - width * 0.23, y - height * 0.34)]
        c.create_polygon(*[a for p in roof for a in p], fill="#172c3b", outline="#101820")
        c.create_polygon(x - width * 0.21, y - height * 0.77, x + width * 0.21, y - height * 0.77,
                         x + width * 0.26, y - height * 0.57, x - width * 0.26, y - height * 0.57,
                         fill="#86bdd0", outline="")
        # Aerofólio e linhas de carroceria.
        c.create_rectangle(x - width * 0.42, y - height * 0.72, x + width * 0.42, y - height * 0.67,
                           fill="#161d25", outline="")
        if conguitos_livery:
            c.create_polygon(x - width * 0.39, y - height * 0.20, x - width * 0.31, y - height * 0.63,
                             x - width * 0.20, y - height * 0.35, x - width * 0.27, y + height * 0.11,
                             fill="#e9b83f", outline="#fff0b0", width=1)
            c.create_polygon(x + width * 0.39, y - height * 0.20, x + width * 0.31, y - height * 0.63,
                             x + width * 0.20, y - height * 0.35, x + width * 0.27, y + height * 0.11,
                             fill="#e9b83f", outline="#fff0b0", width=1)
            mascot_rx, mascot_ry = width * 0.145, height * 0.17
            mascot_y = y - height * 0.20
            c.create_oval(x - mascot_rx, mascot_y - mascot_ry, x + mascot_rx, mascot_y + mascot_ry,
                          fill="#7a3d20", outline="#f4d58a", width=max(1, int(width * 0.012)))
            c.create_oval(x - width * 0.075, mascot_y - height * 0.075, x - width * 0.025,
                          mascot_y - height * 0.015, fill="#fff8dc", outline="")
            c.create_oval(x + width * 0.025, mascot_y - height * 0.075, x + width * 0.075,
                          mascot_y - height * 0.015, fill="#fff8dc", outline="")
            c.create_oval(x - width * 0.055, mascot_y - height * 0.055, x - width * 0.035,
                          mascot_y - height * 0.025, fill="#17100c", outline="")
            c.create_oval(x + width * 0.045, mascot_y - height * 0.055, x + width * 0.065,
                          mascot_y - height * 0.025, fill="#17100c", outline="")
            c.create_arc(x - width * 0.065, mascot_y - height * 0.015, x + width * 0.065,
                         mascot_y + height * 0.09, start=205, extent=130, style="arc",
                         outline="#fff0d0", width=max(1, int(width * 0.014)))
            c.create_rectangle(x - width * 0.34, y + height * 0.025, x + width * 0.34,
                               y + height * 0.17, fill="#e8bd4e", outline="#fff0b0", width=1)
            c.create_text(x, y + height * 0.095, text="CONGUITOS", fill="#4b2416",
                          font=("Segoe UI", max(6, int(width * 0.075)), "bold"))
        if neymar_livery:
            c.create_polygon(x - width * 0.39, y - height * 0.18, x - width * 0.29, y - height * 0.59,
                             x - width * 0.19, y - height * 0.34, x - width * 0.27, y + height * 0.10,
                             fill="#f6d447", outline="")
            c.create_polygon(x + width * 0.39, y - height * 0.18, x + width * 0.29, y - height * 0.59,
                             x + width * 0.19, y - height * 0.34, x + width * 0.27, y + height * 0.10,
                             fill="#f6d447", outline="")
            c.create_oval(x - width * 0.105, y - height * 0.28, x + width * 0.105,
                          y - height * 0.07, fill="#f7f7ef", outline="#173e86", width=1)
            c.create_text(x, y - height * 0.17, text="10", fill="#173e86",
                          font=("Segoe UI", max(7, int(width * 0.10)), "bold"))
            c.create_text(x, y + height * 0.015, text="NEYMAR", fill="#fff4b2",
                          font=("Segoe UI", max(6, int(width * 0.065)), "bold"))
        c.create_rectangle(x - width * 0.035, y - height * 0.27, x + width * 0.035,
                           y + height * 0.09, fill="#8bd8ea", outline="")
        lamp = "#c5f8ff" if player else "#ffefc1"
        c.create_rectangle(x - width * 0.37, y - height * 0.08, x - width * 0.21,
                           y - height * 0.025, fill=lamp, outline="")
        c.create_rectangle(x + width * 0.21, y - height * 0.08, x + width * 0.37,
                           y - height * 0.025, fill=lamp, outline="")
        c.create_rectangle(x - width * 0.35, y + height * 0.05, x - width * 0.22,
                           y + height * 0.095, fill="#fa3c37", outline="")
        c.create_rectangle(x + width * 0.22, y + height * 0.05, x + width * 0.35,
                           y + height * 0.095, fill="#fa3c37", outline="")

    def draw_race(self) -> None:
        if self.state != "race":
            return
        self.canvas.delete("all")
        w, h = self.size()
        horizon = self.draw_road()
        visible = [o for o in self.opponents
                   if 6 < o["distance"] - self.player_distance < DRAW_DISTANCE * SEGMENT_LENGTH]
        visible.sort(key=lambda o: o["distance"], reverse=True)
        for opponent in visible:
            relative = opponent["distance"] - self.player_distance
            rel_seg = relative / SEGMENT_LENGTH
            index = min(DRAW_DISTANCE, max(0, int(rel_seg)))
            t = rel_seg / DRAW_DISTANCE
            y = horizon + (h - horizon) * (1 - t) ** 2.05
            road_width = self.road_widths[index] or w * 0.1
            x = self.road_centers[index] + opponent["lane"] * road_width * 0.68
            scale = (1 - t) ** 1.28
            car_w = max(9, w * 0.078 * scale)
            if y > horizon and y < h * 0.96:
                self.draw_car(x, y - car_w * 0.37, car_w, car_w * 0.77,
                              opponent["color"], hit=opponent["flash"] > 0)

        bottom_width = self.road_widths[0] or w * 0.45
        player_x = self.road_centers[0] + self.player_x * bottom_width * 0.72
        selected = CARS[self.selected_car]
        car_width = min(178, max(116, w * 0.135)) if selected.name == "CONGUITOS XL" else min(122, max(72, w * 0.088))
        self.draw_car(player_x + random.uniform(-self.shake, self.shake),
                      h * 0.89 + random.uniform(-self.shake, self.shake),
                      car_width, car_width * (1.08 if selected.name == "CONGUITOS XL" else 0.9),
                      selected.color, True, selected.name == "NEYMAR 10", self.nitro_active,
                      selected.name == "CONGUITOS XL")
        self.draw_hud(w, h)

    def draw_hud(self, w: int, h: int) -> None:
        car = CARS[self.selected_car]
        track = TRACKS[self.selected_track]
        lap = min(LAPS, int(self.player_distance / TRACK_LENGTH) + 1)
        position = 1 + sum(o["distance"] > self.player_distance for o in self.opponents)
        progress = min(1.0, self.player_distance / (TRACK_LENGTH * LAPS))
        gear = "N" if self.speed < 3 else str(min(7, max(1, int(self.speed / 42) + 1)))

        self.rounded_panel(16, 16, 288, 112, "#0a1828", "#36506a")
        self.text(32, 35, "CIRCUITO", 9, "#9ab0c9", "bold", "w")
        self.text(32, 60, track["name"], 17, "#ffffff", "bold", "w")
        self.text(32, 86, f"VOLTA {lap} / {LAPS}   ·   {DIFFICULTIES[self.selected_difficulty]['name']}", 10,
                  "#b9c8d9", anchor="w")
        self.rounded_panel(w - 194, 16, w - 16, 112, "#0a1828", "#36506a")
        self.text(w - 178, 35, "POSIÇÃO", 9, "#9ab0c9", "bold", "w")
        self.text(w - 178, 64, f"{ordinal(position)} / 8", 22, "#ffffff", "bold", "w")
        self.text(w - 178, 89, format_time(self.elapsed), 10, "#b9c8d9", anchor="w")

        self.rounded_panel(16, h - 150, 254, h - 16, "#0a1828", "#36506a")
        self.text(34, h - 128, "VELOCIDADE", 9, "#9ab0c9", "bold", "w")
        self.text(32, h - 83, f"{round(self.speed):,}".replace(",", "."), 42, "#ffffff", "bold", "w")
        self.text(157, h - 68, "KM/H", 10, "#9fb4ca", "bold", "w")
        self.canvas.create_rectangle(34, h - 51, 232, h - 44, fill="#273b51", outline="")
        self.canvas.create_rectangle(34, h - 51, 34 + 198 * self.speed / max(1, car.max_speed), h - 44,
                                     fill=track["accent"], outline="")
        self.text(34, h - 29, f"MARCHA {gear}   ·   {car.name}", 9, "#c0d1df", "bold", "w")

        if car.has_nitro:
            self.rounded_panel(268, h - 112, 496, h - 16, "#0a1828", "#8e742b")
            nitro_label = "NITRO ATIVO!" if self.nitro_active else "NITRO  ·  SEGURE N + W"
            self.text(286, h - 90, nitro_label, 9, "#ffe06b", "bold", "w")
            self.canvas.create_rectangle(286, h - 65, 478, h - 54, fill="#3b3520", outline="")
            fraction = self.nitro_remaining / max(0.01, car.nitro_seconds)
            self.canvas.create_rectangle(286, h - 65, 286 + 192 * fraction, h - 54, fill="#ffd84d", outline="")
            max_label = f"{int(car.max_speed):,}".replace(",", ".")
            self.text(286, h - 34, f"{self.nitro_remaining:.1f}s  ·  MÁX. {max_label} KM/H", 8,
                      "#fff0ba", "bold", "w")

        self.rounded_panel(w - 318, h - 112, w - 16, h - 16, "#0a1828", "#36506a")
        self.text(w - 300, h - 90, "PROGRESSO DA CORRIDA", 9, "#9ab0c9", "bold", "w")
        self.text(w - 300, h - 67, f"{int(progress * 100)}% concluído", 11, "#e3edf6", "bold", "w")
        self.canvas.create_rectangle(w - 300, h - 49, w - 34, h - 42, fill="#273b51", outline="")
        self.canvas.create_rectangle(w - 300, h - 49, w - 300 + 266 * progress, h - 42,
                                     fill=track["accent"], outline="")
        help_text = "W/↑ acelerar · S/↓ frear · A/D virar · ESPAÇO freio de mão · ESC pausar"
        if car.has_nitro:
            help_text += " · N + W nitro"
        self.text(w / 2, h - 18, help_text, 9, "#e3edf6", "bold")
        if self.impact_flash > 0:
            self.text(w / 2, h * 0.22, self.impact_message, 22,
                      "#ffdc68" if self.impact_message == "COLISÃO!" else "#ff8c78", "bold")

    def draw_pause(self) -> None:
        self.draw_race()
        w, h = self.size()
        self.canvas.create_rectangle(0, 0, w, h, fill="#020914", stipple="gray50", outline="")
        self.rounded_panel(w / 2 - 230, h / 2 - 145, w / 2 + 230, h / 2 + 145)
        self.text(w / 2, h / 2 - 75, "APEX VELOCITY", 12, "#52e5ff", "bold")
        self.text(w / 2, h / 2 - 25, "PAUSADO", 38, "#ffffff", "bold")
        self.text(w / 2, h / 2 + 25, "Pressione ESC para continuar", 13, "#b9c8d9")
        self.text(w / 2, h / 2 + 65, "Pressione M para voltar ao menu", 11, "#91a9bf")

    def draw_finish(self) -> None:
        self.menu_buttons = []
        self.canvas.delete("all")
        w, h = self.size()
        self.draw_background(w, h)
        self.canvas.create_rectangle(0, 0, w, h, fill="#020914", stipple="gray50", outline="")
        self.rounded_panel(w / 2 - 270, h / 2 - 190, w / 2 + 270, h / 2 + 190,
                           "#081827", "#36536d")
        self.text(w / 2, h / 2 - 130, TRACKS[self.selected_track]["name"], 12, "#52e5ff", "bold")
        title = "VITÓRIA!" if self.finish_position == 1 else "CORRIDA FINALIZADA"
        self.text(w / 2, h / 2 - 70, title, 34, "#ffffff", "bold")
        self.text(w / 2, h / 2 - 20, "Você cruzou a linha de chegada.", 13, "#b9c8d9")
        self.text(w / 2, h / 2 + 35, format_time(self.elapsed), 32, "#52e5ff", "bold")
        self.text(w / 2, h / 2 + 78,
                  f"Posição final: {ordinal(self.finish_position)} de 8  ·  {DIFFICULTIES[self.selected_difficulty]['name']}",
                  13, "#e7f3ff")
        self.button(int(w / 2 - 205), int(h / 2 + 115), int(w / 2 + 205), int(h / 2 + 160),
                    "CORRER NOVAMENTE", self.start_race, True)
        self.button(int(w / 2 - 205), int(h / 2 + 169), int(w / 2 + 205), int(h / 2 + 211),
                    "MENU PRINCIPAL", self.draw_menu, False)

    def run(self) -> None:
        self.root.mainloop()


# -----------------------------------------------------------------------------
# APEX VELOCITY 3.0 — oficina, motos e geometria de pista com curvas reais
# Este bloco estende a base 2.0 sem dependências externas.
# -----------------------------------------------------------------------------

import bisect

# Mais amostras por volta para descrever a trajetória com precisão.
SEGMENTS = 480
SEGMENT_LENGTH = 10.0
TRACK_LENGTH = SEGMENTS * SEGMENT_LENGTH
DRAW_DISTANCE = 145

# Veículos de duas rodas. Compartilham os sistemas de oficina da categoria Carros.
MOTORCYCLES = [
    Car("AERO 600R", "Supersport · leve e ágil", "#19c7b2", 265, 91, 96, vehicle_type="bike"),
    Car("THUNDER V4", "Naked · torque e aceleração", "#ef684b", 292, 102, 87, vehicle_type="bike"),
    Car("APEX RR 1000", "Superbike · alta velocidade", "#d8dce5", 325, 108, 92, vehicle_type="bike"),
]

PAINTS = [
    ("AZUL ELÉTRICO", "#168bd2"), ("VERMELHO", "#d83e42"),
    ("VERDE LIMA", "#78c94b"), ("PRETO FOSCO", "#252b33"),
    ("BRANCO PEROLIZADO", "#e7edf0"), ("ROXO", "#8758d7"),
    ("LARANJA", "#f28a2e"), ("DOURADO", "#bd963d"),
]

UPGRADE_INFO = {
    "engine": ("MOTOR", "Mais potência e aceleração", [3500, 6000, 9500, 14000, 20000]),
    "turbo": ("TURBO", "Pressão extra e velocidade final", [4200, 7000, 11000, 16500, 23000]),
    "transmission": ("CÂMBIO", "Relações mais rápidas", [2800, 5000, 8000, 12000, 17500]),
    "tires": ("PNEUS", "Mais aderência nas curvas", [2400, 4200, 6800, 9800, 14500]),
    "brakes": ("FREIOS", "Frenagem mais forte", [2200, 3900, 6200, 9000, 13000]),
    "suspension": ("SUSPENSÃO", "Estabilidade e controle", [2600, 4600, 7200, 10500, 15000]),
    "exhaust": ("ESCAPAMENTO", "Fluxo melhor e resposta", [1800, 3300, 5400, 8200, 12000]),
    "nitro": ("NITRO", "Desbloqueia/estende o impulso", [5000, 8000, 12000, 17000, 24000]),
}

TRACK_SHAPES = [
    # rx, rz, ondulação lateral 3x, ondulação longitudinal 2x, fase.
    # Curvas para os dois lados, com raios adequados para a física arcade.
    (420, 610, 105.42, 72.73, 5.58),  # costa
    (355, 585, 106.22, 71.74, 5.46),  # serra
    (390, 525, 115.22, 51.64, 5.20),  # cidade
    (450, 560, 109.46, 64.35, 5.26),  # deserto
    (340, 620, 101.09, 83.59, 5.35),  # floresta
]


def _av3_default_tune() -> dict:
    return {
        "engine": 0, "turbo": 0, "transmission": 0, "tires": 0,
        "brakes": 0, "suspension": 0, "exhaust": 0, "nitro": 0,
        "paint": -1, "bodykit": 0, "spoiler": 0, "rims": 0, "decals": 0,
        "neon": 0, "ride_height": 0,
    }


_old_av_init = ApexVelocity.__init__


def _av3_init(self):
    # Estes campos precisam existir antes do __init__ antigo chamar draw_menu().
    self.vehicle_category = "car"
    self.selected_motorcycle = 0
    self.garage_tab = "performance"
    self.credits = 120000
    self.tuning = {}
    self.track_path = []
    self.player_heading = 0.0
    self.player_lean = 0.0
    self.player_offset = 0.0
    self._av3_init_done = False
    _old_av_init(self)
    self.rebuild_track()
    self.draw_menu()
    self._av3_init_done = True


ApexVelocity.__init__ = _av3_init


def av3_vehicle_list(self):
    return CARS if self.vehicle_category == "car" else MOTORCYCLES


def av3_selected_vehicle(self):
    vehicles = self.vehicle_list()
    index = self.selected_car if self.vehicle_category == "car" else self.selected_motorcycle
    return vehicles[int(clamp(index, 0, len(vehicles) - 1))]


def av3_tune(self, vehicle=None):
    vehicle = vehicle or self.selected_vehicle()
    key = f"{self.vehicle_category}:{vehicle.name}"
    if key not in self.tuning:
        self.tuning[key] = _av3_default_tune()
    return self.tuning[key]


def av3_stats(self, vehicle=None):
    vehicle = vehicle or self.selected_vehicle()
    tune = self.tune(vehicle)
    engine = tune["engine"]
    turbo = tune["turbo"]
    transmission = tune["transmission"]
    tires = tune["tires"]
    brakes = tune["brakes"]
    suspension = tune["suspension"]
    exhaust = tune["exhaust"]
    nitro_level = tune["nitro"]

    has_factory_nitro = vehicle.has_nitro
    nitro_available = has_factory_nitro or nitro_level > 0
    if has_factory_nitro:
        normal = vehicle.normal_speed or vehicle.max_speed * 0.72
        top = vehicle.max_speed
    else:
        normal = vehicle.max_speed
        top = vehicle.max_speed * (1.22 + nitro_level * 0.045) if nitro_available else vehicle.max_speed

    normal *= (1.0 + engine * 0.022 + turbo * 0.032 + transmission * 0.027 + exhaust * 0.012)
    top *= (1.0 + engine * 0.022 + turbo * 0.032 + transmission * 0.027 + exhaust * 0.012)
    acceleration = vehicle.acceleration * (1.0 + engine * 0.075 + turbo * 0.105 + transmission * 0.025 + exhaust * 0.035)
    handling = clamp(vehicle.handling + tires * 2.2 + suspension * 2.8, 45, 112)
    brake_power = 190.0 * (1.0 + brakes * 0.17 + tires * 0.025)
    base_nitro = vehicle.nitro_seconds if has_factory_nitro else (2.5 if nitro_available else 0.0)
    nitro_seconds = base_nitro + nitro_level * 1.15
    nitro_accel = vehicle.nitro_acceleration * (1.0 + turbo * 0.10 + engine * 0.05) if has_factory_nitro else 260 + turbo * 35 + nitro_level * 22
    paint = vehicle.color if tune["paint"] < 0 else PAINTS[tune["paint"] % len(PAINTS)][1]
    return {
        "normal_speed": normal, "max_speed": top, "acceleration": acceleration,
        "handling": handling, "brake_power": brake_power,
        "has_nitro": nitro_available, "nitro_seconds": nitro_seconds,
        "nitro_acceleration": nitro_accel, "color": paint,
        "vehicle_type": getattr(vehicle, "vehicle_type", "car"),
    }


ApexVelocity.vehicle_list = av3_vehicle_list
ApexVelocity.selected_vehicle = av3_selected_vehicle
ApexVelocity.tune = av3_tune
ApexVelocity.vehicle_stats = av3_stats


def av3_set_category(self, category):
    self.vehicle_category = "bike" if category == "bike" else "car"
    self.draw_menu()


def av3_select_vehicle(self, index):
    if self.vehicle_category == "car":
        self.selected_car = int(clamp(index, 0, len(CARS) - 1))
    else:
        self.selected_motorcycle = int(clamp(index, 0, len(MOTORCYCLES) - 1))
    self.draw_menu()


def av3_set_tab(self, tab):
    self.garage_tab = tab
    self.draw_menu()


def av3_select_track(self, index):
    self.selected_track = int(clamp(index, 0, len(TRACKS) - 1))
    self.rebuild_track()
    self.draw_menu()


def av3_select_difficulty(self, index):
    self.selected_difficulty = int(clamp(index, 0, len(DIFFICULTIES) - 1))
    self.draw_menu()


def av3_upgrade(self, key, delta):
    tune = self.tune()
    old = tune[key]
    if delta > 0 and old < 5:
        cost = UPGRADE_INFO[key][2][old]
        if self.credits >= cost:
            self.credits -= cost
            tune[key] = old + 1
    elif delta < 0 and old > 0:
        refund = int(UPGRADE_INFO[key][2][old - 1] * 0.45)
        self.credits += refund
        tune[key] = old - 1
    self.draw_menu()


def av3_cycle_cosmetic(self, key, delta):
    tune = self.tune()
    if key == "paint":
        tune[key] = (tune[key] + delta) % len(PAINTS) if tune[key] >= 0 else (0 if delta > 0 else len(PAINTS) - 1)
    else:
        tune[key] = (tune[key] + delta) % (5 if key in ("rims", "neon") else 4)
    self.draw_menu()


ApexVelocity.set_category = av3_set_category
ApexVelocity.select_vehicle = av3_select_vehicle
ApexVelocity.set_garage_tab = av3_set_tab
ApexVelocity.select_track = av3_select_track
ApexVelocity.select_difficulty = av3_select_difficulty
ApexVelocity.change_upgrade = av3_upgrade
ApexVelocity.cycle_cosmetic = av3_cycle_cosmetic


def av3_draw_menu(self):
    self.state = "menu"
    self.menu_buttons = []
    self.canvas.delete("all")
    w, h = self.size()
    self.canvas.create_rectangle(0, 0, w, h, fill="#06111d", outline="")
    # Fundo com linhas diagonais para dar identidade visual à garagem.
    for i in range(-h, w, 55):
        self.canvas.create_line(i, 0, i + h, h, fill="#0b1d2d", width=1)
    self.text(38, 34, "APEX VELOCITY 3.0", 20, "#54e2ff", "bold", "w")
    self.text(40, 61, "GARAGEM · OFICINA · CARROS E MOTOS", 9, "#90a8bd", "bold", "w")
    self.text(w - 45, 42, f"CRÉDITOS  {self.credits:,.0f}".replace(",", "."), 13, "#f2d27a", "bold", "e")

    # Painéis da garagem e da oficina.
    self.rounded_panel(30, 88, 435, h - 26, "#0b1b2a", "#29465d")
    self.rounded_panel(450, 88, w - 30, h - 26, "#0b1b2a", "#29465d")

    self.button(52, 108, 224, 145, "CATEGORIA: CARROS", lambda: self.set_category("car"),
                self.vehicle_category == "car", "#16455a" if self.vehicle_category == "car" else "#142638")
    self.button(232, 108, 413, 145, "CATEGORIA: MOTOS", lambda: self.set_category("bike"),
                self.vehicle_category == "bike", "#16455a" if self.vehicle_category == "bike" else "#142638")

    vehicles = self.vehicle_list()
    self.text(55, 165, "ESCOLHA SEU VEÍCULO", 10, "#a9bfd2", "bold", "w")
    current_index = self.selected_car if self.vehicle_category == "car" else self.selected_motorcycle
    for i, vehicle in enumerate(vehicles):
        col, row = i % 2, i // 2
        x1 = 52 + col * 180
        y1 = 185 + row * 43
        x2, y2 = x1 + 170, y1 + 36
        active = i == current_index
        label = vehicle.name
        self.button(x1, y1, x2, y2, label, lambda n=i: self.select_vehicle(n), active,
                    "#17475a" if active else "#142638")
        if active:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#55e1fa", width=2)

    selected = self.selected_vehicle()
    stats = self.vehicle_stats(selected)
    tune = self.tune(selected)
    self.text(55, 335, selected.name, 20, "#ffffff", "bold", "w")
    self.text(55, 359, selected.description, 9, "#9db2c6", anchor="w")
    if self.vehicle_category == "bike":
        self.draw_bike(235, 505, 65, 165, stats["color"], True, 0.05, tune)
    else:
        self.draw_car(235, 520, 160 if selected.name == "CONGUITOS XL" else 132,
                      145 if selected.name == "CONGUITOS XL" else 120, stats["color"], True,
                      selected.name == "NEYMAR 10", False, selected.name == "CONGUITOS XL")
        self.draw_custom_details(235, 520, 132, 120, tune, stats["color"])
    self.text(55, 570, f"FINAL: {int(stats['max_speed']):,} km/h".replace(",", "."), 11, "#e7f4ff", "bold", "w")
    self.text(55, 592, f"ACELERAÇÃO: {stats['acceleration']:.0f}  ·  ADERÊNCIA: {stats['handling']:.0f}",
              9, "#a9bfd2", anchor="w")
    self.text(55, 614, f"FREIOS: {stats['brake_power']:.0f}  ·  NITRO: {stats['nitro_seconds']:.1f}s",
              9, "#a9bfd2", anchor="w")
    self.text(55, 658, "A oficina salva os ajustes por veículo.", 9, "#8fa8bd", anchor="w")
    self.text(55, 678, "Melhorias custam créditos; visual é livre.", 9, "#8fa8bd", anchor="w")

    # Abas da oficina.
    self.button(472, 108, 650, 145, "DESEMPENHO", lambda: self.set_garage_tab("performance"),
                self.garage_tab == "performance", "#17475a" if self.garage_tab == "performance" else "#142638")
    self.button(660, 108, 838, 145, "ESTÉTICA", lambda: self.set_garage_tab("visual"),
                self.garage_tab == "visual", "#17475a" if self.garage_tab == "visual" else "#142638")

    if self.garage_tab == "performance":
        self.text(480, 168, "PEÇAS E PREPARAÇÃO", 10, "#a9bfd2", "bold", "w")
        keys = list(UPGRADE_INFO.keys())
        for idx, key in enumerate(keys):
            col, row = idx // 4, idx % 4
            x = 480 + col * 365
            y = 195 + row * 79
            label, desc, costs = UPGRADE_INFO[key]
            level = tune[key]
            self.rounded_panel(x, y, x + 340, y + 66, "#102337", "#29465d")
            self.text(x + 12, y + 14, f"{label}  ·  NÍVEL {level}/5", 10, "#f0f5fa", "bold", "w")
            self.text(x + 12, y + 36, desc, 8, "#94aabd", anchor="w")
            self.text(x + 12, y + 54, "MAX" if level == 5 else f"Próximo: {costs[level]:,} CR".replace(",", "."),
                      8, "#e4c66e", "bold", "w")
            self.button(x + 256, y + 13, x + 291, y + 49, "−", lambda k=key: self.change_upgrade(k, -1), False, "#26394a")
            self.button(x + 297, y + 13, x + 332, y + 49, "+", lambda k=key: self.change_upgrade(k, 1), False, "#24533f")
        self.text(480, 527, "DICA: pneus + suspensão ajudam a manter a trajetória nas curvas; freios reduzem a distância de frenagem.",
                  8, "#91a9bf", anchor="w")
    else:
        self.text(480, 168, "PERSONALIZAÇÃO VISUAL", 10, "#a9bfd2", "bold", "w")
        self.text(480, 205, "PINTURA", 10, "#f0f5fa", "bold", "w")
        self.button(590, 185, 630, 220, "◀", lambda: self.cycle_cosmetic("paint", -1), False, "#26394a")
        self.button(638, 185, 678, 220, "▶", lambda: self.cycle_cosmetic("paint", 1), False, "#26394a")
        paint_label = "ORIGINAL" if tune["paint"] < 0 else PAINTS[tune["paint"]][0]
        self.text(700, 203, paint_label, 10, stats["color"], "bold", "w")
        self.canvas.create_rectangle(480, 230, 840, 245, fill=stats["color"], outline="#e7edf4")
        cosmetics = [("bodykit", "WIDEBODY / KIT", 0, 3), ("spoiler", "AEROFÓLIO", 0, 3),
                     ("rims", "RODAS / AROS", 0, 4), ("decals", "ADESIVOS / FAIXAS", 0, 3),
                     ("neon", "ILUMINAÇÃO NEON", 0, 4), ("ride_height", "ALTURA / POSTURA", 0, 3)]
        for i, (key, label, _lo, _hi) in enumerate(cosmetics):
            y = 264 + i * 43
            self.text(480, y + 12, label, 10, "#e6edf5", "bold", "w")
            self.text(760, y + 12, f"ESTÁGIO {tune[key]}", 9, "#9db2c6", "bold", "e")
            self.button(790, y - 5, 830, y + 29, "−", lambda k=key: self.cycle_cosmetic(k, -1), False, "#26394a")
            self.button(838, y - 5, 878, y + 29, "+", lambda k=key: self.cycle_cosmetic(k, 1), False, "#24533f")
        self.text(480, 535, "Widebody, rodas, neon, altura e adesivos aparecem também durante a corrida.", 8, "#91a9bf", anchor="w")

    # Seleção de circuito e dificuldade sempre visíveis na oficina.
    self.text(480, 570, "CIRCUITO", 9, "#a9bfd2", "bold", "w")
    track_gap = 5
    x_start, x_end = 480, w - 52
    track_bw = (x_end - x_start - track_gap * 4) / 5
    for i, track in enumerate(TRACKS):
        x1 = int(x_start + i * (track_bw + track_gap))
        x2 = int(x1 + track_bw)
        active = i == self.selected_track
        self.button(x1, 583, x2, 615, track["short"], lambda n=i: self.select_track(n), active,
                    "#17475a" if active else "#142638")
        if active:
            self.canvas.create_rectangle(x1, 583, x2, 615, outline=track["accent"], width=2)

    self.text(480, 642, "DIFICULDADE", 9, "#a9bfd2", "bold", "w")
    diff_gap = 7
    diff_bw = 145
    for i, item in enumerate(DIFFICULTIES):
        x1 = 580 + i * (diff_bw + diff_gap)
        active = i == self.selected_difficulty
        self.button(x1, 626, x1 + diff_bw, 660, item["name"], lambda n=i: self.select_difficulty(n), active,
                    "#31533f" if active else "#142638")
    self.button(480, 684, w - 52, 740, "INICIAR CORRIDA  →", self.start_race, True)


ApexVelocity.draw_menu = av3_draw_menu


def av3_rebuild_track(self):
    # Constrói uma linha central fechada e contínua usando uma curva paramétrica.
    # As coordenadas são reamostradas por distância de arco, não por ângulo,
    # para que a velocidade e a física sejam consistentes em toda a volta.
    rx, rz, amp_x, amp_z, phase = TRACK_SHAPES[self.selected_track]
    dense_n = 6000
    raw = []
    for j in range(dense_n + 1):
        u = 2.0 * math.pi * j / dense_n
        x = rx * math.sin(u) + amp_x * math.sin(3 * u + phase) + amp_x * 0.28 * math.sin(5 * u + phase * 1.7)
        z = rz * (1 - math.cos(u)) + amp_z * math.sin(2 * u + phase * 0.7) + amp_z * 0.25 * math.sin(4 * u + phase * 1.3)
        raw.append((x, z))
    cumulative = [0.0]
    for i in range(1, len(raw)):
        cumulative.append(cumulative[-1] + math.hypot(raw[i][0] - raw[i-1][0], raw[i][1] - raw[i-1][1]))
    total = cumulative[-1]
    sampled = []
    for i in range(SEGMENTS + 1):
        target = total * i / SEGMENTS
        j = bisect.bisect_left(cumulative, target)
        j = max(1, min(j, dense_n))
        span = cumulative[j] - cumulative[j - 1]
        f = 0.0 if span <= 0 else (target - cumulative[j - 1]) / span
        x = raw[j - 1][0] * (1 - f) + raw[j][0] * f
        z = raw[j - 1][1] * (1 - f) + raw[j][1] * f
        sampled.append((x, z))
    # Escala para casar distância física e comprimento do circuito (4.800 m).
    world_scale = TRACK_LENGTH / max(1.0, total)
    # Desloca a origem para (0,0) e remove o pequeno erro numérico de fechamento.
    ox, oz = sampled[0]
    sampled = [((x - ox) * world_scale, (z - oz) * world_scale) for x, z in sampled]
    # Determina orientação tangente e a mantém contínua ao cruzar a linha de chegada.
    angles = []
    for i in range(SEGMENTS):
        prev = sampled[(i - 1) % SEGMENTS]
        nxt = sampled[(i + 1) % SEGMENTS]
        raw_angle = math.atan2(nxt[0] - prev[0], nxt[1] - prev[1])
        if angles:
            while raw_angle - angles[-1] > math.pi:
                raw_angle -= 2 * math.pi
            while raw_angle - angles[-1] < -math.pi:
                raw_angle += 2 * math.pi
        angles.append(raw_angle)
    signed_turn = angles[-1] - angles[0]
    closure = angles[0] + (2 * math.pi if signed_turn >= 0 else -2 * math.pi)
    ds = TRACK_LENGTH / SEGMENTS
    path = []
    for i in range(SEGMENTS):
        prev_i, next_i = (i - 1) % SEGMENTS, (i + 1) % SEGMENTS
        prev_angle = angles[prev_i]
        next_angle = angles[next_i]
        if i == 0:
            prev_angle = angles[-1] - (closure - angles[0])
        if i == SEGMENTS - 1:
            next_angle = closure
        curvature = (next_angle - prev_angle) / (2 * ds)
        path.append({"x": sampled[i][0], "z": sampled[i][1], "theta": angles[i], "k": curvature})
    path.append({"x": sampled[0][0], "z": sampled[0][1], "theta": closure, "k": path[0]["k"]})
    self.track_path = path


def av3_track_pose(self, distance):
    if not self.track_path:
        self.rebuild_track()
    d = distance % TRACK_LENGTH
    segf = d / SEGMENT_LENGTH
    idx = min(SEGMENTS - 1, int(segf))
    f = segf - idx
    a, b = self.track_path[idx], self.track_path[idx + 1]
    return {
        "x": a["x"] * (1-f) + b["x"] * f,
        "z": a["z"] * (1-f) + b["z"] * f,
        "theta": a["theta"] * (1-f) + b["theta"] * f,
        "k": a["k"] * (1-f) + b["k"] * f,
    }


def av3_curve_at(self, index):
    return self.track_pose(index * SEGMENT_LENGTH)["k"]


ApexVelocity.rebuild_track = av3_rebuild_track
ApexVelocity.track_pose = av3_track_pose
ApexVelocity.curve_at = av3_curve_at


def av3_start_race(self):
    self.menu_buttons = []
    self.rebuild_track()
    self.elapsed = 0.0
    self.player_distance = 0.0
    self.player_x = 0.0
    self.player_offset = 0.0
    self.player_heading = 0.0
    self.player_lean = 0.0
    self.speed = 0.0
    self.steering = 0.0
    self.shake = 0.0
    self.nitro_remaining = self.vehicle_stats()["nitro_seconds"]
    self.nitro_active = False
    self.impact_flash = 0.0
    self.impact_message = ""
    self.opponents = []
    stats = self.vehicle_stats()
    difficulty = DIFFICULTIES[self.selected_difficulty]
    base_speed = stats["normal_speed"]
    for i in range(7):
        self.opponents.append({
            "distance": 65 + i * 64 + random.uniform(-10, 10),
            "lane": (-3.1 if i % 2 == 0 else 3.1) + random.uniform(-0.35, 0.35),
            "speed": clamp(base_speed * 0.74 * difficulty["speed"] * random.uniform(0.92, 1.06), 130, 560),
            "color": OPPONENT_COLORS[i],
            "collision_cd": random.uniform(0.0, 0.25),
            "id": i,
            "flash": 0.0,
        })
    self.state = "race"
    self.last_tick = time.perf_counter()
    self.draw_race()


ApexVelocity.start_race = av3_start_race


def av3_update(self, dt):
    if self.state != "race":
        return
    dt = min(dt, 0.04)
    self.elapsed += dt
    vehicle = self.selected_vehicle()
    stats = self.vehicle_stats(vehicle)
    tune = self.tune(vehicle)
    difficulty = DIFFICULTIES[self.selected_difficulty]
    throttle = self.keys.get("w", False) or self.keys.get("up", False)
    brake = self.keys.get("s", False) or self.keys.get("down", False)
    left = self.keys.get("a", False) or self.keys.get("left", False)
    right = self.keys.get("d", False) or self.keys.get("right", False)
    handbrake = self.keys.get("space", False)
    nitro_key = self.keys.get("n", False) or self.keys.get("shift_l", False) or self.keys.get("shift_r", False)
    self.nitro_active = bool(stats["has_nitro"] and nitro_key and throttle and self.nitro_remaining > 0.0)

    # Motor, turbo, câmbio e nitro alteram efetivamente a aceleração e a final.
    if self.nitro_active:
        self.nitro_remaining = max(0.0, self.nitro_remaining - dt)
        self.speed += stats["nitro_acceleration"] * dt
    elif throttle:
        self.speed += stats["acceleration"] * dt
        if self.speed > stats["normal_speed"] and not vehicle.has_nitro:
            self.speed = stats["normal_speed"]
    else:
        self.speed = max(0.0, self.speed - 8.0 * dt)
    if brake:
        self.speed = max(0.0, self.speed - stats["brake_power"] * dt)
    if handbrake:
        self.speed = max(0.0, self.speed - 130.0 * dt)
    max_allowed = stats["max_speed"] if self.nitro_active else stats["normal_speed"]
    if vehicle.has_nitro and not self.nitro_active:
        max_allowed = stats["normal_speed"]
    self.speed = clamp(self.speed, 0.0, max_allowed)

    # Dinâmica do veículo sobre uma estrada curva de verdade.
    # A guinada do volante compete com a curvatura da pista; sem esterçar,
    # o veículo não acompanha automaticamente a curva e pode sair da estrada.
    self.steering = float(right) - float(left)
    v_ms = self.speed / 3.6
    handling_factor = stats["handling"] / 90.0
    max_yaw_rate = (0.42 + min(v_ms, 95.0) * 0.0065) * handling_factor
    if stats["vehicle_type"] == "bike":
        max_yaw_rate *= 1.13
    road_curve = self.track_pose(self.player_distance)["k"]
    yaw_from_wheel = self.steering * max_yaw_rate
    self.player_heading += (yaw_from_wheel - road_curve * v_ms) * dt
    self.player_heading = clamp(self.player_heading, -0.68, 0.68)
    self.player_offset += v_ms * math.sin(self.player_heading) * dt
    if handbrake and abs(self.player_heading) < 0.68:
        self.player_heading += self.steering * 0.12 * dt
    self.player_lean = clamp(self.player_heading * 0.9 + self.steering * min(v_ms / 90.0, 1.0) * 0.12, -0.75, 0.75)
    self.player_x = self.player_offset / 6.0

    # Limites da pista e penalidade gradual fora do asfalto.
    offroad = abs(self.player_offset) > 5.45
    if abs(self.player_offset) > 6.2:
        self.speed = max(35.0, self.speed - 115.0 * dt)
    elif offroad:
        self.speed = max(55.0, self.speed - 55.0 * dt)
    if offroad:
        self.shake = min(7.0, self.shake + dt * 15)
        if self.impact_flash <= 0:
            self.impact_message = "FORA DA PISTA!"
            self.impact_flash = 0.30
    else:
        self.shake = max(0.0, self.shake - dt * 12)

    self.player_distance += self.speed / 3.6 * dt

    # IA segue a linha central e faz pequenas mudanças de faixa.
    for opponent in self.opponents:
        opponent["collision_cd"] = max(0.0, opponent["collision_cd"] - dt)
        opponent["flash"] = max(0.0, opponent["flash"] - dt)
        opponent["distance"] += opponent["speed"] / 3.6 * dt
        relative = opponent["distance"] - self.player_distance
        sway = math.sin(self.elapsed * (0.60 + difficulty["aggression"] * 0.40) + opponent["id"] * 1.8) * 0.24
        target_lane = clamp((-3.1 if opponent["id"] % 2 == 0 else 3.1) + sway, -4.0, 4.0)
        if abs(relative) < 30 and abs(opponent["lane"] - self.player_offset) < 2.2:
            target_lane = clamp(opponent["lane"] + (1.0 if opponent["lane"] < self.player_offset else -1.0), -4.2, 4.2)
        opponent["lane"] += (target_lane - opponent["lane"]) * min(1.0, dt * (0.7 + difficulty["aggression"]))

    # Colisão jogador x rival: largura diferente para moto e carro.
    player_half = 0.75 if stats["vehicle_type"] == "bike" else 1.05
    for opponent in self.opponents:
        gap = opponent["distance"] - self.player_distance
        lateral = opponent["lane"] - self.player_offset
        if abs(gap) < (5.2 if stats["vehicle_type"] == "bike" else 7.2) and abs(lateral) < (1.25 + player_half) and opponent["collision_cd"] <= 0:
            side = -1.0 if lateral > 0 else 1.0
            if abs(lateral) < 0.05:
                side = -1.0 if opponent["id"] % 2 == 0 else 1.0
            impact = abs(self.speed - opponent["speed"]) / 270.0
            self.speed *= clamp(0.58 - impact * 0.08, 0.36, 0.60)
            self.player_offset += side * (1.25 if stats["vehicle_type"] == "bike" else 1.05)
            opponent["lane"] = clamp(opponent["lane"] - side * 1.0, -4.4, 4.4)
            opponent["speed"] *= 0.82
            opponent["distance"] += -2.2 if gap > 0 else 2.2
            opponent["collision_cd"] = 0.85
            opponent["flash"] = 0.4
            self.shake = max(self.shake, 5.0)
            self.impact_flash = 0.5
            self.impact_message = "COLISÃO!"

    # Colisões entre os próprios adversários.
    for i in range(len(self.opponents)):
        a = self.opponents[i]
        for j in range(i + 1, len(self.opponents)):
            b = self.opponents[j]
            if abs(a["distance"] - b["distance"]) < 5.5 and abs(a["lane"] - b["lane"]) < 1.8:
                if a["collision_cd"] <= 0 and b["collision_cd"] <= 0:
                    side = -1 if a["lane"] >= b["lane"] else 1
                    a["lane"] = clamp(a["lane"] + side * 0.8, -4.5, 4.5)
                    b["lane"] = clamp(b["lane"] - side * 0.8, -4.5, 4.5)
                    a["speed"] *= 0.93
                    b["speed"] *= 0.93
                    a["collision_cd"] = b["collision_cd"] = 0.7
                    a["flash"] = b["flash"] = 0.25

    self.impact_flash = max(0.0, self.impact_flash - dt)
    self.player_offset = clamp(self.player_offset, -8.0, 8.0)
    self.player_x = self.player_offset / 6.0
    if self.player_distance >= TRACK_LENGTH * LAPS:
        self.finish_race()


ApexVelocity.update = av3_update


def av3_project(self, distance, lateral, player_pose, player_yaw, w, h):
    pose = self.track_pose(distance)
    # Normal à direita da tangente.
    wx = pose["x"] + math.cos(pose["theta"]) * lateral
    wz = pose["z"] - math.sin(pose["theta"]) * lateral
    player_x = player_pose["x"] + math.cos(player_pose["theta"]) * self.player_offset
    player_z = player_pose["z"] - math.sin(player_pose["theta"]) * self.player_offset
    dx, dz = wx - player_x, wz - player_z
    forward = dx * math.sin(player_yaw) + dz * math.cos(player_yaw)
    side = dx * math.cos(player_yaw) - dz * math.sin(player_yaw)
    if forward <= 1.5:
        return None
    focal = min(w, h) * 1.28
    scale = focal / forward
    horizon = h * 0.425
    sx = w * 0.5 + side * scale
    sy = horizon + 3.65 * scale
    half_road = 6.15 * scale
    return sx, sy, half_road, scale, forward


ApexVelocity.project_track = av3_project


def av3_draw_road(self):
    w, h = self.size()
    self.draw_background(w, h)
    horizon = h * 0.425
    player_pose = self.track_pose(self.player_distance)
    player_yaw = player_pose["theta"] + self.player_heading
    track = TRACKS[self.selected_track]

    points = []
    for i in range(DRAW_DISTANCE + 1):
        # Pequeno deslocamento à frente da câmera evita projetar o eixo exatamente no horizonte.
        p = self.project_track(self.player_distance + 7.0 + i * 10.0, 0.0,
                               player_pose, player_yaw, w, h)
        points.append(p)

    # Segmentos do horizonte até a câmera. O centro da estrada vem da geometria
    # fechada do circuito, logo as curvas existem mesmo sem qualquer input do jogador.
    for i in range(DRAW_DISTANCE - 1, -1, -1):
        far, near = points[i + 1], points[i]
        if far is None or near is None:
            continue
        fx, fy, fw, fs, _ = far
        nx, ny, nw, ns, _ = near
        if ny < fy:
            continue
        band = ((int(self.player_distance / 10) + i) // 3) % 2
        grass = track["ground"] if band else track["hill"]
        self.poly([(0, fy), (w, fy), (w, ny), (0, ny)], grass)
        curb_far, curb_near = fw * 0.10, nw * 0.10
        curb = "#f4f1e7" if band else "#d84b42"
        self.poly([(fx-fw-curb_far, fy), (fx-fw, fy), (nx-nw, ny), (nx-nw-curb_near, ny)], curb)
        self.poly([(fx+fw, fy), (fx+fw+curb_far, fy), (nx+nw+curb_near, ny), (nx+nw, ny)], curb)
        asphalt = track["road"] if band else "#343a42"
        self.poly([(fx-fw, fy), (fx+fw, fy), (nx+nw, ny), (nx-nw, ny)], asphalt)
        # Bordas claras e tracejado central dão referência para tangência e frenagem.
        self.canvas.create_line(fx-fw*0.94, fy, nx-nw*0.94, ny, fill="#d7e1e5", width=max(1, int(ns*0.018)))
        self.canvas.create_line(fx+fw*0.94, fy, nx+nw*0.94, ny, fill="#d7e1e5", width=max(1, int(ns*0.018)))
        if (i // 5) % 2 == 0:
            self.canvas.create_line(fx, fy, nx, ny, fill="#d6dadd", width=max(1, int(ns*0.014)))
        # Objetos de pista ancorados na mesma geometria curva.
        if i % 12 == 0 and i > 1:
            size = clamp(ns * 0.95, 8, 68)
            for side in (-1, 1):
                obj = self.project_track(self.player_distance + 7.0 + i * 10.0,
                                         side * 9.2, player_pose, player_yaw, w, h)
                if obj and horizon < obj[1] < h:
                    if track["kind"] == "city":
                        self.canvas.create_rectangle(obj[0]-size*.16, obj[1]-size*1.8,
                                                     obj[0]+size*.16, obj[1], fill="#343b55", outline=track["accent"])
                    else:
                        self.draw_tree(obj[0], obj[1], size, 0)
        if i % 46 == 0 and i > 3:
            sign = self.project_track(self.player_distance + 7.0 + i * 10.0,
                                      -9.6, player_pose, player_yaw, w, h)
            if sign and horizon < sign[1] < h:
                sw = clamp(sign[3] * 1.8, 10, 120)
                self.canvas.create_rectangle(sign[0]-sw, sign[1]-sw*.48, sign[0]+sw,
                                             sign[1]-sw*.12, fill="#64717c", outline="#d0d7dd")

    # Linha de largada: pequeno tabuleiro na largura da estrada.
    if (self.player_distance % TRACK_LENGTH) < 100:
        near = points[0]
        if near:
            cx, yy, rw, _, _ = near
            tile = max(4, rw * 0.10)
            for n in range(12):
                for side in range(2):
                    xx = cx - rw * 0.9 + (n * 2 + side) * tile
                    self.canvas.create_rectangle(xx, yy-3, xx+tile, yy+5,
                                                 fill="#f2f4f5" if (n+side)%2 == 0 else "#20252b", outline="")
    return horizon


ApexVelocity.draw_road = av3_draw_road


def av3_draw_bike(self, x, y, width, height, color, player=False, lean=0.0, tune=None):
    tune = tune or _av3_default_tune()
    c = self.canvas
    lean_px = lean * width * 0.28
    c.create_oval(x-width*.27, y-height*.92, x+width*.27, y-height*.48,
                  fill="#090d12", outline="#65727d", width=max(1, int(width*.025)))
    c.create_oval(x-width*.24+lean_px*.25, y-height*.20, x+width*.24+lean_px*.25, y+height*.23,
                  fill="#090d12", outline="#65727d", width=max(1, int(width*.025)))
    # Garfo, chassi e tanque vistos por trás.
    self.canvas.create_line(x, y-height*.76, x+lean_px, y-height*.17, fill="#c8d1d7", width=max(2, int(width*.07)))
    self.canvas.create_polygon(x-width*.14+lean_px, y-height*.72,
                               x+width*.14+lean_px, y-height*.72,
                               x+width*.24+lean_px, y-height*.30,
                               x-width*.24+lean_px, y-height*.30,
                               fill=color, outline="#dbe8ee", width=1)
    self.canvas.create_polygon(x-width*.23+lean_px, y-height*.34,
                               x+width*.23+lean_px, y-height*.34,
                               x+width*.16, y-height*.10,
                               x-width*.16, y-height*.10,
                               fill="#161f2a", outline="#55616b")
    # Rider e capacete.
    rider = color if player else "#222b35"
    self.canvas.create_oval(x-width*.18+lean_px, y-height*.98, x+width*.18+lean_px,
                            y-height*.69, fill="#202a35", outline="#aebdc8", width=1)
    self.canvas.create_arc(x-width*.14+lean_px, y-height*.96, x+width*.14+lean_px,
                           y-height*.74, start=190, extent=160, style="arc", outline="#9bd7e6", width=2)
    self.canvas.create_polygon(x-width*.24+lean_px, y-height*.62,
                               x+width*.24+lean_px, y-height*.62,
                               x+width*.30+lean_px, y-height*.38,
                               x-width*.30+lean_px, y-height*.38,
                               fill=rider, outline="#101820")
    self.canvas.create_line(x-width*.28, y-height*.67, x+width*.28, y-height*.67,
                            fill="#becbd3", width=max(1, int(width*.025)))
    # Lanterna, escapamento e detalhes configuráveis.
    self.canvas.create_oval(x-width*.07+lean_px, y-height*.39, x+width*.07+lean_px,
                            y-height*.29, fill="#ff4545", outline="#ffc2b4")
    for side in (-1, 1):
        self.canvas.create_line(x+side*width*.17, y-height*.30, x+side*width*.24,
                                y-height*.12, fill="#aab4bd", width=max(1, int(width*.035)))
    if tune.get("rims", 0):
        ring = ["#aeb8c2", "#d4b65c", "#55c5dc", "#e65c54", "#dfe4ea"][tune["rims"]]
        c.create_oval(x-width*.17, y-height*.89, x+width*.17, y-height*.51, outline=ring, width=max(1, int(width*.035)))
    if tune.get("decals", 0):
        c.create_text(x+lean_px, y-height*.48, text="AV", fill="#fff4cc", font=("Segoe UI", max(5, int(width*.10)), "bold"))
    if tune.get("neon", 0):
        neon_colors = ["#3eeaff", "#ff4bd8", "#9cff4b", "#b78bff", "#ffb347"]
        c.create_line(x-width*.22, y-height*.23, x+width*.22, y-height*.23,
                      fill=neon_colors[tune["neon"]], width=max(2, int(width*.035)))
    if tune.get("spoiler", 0):
        c.create_line(x-width*.24, y-height*.72, x+width*.24, y-height*.72,
                      fill="#171c23", width=max(2, int(width*.05)))


ApexVelocity.draw_bike = av3_draw_bike


def av3_draw_custom_details(self, x, y, width, height, tune, color):
    # Acessórios visíveis no preview e na corrida.
    bodykit = tune.get("bodykit", 0)
    if bodykit:
        flare = width * (0.025 + bodykit * 0.018)
        for side in (-1, 1):
            self.canvas.create_polygon(
                x + side*width*.40, y-height*.48,
                x + side*(width*.48+flare), y-height*.30,
                x + side*(width*.51+flare), y+height*.04,
                x + side*width*.40, y+height*.13,
                fill="#111a23", outline="#758796", width=1)
        self.canvas.create_polygon(x-width*.48, y+height*.08, x-width*.30, y+height*.19,
                                   x+width*.30, y+height*.19, x+width*.48, y+height*.08,
                                   fill="#101820", outline="#7b8b99")
        if bodykit >= 2:
            self.canvas.create_line(x-width*.46, y-height*.18, x-width*.53, y+height*.05,
                                    fill="#b6c6d0", width=max(2, int(width*.028)))
            self.canvas.create_line(x+width*.46, y-height*.18, x+width*.53, y+height*.05,
                                    fill="#b6c6d0", width=max(2, int(width*.028)))
    if tune.get("spoiler", 0):
        sw = width * (0.48 + tune["spoiler"] * 0.055)
        sy = y - height * (0.74 + tune["spoiler"] * 0.015)
        self.canvas.create_line(x-sw/2, sy, x+sw/2, sy, fill="#101820", width=max(3, int(width*.035)))
        self.canvas.create_line(x-sw*.34, sy+height*.035, x+sw*.34, sy+height*.035,
                                fill="#8795a0", width=max(1, int(width*.018)))
    if tune.get("rims", 0):
        ring = ["#9caab5", "#e6c35c", "#47c9df", "#d95757", "#e5eaf0"][tune["rims"]]
        for side in (-1, 1):
            self.canvas.create_oval(x+side*width*.31-width*.07, y-height*.12,
                                    x+side*width*.31+width*.07, y+height*.24,
                                    outline=ring, width=max(1, int(width*.025)))
    if tune.get("decals", 0):
        accent = ["#ffffff", "#f4d252", "#54e4ff", "#e879ff"][tune["decals"]]
        self.canvas.create_line(x-width*.31, y-height*.40, x-width*.22, y+height*.08,
                                fill=accent, width=max(2, int(width*.025)))
        self.canvas.create_line(x+width*.31, y-height*.40, x+width*.22, y+height*.08,
                                fill=accent, width=max(2, int(width*.025)))
    if tune.get("neon", 0):
        neon_colors = ["#3eeaff", "#ff4bd8", "#9cff4b", "#b78bff", "#ffb347"]
        neon = neon_colors[tune["neon"]]
        self.canvas.create_line(x-width*.34, y+height*.16, x+width*.34, y+height*.16,
                                fill=neon, width=max(2, int(width*.025)))
        self.canvas.create_line(x-width*.40, y+height*.05, x-width*.44, y+height*.15,
                                fill=neon, width=max(2, int(width*.02)))
        self.canvas.create_line(x+width*.40, y+height*.05, x+width*.44, y+height*.15,
                                fill=neon, width=max(2, int(width*.02)))
    if tune.get("ride_height", 0):
        # Indicador visual de stance/altura ajustada na carroceria.
        stance = ["#9aa8b5", "#58c8dd", "#e7c15c", "#e77979"][tune["ride_height"]]
        self.canvas.create_line(x-width*.25, y+height*.12, x+width*.25, y+height*.12,
                                fill=stance, width=max(2, int(width*.018)))


ApexVelocity.draw_custom_details = av3_draw_custom_details


def av3_draw_race(self):
    if self.state != "race":
        return
    self.canvas.delete("all")
    w, h = self.size()
    self.draw_road()
    player_pose = self.track_pose(self.player_distance)
    player_yaw = player_pose["theta"] + self.player_heading
    stats = self.vehicle_stats()
    vehicle = self.selected_vehicle()
    tune = self.tune(vehicle)

    # Rivais são projetados na mesma geometria física do asfalto.
    visible = [o for o in self.opponents if 4 < o["distance"] - self.player_distance < DRAW_DISTANCE * 10]
    visible.sort(key=lambda o: o["distance"], reverse=True)
    for opponent in visible:
        p = self.project_track(opponent["distance"], opponent["lane"], player_pose, player_yaw, w, h)
        if not p:
            continue
        sx, sy, _roadw, scale, forward = p
        if sy < h*.425 or sy > h*1.05:
            continue
        bike_mode = self.vehicle_category == "bike" and opponent["id"] % 3 == 0
        ww = clamp((1.05 if bike_mode else 2.0) * scale, 7, 105)
        hh = ww * (2.05 if bike_mode else 1.10)
        if bike_mode:
            self.draw_bike(sx, sy, ww, hh, opponent["color"], False, 0.0, None)
        else:
            self.draw_car(sx, sy, ww, hh, opponent["color"], hit=opponent["flash"] > 0)

    # Player ocupa o primeiro plano; o modelo inclina de acordo com sua guinada.
    px = w * 0.5 + random.uniform(-self.shake, self.shake)
    py = h * 0.90 + random.uniform(-self.shake, self.shake)
    if stats["vehicle_type"] == "bike":
        self.draw_bike(px, py, 82, 178, stats["color"], True, self.player_lean, tune)
    else:
        base_w = 170 if vehicle.name == "CONGUITOS XL" else 132
        base_h = 155 if vehicle.name == "CONGUITOS XL" else 120
        self.draw_car(px, py, base_w, base_h, stats["color"], True,
                      vehicle.name == "NEYMAR 10", self.nitro_active,
                      vehicle.name == "CONGUITOS XL")
        self.draw_custom_details(px, py, base_w, base_h, tune, stats["color"])
    self.draw_hud(w, h)


ApexVelocity.draw_race = av3_draw_race


def av3_draw_hud(self, w, h):
    vehicle = self.selected_vehicle()
    stats = self.vehicle_stats(vehicle)
    track = TRACKS[self.selected_track]
    lap = min(LAPS, int(self.player_distance / TRACK_LENGTH) + 1)
    position = 1 + sum(o["distance"] > self.player_distance for o in self.opponents)
    progress = min(1.0, self.player_distance / (TRACK_LENGTH * LAPS))
    gear = "N" if self.speed < 3 else str(min(7, max(1, int(self.speed / 42) + 1)))
    self.rounded_panel(16, 16, 310, 116, "#0a1828", "#36506a")
    self.text(32, 35, "CIRCUITO", 9, "#9ab0c9", "bold", "w")
    self.text(32, 60, track["name"], 16, "#ffffff", "bold", "w")
    self.text(32, 86, f"VOLTA {lap}/{LAPS}  ·  {DIFFICULTIES[self.selected_difficulty]['name']}", 9,
              "#b9c8d9", anchor="w")
    self.rounded_panel(w - 194, 16, w - 16, 116, "#0a1828", "#36506a")
    self.text(w - 178, 35, "POSIÇÃO", 9, "#9ab0c9", "bold", "w")
    self.text(w - 178, 65, f"{ordinal(position)} / 8", 22, "#ffffff", "bold", "w")
    self.text(w - 178, 91, format_time(self.elapsed), 10, "#b9c8d9", anchor="w")

    self.rounded_panel(16, h - 150, 265, h - 16, "#0a1828", "#36506a")
    self.text(34, h - 128, "VELOCIDADE", 9, "#9ab0c9", "bold", "w")
    self.text(32, h - 83, f"{round(self.speed):,}".replace(",", "."), 42, "#ffffff", "bold", "w")
    self.text(165, h - 68, "KM/H", 10, "#9fb4ca", "bold", "w")
    self.canvas.create_rectangle(34, h - 51, 244, h - 44, fill="#273b51", outline="")
    self.canvas.create_rectangle(34, h - 51, 34 + 210 * min(1.0, self.speed / max(1, stats["max_speed"])),
                                 h - 44, fill=track["accent"], outline="")
    self.text(34, h - 29, f"MARCHA {gear}  ·  {vehicle.name}", 9, "#c0d1df", "bold", "w")
    if stats["has_nitro"]:
        self.rounded_panel(278, h - 112, 500, h - 16, "#0a1828", "#8e742b")
        self.text(294, h - 90, "NITRO ATIVO!" if self.nitro_active else "NITRO · SEGURE N + W",
                  9, "#ffe06b", "bold", "w")
        self.canvas.create_rectangle(294, h - 65, 482, h - 54, fill="#3b3520", outline="")
        frac = self.nitro_remaining / max(.01, stats["nitro_seconds"])
        self.canvas.create_rectangle(294, h - 65, 294 + 188 * frac, h - 54, fill="#ffd84d", outline="")
        self.text(294, h - 34, f"{self.nitro_remaining:.1f}s  ·  MÁX. {int(stats['max_speed']):,} KM/H".replace(",", "."),
                  8, "#fff0ba", "bold", "w")
    self.rounded_panel(w - 318, h - 112, w - 16, h - 16, "#0a1828", "#36506a")
    self.text(w - 300, h - 90, "PROGRESSO DA CORRIDA", 9, "#9ab0c9", "bold", "w")
    self.text(w - 300, h - 67, f"{int(progress*100)}% concluído", 11, "#e3edf6", "bold", "w")
    self.canvas.create_rectangle(w - 300, h - 49, w - 34, h - 42, fill="#273b51", outline="")
    self.canvas.create_rectangle(w - 300, h - 49, w - 300 + 266 * progress, h - 42, fill=track["accent"], outline="")
    steer_hint = "A/D: virar" if stats["vehicle_type"] == "car" else "A/D: inclinar e virar"
    self.text(w / 2, h - 18, f"W acelerar · S frear · {steer_hint} · ESPAÇO freio de mão · ESC pausar",
              8, "#e3edf6", "bold")
    if self.impact_flash > 0:
        self.text(w / 2, h * .22, self.impact_message, 22,
                  "#ffdc68" if self.impact_message == "COLISÃO!" else "#ff8c78", "bold")


ApexVelocity.draw_hud = av3_draw_hud


def av3_key_down(self, event):
    key = event.keysym.lower()
    self.keys[key] = True
    if key == "escape":
        if self.state == "race":
            self.state = "paused"
            self.draw_pause()
        elif self.state == "paused":
            self.state = "race"
            self.last_tick = time.perf_counter()
    elif self.state == "paused" and key == "m":
        self.draw_menu()
    elif self.state == "menu":
        if key in ("c",):
            self.set_category("car")
        elif key in ("b",):
            self.set_category("bike")
        elif key == "tab":
            self.set_garage_tab("visual" if self.garage_tab == "performance" else "performance")
        elif key in ("1", "2", "3", "4", "5"):
            self.select_vehicle(int(key) - 1)


ApexVelocity.on_key_down = av3_key_down


def av3_finish_race(self):
    self.player_distance = TRACK_LENGTH * LAPS
    self.finish_position = 1 + sum(o["distance"] > self.player_distance for o in self.opponents)
    reward = [6500, 9000, 12500, 17000][self.selected_difficulty]
    if self.finish_position == 1:
        reward = int(reward * 1.5)
    self.credits += reward
    self.last_reward = reward
    self.state = "finished"
    self.draw_finish()


ApexVelocity.finish_race = av3_finish_race


def av3_draw_finish(self):
    self.menu_buttons = []
    self.canvas.delete("all")
    w, h = self.size()
    self.draw_background(w, h)
    self.canvas.create_rectangle(0, 0, w, h, fill="#020914", stipple="gray50", outline="")
    self.rounded_panel(w/2-280, h/2-205, w/2+280, h/2+205, "#081827", "#36536d")
    self.text(w/2, h/2-150, TRACKS[self.selected_track]["name"], 12, "#52e5ff", "bold")
    title = "VITÓRIA!" if self.finish_position == 1 else "CORRIDA FINALIZADA"
    self.text(w/2, h/2-92, title, 34, "#ffffff", "bold")
    self.text(w/2, h/2-42, "Você cruzou a linha de chegada.", 13, "#b9c8d9")
    self.text(w/2, h/2+12, format_time(self.elapsed), 32, "#52e5ff", "bold")
    self.text(w/2, h/2+57, f"Posição: {ordinal(self.finish_position)} de 8  ·  {DIFFICULTIES[self.selected_difficulty]['name']}",
              12, "#e7f3ff")
    self.text(w/2, h/2+91, f"RECOMPENSA: +{getattr(self, 'last_reward', 0):,} CR  ·  SALDO: {self.credits:,} CR".replace(",", "."),
              11, "#f2d27a", "bold")
    self.button(int(w/2-205), int(h/2+122), int(w/2+205), int(h/2+165), "CORRER NOVAMENTE", self.start_race, True)
    self.button(int(w/2-205), int(h/2+171), int(w/2+205), int(h/2+213), "VOLTAR À GARAGEM", self.draw_menu, False)


ApexVelocity.draw_finish = av3_draw_finish


if __name__ == "__main__":
    ApexVelocity().run()
