"""APEX VELOCITY 4.0 — jogo arcade de corrida 3D em Python/Ursina.

Execute com: python apex_velocity_3d.py
Controles: W/S acelerar/frear, A/D esterçar, SHIFT nitro (veículos especiais),
ESPAÇO freio de mão, C alterna câmera, ESC pausa.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from ursina import *
from ursina.shaders import lit_with_shadows_shader

from apex_core import (
    BIKES, CARS, DIFFICULTIES, LAPS_TO_WIN, PAINTS, ROAD_WIDTH, TRACKS,
    UPGRADE_BASE_COST, UPGRADE_NAMES, VEHICLES, build_track_path,
    calculate_stats, nearest_track_point, sample_track, upgrade_cost,
)

BASE_DIR = Path(__file__).resolve().parent
SAVE_FILE = BASE_DIR / "apex_save.json"


def c32(rgb: tuple[int, int, int], alpha: int = 255):
    return color.rgba32(rgb[0], rgb[1], rgb[2], alpha)


def vec2_distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ApexVelocity3D:
    def __init__(self):
        self.app = Ursina(title="Apex Velocity 4.0 | 3D Motorsport", borderless=False, fullscreen=False)
        window.size = (1440, 900)
        window.position = (40, 35)
        window.title = "APEX VELOCITY 4.0 — 3D MOTORSPORT"
        window.color = color.rgb32(7, 12, 23)
        window.exit_button.visible = False
        try:
            window.fps_counter.enabled = True
        except AttributeError:
            pass

        self.state = "menu"
        self.world_root = None
        self.ui_items: list = []
        self.preview = None
        self.player_visual = None
        self.opponents: list[dict] = []
        self.track_path = None
        self.track_index = 0
        self.difficulty_index = 1
        self.vehicle_kind = "car"
        self.vehicle_index = 0
        self.selected_vehicle_id = CARS[0]["id"]
        self.paint_names = ["AZUL", "VERMELHO", "ROXO", "VERDE", "CHOCOLATE", "DOURADO", "BRANCO", "PRETO", "ROSA", "MENTA", "LARANJA", "AZUL ROYAL"]

        self.save = self.load_save()
        self.credits = self.save["credits"]
        self.upgrades = self.save["upgrades"]
        self.cosmetics = self.save["cosmetics"]

        self.player_speed = 0.0
        self.player_yaw = 0.0
        self.player_lateral = 0.0
        self.player_laps = 0
        self.last_track_index = 0
        self.player_progress = 0.0
        self.race_time = 0.0
        self.race_position = 1
        self.nitro_remaining = 0.0
        self.nitro_active = False
        self.collision_cooldown = 0.0
        self.impact_flash = 0.0
        self.impact_text = ""
        self.camera_mode = 0
        self.camera_shake = 0.0
        self.finish_reward = 0
        self.hud: dict[str, Text] = {}

        self.setup_lighting()
        self.show_menu()
        global game
        game = self
        self.app.run()

    # ---------- Save e dados ----------
    def load_save(self) -> dict:
        from apex_core import normalize_save, fresh_save
        try:
            return normalize_save(json.loads(SAVE_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return fresh_save()

    def save_game(self):
        self.save = {"credits": self.credits, "upgrades": self.upgrades, "cosmetics": self.cosmetics}
        try:
            SAVE_FILE.write_text(json.dumps(self.save, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def selected_vehicle(self) -> dict:
        pool = CARS if self.vehicle_kind == "car" else BIKES
        self.vehicle_index = max(0, min(self.vehicle_index, len(pool) - 1))
        vehicle = pool[self.vehicle_index]
        self.selected_vehicle_id = vehicle["id"]
        return vehicle

    def current_upgrades(self, vehicle_id: str | None = None) -> dict[str, int]:
        key = vehicle_id or self.selected_vehicle()["id"]
        data = self.upgrades.get(key, {})
        return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def current_cosmetics(self, vehicle_id: str | None = None) -> dict:
        key = vehicle_id or self.selected_vehicle()["id"]
        default = {"paint": None, "widebody": False, "spoiler": False, "neon": False, "lowered": False, "rim": 0}
        stored = self.cosmetics.get(key, {})
        if isinstance(stored, dict):
            default.update(stored)
        return default

    def stats_for(self, vehicle: dict) -> dict[str, float]:
        return calculate_stats(vehicle, self.current_upgrades(vehicle["id"]))

    # ---------- Cena e iluminação ----------
    def setup_lighting(self):
        self.sky = Sky()
        self.sun = DirectionalLight(parent=scene, shadows=True, rotation=(48, -42, 28))
        self.sun.look_at(Vec3(1, -1, -1))
        self.ambient = AmbientLight(parent=scene, color=color.rgba32(105, 112, 132, 255))

    def clear_world(self):
        if self.world_root is not None:
            destroy(self.world_root)
        self.world_root = Entity()
        self.preview = None
        self.player_visual = None
        self.opponents = []

    def clear_ui(self):
        for item in self.ui_items:
            try:
                destroy(item)
            except Exception:
                pass
        self.ui_items = []
        self.hud = {}

    def ui_text(self, text: str, position, scale=1.0, tint=color.white, origin=(0, 0), parent=None):
        obj = Text(text=text, parent=parent or camera.ui, position=position, scale=scale, color=tint, origin=origin)
        self.ui_items.append(obj)
        return obj

    def ui_panel(self, position, scale, tint=None):
        panel = Entity(parent=camera.ui, model="quad", position=position, scale=scale,
                       color=tint or color.rgba32(8, 16, 29, 218), z=0.08)
        self.ui_items.append(panel)
        return panel

    def ui_button(self, text: str, position, callback, scale=(0.24, 0.062), tint=None, text_scale=0.72):
        button = Button(parent=camera.ui, text=text, position=position, scale=scale,
                        color=tint or color.rgb32(25, 43, 62), highlight_color=color.rgb32(40, 84, 108),
                        pressed_color=color.rgb32(15, 130, 155), text_color=color.white, text_size=text_scale)
        button.on_click = callback
        self.ui_items.append(button)
        return button

    def set_camera_for_showroom(self, look_at=(-3, 1.0, 0)):
        camera.position = (0, 7.0, -23)
        camera.look_at(Vec3(*look_at))
        camera.fov = 68

    def create_platform(self, center=(-3.5, 0, 0), accent=color.azure):
        Entity(parent=self.world_root, model="cube", scale=(500, 0.25, 500), position=(0, -0.85, 0), color=color.rgb32(23, 31, 42), shader=lit_with_shadows_shader)
        Entity(parent=self.world_root, model="cylinder", position=center, scale=(13, 0.65, 13), color=color.rgb32(37, 49, 63), shader=lit_with_shadows_shader)
        Entity(parent=self.world_root, model="cylinder", position=(center[0], 0.35, center[2]), scale=(11.9, 0.12, 11.9), color=accent)
        Entity(parent=self.world_root, model="cylinder", position=(center[0], 0.44, center[2]), scale=(10.9, 0.08, 10.9), color=color.rgb32(14, 21, 31))
        for i in range(24):
            a = i * math.tau / 24
            x = center[0] + math.cos(a) * 11.5
            z = center[2] + math.sin(a) * 11.5
            Entity(parent=self.world_root, model="cube", position=(x, 0.48, z), scale=(0.45, 0.12, 0.8), rotation_y=-math.degrees(a), color=accent)

    # ---------- Modelos 3D procedurais ----------
    def create_vehicle_model(self, vehicle: dict, customization: dict | None = None, parent=None):
        customization = customization or {"paint": None, "widebody": False, "spoiler": False, "neon": False, "lowered": False, "rim": 0}
        root = Entity(parent=parent or self.world_root, position=(0, 0, 0))
        root.scale = vehicle.get("scale", 1.0)
        paint_index = customization.get("paint")
        paint = PAINTS[paint_index] if isinstance(paint_index, int) and 0 <= paint_index < len(PAINTS) else vehicle["color"]
        body_color = c32(paint)
        wheels = []
        flames = []
        neon_entities = []

        if vehicle["kind"] == "car":
            lowered = bool(customization.get("lowered"))
            y_shift = -0.10 if lowered else 0.0
            # Chassi e carroceria em vários volumes, para evitar aparência de um bloco único.
            Entity(parent=root, model="cube", position=(0, 0.42 + y_shift, 0), scale=(1.92, 0.36, 4.15), color=color.rgb32(21, 24, 31), shader=lit_with_shadows_shader)
            Entity(parent=root, model="cube", position=(0, 0.70 + y_shift, -0.05), scale=(2.06, 0.48, 3.95), color=body_color, shader=lit_with_shadows_shader)
            Entity(parent=root, model="cube", position=(0, 0.84 + y_shift, 1.30), scale=(1.96, 0.20, 1.18), color=body_color)
            Entity(parent=root, model="cube", position=(0, 0.82 + y_shift, -1.47), scale=(1.96, 0.22, 0.92), color=body_color)
            # Cabine e vidros escuros.
            Entity(parent=root, model="cube", position=(0, 1.15 + y_shift, -0.20), scale=(1.52, 0.69, 1.85), color=color.rgb32(24, 38, 52), shader=lit_with_shadows_shader)
            Entity(parent=root, model="cube", position=(0, 1.51 + y_shift, -0.20), scale=(1.36, 0.10, 1.58), color=color.rgb32(42, 54, 67))
            Entity(parent=root, model="cube", position=(0, 1.15 + y_shift, 0.78), scale=(1.38, 0.46, 0.08), color=color.rgb32(75, 107, 126))
            Entity(parent=root, model="cube", position=(0, 1.12 + y_shift, -1.13), scale=(1.36, 0.44, 0.08), color=color.rgb32(50, 76, 92))
            # Para-brisa lateral, entradas de ar e detalhes frontais.
            for side in (-1, 1):
                Entity(parent=root, model="cube", position=(side * 0.78, 0.98 + y_shift, -0.2), scale=(0.06, 0.43, 1.35), color=color.rgb32(33, 57, 72))
                Entity(parent=root, model="cube", position=(side * 0.94, 0.56 + y_shift, 0), scale=(0.12, 0.16, 2.5), color=color.rgb32(18, 22, 29))
                Entity(parent=root, model="cube", position=(side * 0.67, 0.68 + y_shift, 2.00), scale=(0.48, 0.12, 0.10), color=color.rgb32(240, 239, 208))
                Entity(parent=root, model="cube", position=(side * 0.68, 0.65 + y_shift, -2.00), scale=(0.46, 0.14, 0.10), color=color.rgb32(224, 46, 41))
                Entity(parent=root, model="cube", position=(side * 1.02, 0.57 + y_shift, 1.10), scale=(0.16, 0.34, 1.0), color=body_color)
                for z in (-1.30, 1.28):
                    wheel = Entity(parent=root, model="cylinder", position=(side * 1.01, 0.46 + y_shift, z), scale=(0.76, 0.30, 0.76), rotation=(0, 0, 90), color=color.rgb32(15, 17, 20), shader=lit_with_shadows_shader)
                    wheels.append(wheel)
                    Entity(parent=root, model="cylinder", position=(side * 1.18, 0.46 + y_shift, z), scale=(0.43, 0.315, 0.43), rotation=(0, 0, 90), color=color.rgb32(158, 170, 181))
                    Entity(parent=root, model="cylinder", position=(side * 1.205, 0.46 + y_shift, z), scale=(0.16, 0.32, 0.16), rotation=(0, 0, 90), color=color.rgb32(47, 54, 63))
                if customization.get("widebody"):
                    for z in (-1.30, 1.28):
                        Entity(parent=root, model="cube", position=(side * 1.07, 0.77 + y_shift, z), scale=(0.34, 0.48, 1.05), color=body_color)
            # Spoiler opcional.
            if customization.get("spoiler") or vehicle["id"] in ("vortex_r", "apex_rr1000"):
                for side in (-0.62, 0.62):
                    Entity(parent=root, model="cube", position=(side, 1.04 + y_shift, -1.82), scale=(0.10, 0.48, 0.10), color=color.rgb32(22, 25, 30))
                Entity(parent=root, model="cube", position=(0, 1.30 + y_shift, -1.90), scale=(1.75, 0.12, 0.48), color=color.rgb32(24, 28, 34))
            # Detalhes das edições especiais.
            if vehicle["id"] == "neymar_10":
                Entity(parent=root, model="cube", position=(0, 0.965 + y_shift, 0.35), scale=(0.20, 0.025, 2.55), color=color.rgb32(245, 211, 42))
                for side in (-0.53, 0.53):
                    Entity(parent=root, model="cube", position=(side, 0.965 + y_shift, 0.35), scale=(0.08, 0.028, 2.55), color=color.rgb32(245, 211, 42))
                Text(parent=root, text="NEYMAR 10", position=(-0.56, 1.66 + y_shift, -0.58), rotation=(90, 0, 0), scale=3.4, color=color.rgb32(255, 226, 76))
                Entity(parent=root, model="cube", position=(0, 1.62 + y_shift, -0.18), scale=(0.88, 0.05, 0.42), color=color.rgb32(20, 145, 74))
            if vehicle["id"] == "conguitos_xl":
                Entity(parent=root, model="cube", position=(0, 1.44 + y_shift, -0.12), scale=(1.65, 0.09, 1.75), color=color.rgb32(107, 59, 33))
                Text(parent=root, text="CONGUITOS", position=(-0.84, 1.73 + y_shift, -1.58), rotation=(90, 0, 0), scale=3.0, color=color.rgb32(250, 211, 126))
                # Grande adesivo traseiro visível quando o carro é visto de trás.
                Entity(parent=root, model="cube", position=(0, 1.08 + y_shift, -2.04), scale=(1.40, 0.42, 0.05), color=color.rgb32(244, 209, 122))
                Text(parent=root, text="CONGUITOS", position=(-0.75, 1.25 + y_shift, -2.075), rotation=(0, 180, 0), scale=2.2, color=color.rgb32(73, 39, 22))
            # Neon e escapes.
            if customization.get("neon"):
                for side in (-0.75, 0.75):
                    neon = Entity(parent=root, model="cube", position=(side, 0.27 + y_shift, 0), scale=(0.08, 0.045, 2.9), color=color.rgba32(35, 182, 255, 210))
                    neon_entities.append(neon)
            for side in (-0.45, 0.45):
                Entity(parent=root, model="cylinder", position=(side, 0.50 + y_shift, -2.08), scale=(0.18, 0.24, 0.18), rotation=(90, 0, 0), color=color.rgb32(105, 113, 124))
            # Chamas de nitro, invisíveis até ativação.
            for side in (-0.42, 0.42):
                flame = Entity(parent=root, model="cone", position=(side, 0.50 + y_shift, -2.42), rotation=(90, 0, 0), scale=(0.34, 0.95, 0.34), color=color.rgb32(255, 126, 24), enabled=False)
                flames.append(flame)
        else:
            # Moto com rodas, pneus, tanque, assento, garfo dianteiro e guidão.
            if customization.get("lowered"):
                root.scale_y *= 0.96
            for z in (-1.03, 1.10):
                wheel = Entity(parent=root, model="cylinder", position=(0, 0.50, z), scale=(0.92, 0.22, 0.92), rotation=(0, 0, 90), color=color.rgb32(12, 15, 19), shader=lit_with_shadows_shader)
                wheels.append(wheel)
                Entity(parent=root, model="cylinder", position=(0.0, 0.50, z), scale=(0.46, 0.24, 0.46), rotation=(0, 0, 90), color=color.rgb32(155, 164, 172))
            Entity(parent=root, model="cube", position=(0, 0.87, -0.03), scale=(0.28, 0.48, 1.95), rotation=(0, 0, 0), color=color.rgb32(34, 37, 42))
            Entity(parent=root, model="sphere", position=(0, 1.07, 0.20), scale=(0.88, 0.55, 0.98), color=body_color, shader=lit_with_shadows_shader)
            Entity(parent=root, model="cube", position=(0, 1.32, -0.43), scale=(0.64, 0.20, 0.75), color=color.rgb32(28, 31, 37))
            Entity(parent=root, model="cube", position=(0, 0.92, 0.85), scale=(0.32, 0.66, 0.22), rotation=(0, 0, -13), color=color.rgb32(156, 167, 180))
            Entity(parent=root, model="cube", position=(0, 0.92, -0.84), scale=(0.32, 0.58, 0.22), rotation=(0, 0, 13), color=color.rgb32(156, 167, 180))
            Entity(parent=root, model="cube", position=(0, 1.40, 0.93), scale=(0.85, 0.12, 0.13), color=color.rgb32(39, 43, 49))
            Entity(parent=root, model="sphere", position=(0, 1.14, 1.10), scale=(0.35, 0.26, 0.16), color=color.rgb32(250, 235, 180))
            Entity(parent=root, model="cube", position=(0, 0.80, -1.18), scale=(0.50, 0.12, 0.18), color=color.rgb32(220, 47, 42))
            if customization.get("widebody"):
                for side in (-1, 1):
                    Entity(parent=root, model="cube", position=(side * 0.34, 0.96, 0.10), scale=(0.22, 0.40, 0.95), color=body_color)
            if customization.get("spoiler"):
                Entity(parent=root, model="cube", position=(0, 1.32, -0.88), scale=(0.95, 0.10, 0.25), color=color.rgb32(28, 31, 38))
            if customization.get("neon"):
                neon_entities.append(Entity(parent=root, model="cube", position=(0, 0.30, 0), scale=(0.08, 0.06, 1.1), color=color.rgba32(35, 182, 255, 210)))
            flame = Entity(parent=root, model="cone", position=(0, 0.62, -1.45), rotation=(90, 0, 0), scale=(0.30, 0.85, 0.30), color=color.rgb32(255, 126, 24), enabled=False)
            flames.append(flame)

        return {"root": root, "wheels": wheels, "flames": flames, "neon": neon_entities, "kind": vehicle["kind"]}

    # ---------- Menu principal e garagem ----------
    def show_menu(self):
        self.state = "menu"
        self.clear_ui()
        self.clear_world()
        self.create_platform(accent=color.rgb32(28, 191, 221))
        vehicle = self.selected_vehicle()
        custom = self.current_cosmetics(vehicle["id"])
        self.preview = self.create_vehicle_model(vehicle, custom, parent=self.world_root)
        self.preview["root"].position = (-3.7, 0.42, 0)
        self.preview["root"].rotation_y = 28
        self.set_camera_for_showroom(look_at=(-3.0, 1.1, 0))

        self.ui_panel((0.52, 0, 0.01), (0.72, 1.70), color.rgba32(5, 12, 24, 226))
        self.ui_text("APEX VELOCITY", (0.55, 0.39), scale=2.0, tint=color.rgb32(72, 222, 245))
        self.ui_text("3D MOTORSPORT  •  CARROS & MOTOS", (0.55, 0.315), scale=0.76, tint=color.rgb32(197, 211, 225))
        self.ui_text(f"VEÍCULO: {vehicle['name']}", (0.55, 0.20), scale=1.0, tint=color.white)
        self.ui_button("VEÍCULO ANTERIOR", (0.30, 0.105), self.previous_vehicle, scale=(0.28, 0.055))
        self.ui_button("PRÓXIMO VEÍCULO", (0.69, 0.105), self.next_vehicle, scale=(0.28, 0.055))
        self.ui_button(f"PISTA: {TRACKS[self.track_index]['name']}", (0.55, -0.005), self.next_track, scale=(0.55, 0.06), tint=color.rgb32(35, 66, 84))
        self.ui_button(f"DIFICULDADE: {DIFFICULTIES[self.difficulty_index]['name']}", (0.55, -0.09), self.next_difficulty, scale=(0.55, 0.06), tint=color.rgb32(35, 66, 84))
        self.ui_button("INICIAR CORRIDA", (0.55, -0.215), self.start_race, scale=(0.55, 0.085), tint=color.rgb32(8, 139, 160), text_scale=0.9)
        self.ui_button("GARAGEM / OFICINA", (0.55, -0.325), self.show_garage, scale=(0.55, 0.07), tint=color.rgb32(37, 57, 80))
        self.ui_button("SAIR", (0.55, -0.425), application.quit, scale=(0.55, 0.055), tint=color.rgb32(75, 39, 47))
        self.ui_text(f"CRÉDITOS  $ {self.credits:,}".replace(",", "."), (0.55, -0.50), scale=0.75, tint=color.rgb32(255, 220, 110))
        self.ui_text("WASD dirigir  •  SHIFT nitro especial  •  C câmera  •  ESC pausa", (0, -0.475), scale=0.68, tint=color.rgb32(177, 194, 210))

    def cycle_vehicle(self, delta: int):
        pool = CARS if self.vehicle_kind == "car" else BIKES
        self.vehicle_index = (self.vehicle_index + delta) % len(pool)
        self.show_menu()

    def previous_vehicle(self):
        self.cycle_vehicle(-1)

    def next_vehicle(self):
        self.cycle_vehicle(1)

    def next_track(self):
        self.track_index = (self.track_index + 1) % len(TRACKS)
        self.show_menu()

    def next_difficulty(self):
        self.difficulty_index = (self.difficulty_index + 1) % len(DIFFICULTIES)
        self.show_menu()

    def show_garage(self):
        self.state = "garage"
        self.clear_ui()
        self.clear_world()
        vehicle = self.selected_vehicle()
        track = TRACKS[self.track_index]
        self.create_platform(accent=c32(track["accent"]))
        self.preview = self.create_vehicle_model(vehicle, self.current_cosmetics(vehicle["id"]), parent=self.world_root)
        self.preview["root"].position = (-3.7, 0.42, 0)
        self.preview["root"].rotation_y = 28
        self.set_camera_for_showroom(look_at=(-3.0, 1.0, 0))

        stats = self.stats_for(vehicle)
        cosmetics = self.current_cosmetics(vehicle["id"])
        self.ui_panel((0.53, 0, 0.01), (0.72, 0.96), color.rgba32(5, 12, 24, 234))
        self.ui_button("← MENU", (0.20, 0.43), self.show_menu, scale=(0.18, 0.05), tint=color.rgb32(70, 47, 51), text_scale=0.62)
        self.ui_text("GARAGEM  /  PERSONALIZAÇÃO", (0.55, 0.43), scale=1.15, tint=color.rgb32(72, 222, 245))
        self.ui_text(f"CRÉDITOS  $ {self.credits:,}".replace(",", "."), (0.55, 0.365), scale=0.72, tint=color.rgb32(255, 220, 110))
        self.ui_button("CARROS", (0.35, 0.285), lambda: self.change_category("car"), scale=(0.22, 0.05), tint=color.rgb32(15, 119, 145) if self.vehicle_kind == "car" else None)
        self.ui_button("MOTOS", (0.70, 0.285), lambda: self.change_category("bike"), scale=(0.22, 0.05), tint=color.rgb32(15, 119, 145) if self.vehicle_kind == "bike" else None)
        self.ui_button("◀ ANTERIOR", (0.35, 0.215), lambda: self.garage_cycle(-1), scale=(0.22, 0.05))
        self.ui_button("PRÓXIMO ▶", (0.70, 0.215), lambda: self.garage_cycle(1), scale=(0.22, 0.05))
        self.ui_text(f"{vehicle['name']}  |  {vehicle['description']}", (0.55, 0.145), scale=0.76, tint=color.white)
        stat_line = f"VEL. {stats['top_speed']:.0f} km/h   ACEL. {stats['acceleration']:.0f}   ADER. {stats['handling']:.2f}   FREIO {stats['braking']:.2f}"
        self.ui_text(stat_line, (0.55, 0.09), scale=0.56, tint=color.rgb32(174, 202, 222))
        self.ui_text("ESTÉTICA", (0.55, 0.015), scale=0.80, tint=color.rgb32(255, 213, 100))
        paint_label = self.paint_names[(cosmetics.get("paint") or 0) % len(self.paint_names)] if cosmetics.get("paint") is not None else "ORIGINAL"
        self.ui_button(f"PINTURA: {paint_label}", (0.36, -0.065), self.cycle_paint, scale=(0.31, 0.05), text_scale=0.62)
        self.ui_button(f"WIDEBODY: {'ON' if cosmetics.get('widebody') else 'OFF'}", (0.70, -0.065), self.toggle_widebody, scale=(0.31, 0.05), text_scale=0.62)
        self.ui_button(f"AEROFÓLIO: {'ON' if cosmetics.get('spoiler') else 'OFF'}", (0.36, -0.13), self.toggle_spoiler, scale=(0.31, 0.05), text_scale=0.62)
        self.ui_button(f"NEON: {'ON' if cosmetics.get('neon') else 'OFF'}", (0.70, -0.13), self.toggle_neon, scale=(0.31, 0.05), text_scale=0.62)
        self.ui_button(f"SUSPENSÃO BAIXA: {'ON' if cosmetics.get('lowered') else 'OFF'}", (0.53, -0.195), self.toggle_lowered, scale=(0.48, 0.05), text_scale=0.62)
        self.ui_button("OFICINA  •  UPGRADES DE DESEMPENHO", (0.53, -0.30), self.show_workshop, scale=(0.56, 0.07), tint=color.rgb32(8, 139, 160), text_scale=0.70)
        self.ui_text("Pinte, alargue a carroceria, troque o visual e prepare seu veículo.", (0.53, -0.405), scale=0.59, tint=color.rgb32(177, 194, 210))

    def show_workshop(self):
        self.state = "garage"
        self.clear_ui()
        self.clear_world()
        vehicle = self.selected_vehicle()
        self.create_platform(accent=color.rgb32(255, 194, 72))
        self.preview = self.create_vehicle_model(vehicle, self.current_cosmetics(vehicle["id"]), parent=self.world_root)
        self.preview["root"].position = (-3.7, 0.42, 0)
        self.preview["root"].rotation_y = 28
        self.set_camera_for_showroom(look_at=(-3.0, 1.0, 0))
        stats = self.stats_for(vehicle)
        levels = self.current_upgrades(vehicle["id"])
        self.ui_panel((0.53, 0, 0.01), (0.72, 0.96), color.rgba32(5, 12, 24, 236))
        self.ui_button("← GARAGEM", (0.22, 0.43), self.show_garage, scale=(0.20, 0.05), tint=color.rgb32(70, 47, 51), text_scale=0.62)
        self.ui_text("OFICINA  /  DESEMPENHO", (0.56, 0.43), scale=1.15, tint=color.rgb32(255, 205, 84))
        self.ui_text(f"{vehicle['name']}     CRÉDITOS: $ {self.credits:,}".replace(",", "."), (0.55, 0.34), scale=0.72, tint=color.white)
        self.ui_text(f"VEL. {stats['top_speed']:.0f} km/h     ACEL. {stats['acceleration']:.1f}     ADER. {stats['handling']:.2f}     FREIO {stats['braking']:.2f}", (0.55, 0.265), scale=0.62, tint=color.rgb32(174, 202, 222))
        self.ui_text("ESCOLHA UMA PEÇA PARA COMPRAR O PRÓXIMO NÍVEL", (0.55, 0.18), scale=0.65, tint=color.rgb32(255, 213, 100))
        items = ["engine", "turbo", "gearbox", "brakes", "tires", "suspension", "exhaust", "nitro"]
        xs = (0.35, 0.70)
        ys = (0.09, 0.01, -0.07, -0.15)
        for i, item in enumerate(items):
            col = i % 2
            row = i // 2
            level = levels.get(item, 0)
            cost = upgrade_cost(item, level) if level < 5 else 0
            label = f"{UPGRADE_NAMES[item].upper()}  {level}/5" + (f"  ${cost:,}".replace(",", ".") if level < 5 else "  MAX")
            if item == "nitro" and not vehicle.get("nitro_speed"):
                button = self.ui_button("NITRO  INDISPONÍVEL", (xs[col], ys[row]), lambda: None, scale=(0.32, 0.06), text_scale=0.62)
                button.disabled = True
            else:
                self.ui_button(label, (xs[col], ys[row]), lambda key=item: self.buy_upgrade(key), scale=(0.32, 0.06), text_scale=0.62)
        nitro_note = "Nitro melhora a carga/velocidade das edições Neymar 10 e Conguitos XL." if vehicle.get("nitro_speed") else "Este veículo não possui sistema de nitro especial; os demais upgrades continuam disponíveis."
        self.ui_text(nitro_note, (0.55, -0.255), scale=0.60, tint=color.rgb32(185, 199, 211))
        self.ui_button("VOLTAR À GARAGEM", (0.55, -0.37), self.show_garage, scale=(0.42, 0.065), tint=color.rgb32(8, 128, 149))

    def change_category(self, kind: str):
        self.vehicle_kind = kind
        self.vehicle_index = 0
        self.show_garage()

    def garage_cycle(self, delta: int):
        pool = CARS if self.vehicle_kind == "car" else BIKES
        self.vehicle_index = (self.vehicle_index + delta) % len(pool)
        self.show_garage()

    def update_cosmetic(self, key: str, value):
        vehicle = self.selected_vehicle()
        custom = self.current_cosmetics(vehicle["id"])
        custom[key] = value
        self.cosmetics[vehicle["id"]] = custom
        self.save_game()
        self.show_garage()

    def cycle_paint(self):
        vehicle = self.selected_vehicle()
        custom = self.current_cosmetics(vehicle["id"])
        current = custom.get("paint")
        custom["paint"] = 0 if current is None else (int(current) + 1) % len(PAINTS)
        self.cosmetics[vehicle["id"]] = custom
        self.save_game()
        self.show_garage()

    def toggle_widebody(self):
        c = self.current_cosmetics(); self.update_cosmetic("widebody", not c.get("widebody", False))

    def toggle_spoiler(self):
        c = self.current_cosmetics(); self.update_cosmetic("spoiler", not c.get("spoiler", False))

    def toggle_neon(self):
        c = self.current_cosmetics(); self.update_cosmetic("neon", not c.get("neon", False))

    def toggle_lowered(self):
        c = self.current_cosmetics(); self.update_cosmetic("lowered", not c.get("lowered", False))

    def buy_upgrade(self, item: str):
        vehicle = self.selected_vehicle()
        if item == "nitro" and not vehicle.get("nitro_speed"):
            return
        levels = self.current_upgrades(vehicle["id"])
        level = levels.get(item, 0)
        if level >= 5:
            return
        cost = upgrade_cost(item, level)
        if self.credits < cost:
            self.show_insufficient_credits()
            return
        self.credits -= cost
        levels[item] = level + 1
        self.upgrades[vehicle["id"]] = levels
        self.save_game()
        self.show_garage()

    def show_insufficient_credits(self):
        # Retorno visual curto, sem interromper a tela da oficina.
        self.ui_text("CRÉDITOS INSUFICIENTES", (0.55, -0.44), scale=0.8, tint=color.rgb32(255, 104, 104))

    # ---------- Construção das pistas 3D ----------
    def add_strip_mesh(self, points, offset_a: float, offset_b: float, y: float, tint):
        verts = []
        tris = []
        n = len(points)
        for i, (x, z) in enumerate(points):
            px, pz = points[(i - 1) % n]
            nx, nz = points[(i + 1) % n]
            tx, tz = nx - px, nz - pz
            length = math.hypot(tx, tz) or 1.0
            nxv, nzv = -tz / length, tx / length
            verts.append(Vec3(x + nxv * offset_a, y, z + nzv * offset_a))
            verts.append(Vec3(x + nxv * offset_b, y, z + nzv * offset_b))
        for i in range(n):
            a = i * 2
            b = ((i + 1) % n) * 2
            tris.extend([(a, a + 1, b), (a + 1, b + 1, b)])
        mesh = Mesh(vertices=verts, triangles=tris, static=True)
        mesh.generate_normals()
        Entity(parent=self.world_root, model=mesh, color=tint, double_sided=True, shader=lit_with_shadows_shader)

    def build_track(self):
        track = TRACKS[self.track_index]
        self.track_path = build_track_path(self.track_index)
        points = self.track_path.points
        ground = c32(track["ground"])
        Entity(parent=self.world_root, model="cube", scale=(520, 0.25, 520), position=(0, -0.45, 0), color=ground, shader=lit_with_shadows_shader)
        # Faixa externa, pista, bordas e linhas: as curvas são construídas com a geometria do centro da pista.
        self.add_strip_mesh(points, -ROAD_WIDTH / 2 - 1.4, ROAD_WIDTH / 2 + 1.4, -0.02, color.rgb32(105, 108, 111))
        self.add_strip_mesh(points, -ROAD_WIDTH / 2, ROAD_WIDTH / 2, 0.015, c32(track["road"]))
        self.add_strip_mesh(points, -ROAD_WIDTH / 2 + 0.25, -ROAD_WIDTH / 2 + 0.55, 0.035, color.rgb32(235, 238, 239))
        self.add_strip_mesh(points, ROAD_WIDTH / 2 - 0.55, ROAD_WIDTH / 2 - 0.25, 0.035, color.rgb32(235, 238, 239))
        # Linha central tracejada.
        for i in range(0, len(points), 14):
            x, z = points[i]
            nx, nz = points[(i + 1) % len(points)]
            yaw = math.degrees(math.atan2(nx - x, nz - z))
            Entity(parent=self.world_root, model="cube", position=(x, 0.055, z), rotation_y=yaw,
                   scale=(0.13, 0.035, 2.2), color=color.rgb32(235, 210, 112))
        # Zebras alternadas nas bordas.
        for i in range(0, len(points), 7):
            x, z = points[i]
            px, pz = points[(i - 1) % len(points)]
            nx, nz = points[(i + 1) % len(points)]
            tx, tz = nx - px, nz - pz
            length = math.hypot(tx, tz) or 1.0
            normal = (-tz / length, tx / length)
            yaw = math.degrees(math.atan2(tx, tz))
            for side in (-1, 1):
                xx = x + normal[0] * side * (ROAD_WIDTH / 2 + 0.25)
                zz = z + normal[1] * side * (ROAD_WIDTH / 2 + 0.25)
                curb_color = color.rgb32(225, 52, 48) if (i // 7) % 2 == 0 else color.white
                Entity(parent=self.world_root, model="cube", position=(xx, 0.09, zz), rotation_y=yaw,
                       scale=(0.75, 0.16, 2.4), color=curb_color)
        # Linha de largada.
        x, z, yaw = sample_track(self.track_path, 0)
        Entity(parent=self.world_root, model="cube", position=(x, 0.075, z), rotation_y=yaw,
               scale=(ROAD_WIDTH, 0.04, 0.85), color=color.rgb32(235, 235, 235))
        for ix in range(12):
            for iz in range(2):
                xx = x - ROAD_WIDTH / 2 + (ix + 0.5) * ROAD_WIDTH / 12
                zz = z + (iz - 0.5) * 0.42
                if (ix + iz) % 2 == 0:
                    Entity(parent=self.world_root, model="cube", position=(xx, 0.105, zz), scale=(ROAD_WIDTH / 12, 0.025, 0.42), color=color.rgb32(23, 25, 30))
        self.build_scenery()

    def build_tree(self, x: float, z: float, scale: float, tint):
        Entity(parent=self.world_root, model="cylinder", position=(x, scale * 1.15, z), scale=(scale * 0.22, scale * 2.3, scale * 0.22), color=color.rgb32(102, 72, 48))
        Entity(parent=self.world_root, model="sphere", position=(x, scale * 2.55, z), scale=(scale * 1.45, scale * 1.55, scale * 1.45), color=tint)
        Entity(parent=self.world_root, model="sphere", position=(x + scale * 0.35, scale * 2.3, z + scale * 0.2), scale=(scale, scale * 1.15, scale), color=tint.tint(0.08))

    def build_scenery(self):
        track = TRACKS[self.track_index]
        rng = random.Random(self.track_index + 27)
        pts = self.track_path.points
        for i in range(0, len(pts), 10):
            x, z = pts[i]
            px, pz = pts[(i - 1) % len(pts)]
            nx, nz = pts[(i + 1) % len(pts)]
            dx, dz = nx - px, nz - pz
            length = math.hypot(dx, dz) or 1.0
            normal = (-dz / length, dx / length)
            for side in (-1, 1):
                offset = ROAD_WIDTH / 2 + rng.uniform(13, 29)
                sx = x + normal[0] * offset * side
                sz = z + normal[1] * offset * side
                if self.track_index in (0, 4):
                    self.build_tree(sx, sz, rng.uniform(1.6, 3.0), color.rgb32(47, 119, 68) if self.track_index == 4 else color.rgb32(39, 133, 83))
                elif self.track_index == 1:
                    Entity(parent=self.world_root, model="cone", position=(sx, 3.0, sz), scale=(rng.uniform(7, 13), rng.uniform(8, 17), rng.uniform(7, 13)), color=color.rgb32(197, 215, 224))
                    Entity(parent=self.world_root, model="cone", position=(sx, 5.4, sz), scale=(4.5, 8.0, 4.5), color=color.rgb32(235, 242, 245))
                elif self.track_index == 2:
                    h = rng.uniform(8, 22)
                    w = rng.uniform(5, 10)
                    building = Entity(parent=self.world_root, model="cube", position=(sx, h / 2, sz), scale=(w, h, w), color=color.rgb32(37, 45, 73), shader=lit_with_shadows_shader)
                    for floor in range(1, int(h / 3)):
                        Entity(parent=self.world_root, model="cube", position=(sx, floor * 3, sz + w / 2 + 0.03), scale=(w * 0.55, 0.28, 0.06), color=color.rgb32(75, 208, 222))
                elif self.track_index == 3:
                    Entity(parent=self.world_root, model="cone", position=(sx, 3.8, sz), scale=(rng.uniform(6, 11), rng.uniform(7, 13), rng.uniform(6, 11)), color=color.rgb32(164, 92, 60))
                    Entity(parent=self.world_root, model="cube", position=(sx, 0.8, sz), scale=(rng.uniform(4, 8), rng.uniform(1.5, 3.0), rng.uniform(3, 6)), rotation_y=rng.uniform(0, 180), color=color.rgb32(196, 132, 84))
        # Painéis e postes decorativos em torno de cada circuito.
        for i in range(0, len(pts), 45):
            x, z = pts[i]
            px, pz = pts[(i - 1) % len(pts)]
            nx, nz = pts[(i + 1) % len(pts)]
            dx, dz = nx - px, nz - pz
            length = math.hypot(dx, dz) or 1.0
            nxv, nzv = -dz / length, dx / length
            side = 1 if (i // 45) % 2 else -1
            sx, sz = x + nxv * side * 14.0, z + nzv * side * 14.0
            Entity(parent=self.world_root, model="cube", position=(sx, 2.6, sz), scale=(0.24, 5.2, 0.24), color=color.rgb32(45, 53, 62))
            Entity(parent=self.world_root, model="cube", position=(sx, 5.15, sz), scale=(4.5, 0.65, 0.22), rotation_y=math.degrees(math.atan2(dx, dz)), color=c32(track["accent"]))

    # ---------- Corrida ----------
    def start_race(self):
        self.state = "race"
        self.clear_ui()
        self.clear_world()
        self.build_track()
        vehicle = self.selected_vehicle()
        custom = self.current_cosmetics(vehicle["id"])
        self.player_visual = self.create_vehicle_model(vehicle, custom, parent=self.world_root)
        x, z, yaw = sample_track(self.track_path, 0)
        self.player_visual["root"].position = (x, -0.04, z)
        self.player_yaw = yaw
        self.player_visual["root"].rotation_y = yaw
        self.player_speed = 0.0
        self.player_laps = 0
        self.last_track_index = 0
        self.player_progress = 0.0
        self.race_time = 0.0
        self.collision_cooldown = 0.0
        self.impact_flash = 0.0
        self.nitro_remaining = float(vehicle.get("nitro_seconds", 0))
        self.nitro_active = False
        self.finish_reward = 0

        # Seis rivais com mistura de carros e motos.
        rng = random.Random(100 + self.track_index * 5 + self.difficulty_index)
        available = [v for v in VEHICLES if v["id"] != vehicle["id"]]
        difficulty = DIFFICULTIES[self.difficulty_index]
        for i in range(6):
            rival = rng.choice(available)
            visual = self.create_vehicle_model(rival, None, parent=self.world_root)
            progress = -14.0 * (i + 1)
            rx, rz, ryaw = sample_track(self.track_path, progress)
            visual["root"].position = (rx, -0.04, rz)
            visual["root"].rotation_y = ryaw
            base = rng.uniform(175, 258) * difficulty["ai_speed"]
            if rival["kind"] == "bike":
                base *= 1.03
            self.opponents.append({"vehicle": rival, "visual": visual, "progress": progress,
                                   "speed": base, "lane": rng.choice([-3.0, -1.3, 1.3, 3.0]),
                                   "offset": rng.uniform(-0.7, 0.7)})

        self.camera_mode = 0
        camera.position = self.player_visual["root"].position + Vec3(0, 7, -17)
        camera.look_at(self.player_visual["root"].position + Vec3(0, 1.5, 2))
        camera.fov = 82
        self.build_hud()

    def build_hud(self):
        self.ui_panel((-0.66, 0.405, 0.02), (0.40, 0.19), color.rgba32(5, 12, 24, 190))
        self.hud["position"] = self.ui_text("POSIÇÃO  1/7", (-0.82, 0.46), scale=0.85, tint=color.white, origin=(-0.5, 0))
        self.hud["lap"] = self.ui_text("VOLTA  1/3", (-0.82, 0.405), scale=0.80, tint=color.white, origin=(-0.5, 0))
        self.hud["time"] = self.ui_text("TEMPO  00:00.00", (-0.82, 0.35), scale=0.75, tint=color.white, origin=(-0.5, 0))
        self.ui_panel((-0.70, -0.405, 0.02), (0.34, 0.18), color.rgba32(5, 12, 24, 196))
        self.hud["speed"] = self.ui_text("000", (-0.82, -0.39), scale=2.25, tint=color.rgb32(85, 224, 245), origin=(-0.5, 0))
        self.hud["unit"] = self.ui_text("KM/H", (-0.62, -0.45), scale=0.65, tint=color.white, origin=(-0.5, 0))
        self.hud["nitro"] = self.ui_text("NITRO  —", (-0.82, -0.49), scale=0.68, tint=color.rgb32(255, 193, 73), origin=(-0.5, 0))
        self.hud["track"] = self.ui_text(TRACKS[self.track_index]["name"], (0, 0.47), scale=0.85, tint=color.white)
        self.hud["impact"] = self.ui_text("", (0, -0.30), scale=1.2, tint=color.rgb32(255, 110, 94))
        self.ui_text("WASD dirigir  •  ESPAÇO freio de mão  •  SHIFT nitro  •  C câmera  •  ESC pausa", (0, -0.485), scale=0.62, tint=color.rgb32(195, 207, 218))

    def update_player(self, dt: float):
        if not self.player_visual:
            return
        vehicle = self.selected_vehicle()
        stats = self.stats_for(vehicle)
        keys = held_keys
        throttle = keys["w"] + keys["up"]
        brake = keys["s"] + keys["down"]
        steer = keys["d"] + keys["right"] - keys["a"] - keys["left"]
        handbrake = keys["space"]
        using_nitro = bool(keys["shift"] and self.nitro_remaining > 0 and vehicle.get("nitro_speed"))
        self.nitro_active = using_nitro

        normal_max = stats["top_speed"]
        target_max = stats["nitro_speed"] if using_nitro else normal_max
        accel = stats["acceleration"]
        if throttle:
            self.player_speed += accel * dt
        else:
            self.player_speed -= 22.0 * dt
        if brake:
            self.player_speed -= 165.0 * stats["braking"] * dt
        if handbrake:
            self.player_speed -= 35.0 * dt
        if using_nitro:
            self.player_speed += (accel * 2.8 + 85.0) * dt
            self.nitro_remaining = max(0.0, self.nitro_remaining - dt)
        self.player_speed = clamp(self.player_speed, 0.0, target_max)

        # Física cinemática: a frente do veículo gira, e sua posição muda nessa direção.
        # Assim, sem esterçar, o jogador realmente sai de uma curva em vez de a pista deslizar.
        speed_factor = clamp(self.player_speed / 220.0, 0.12, 1.15)
        handling = stats["handling"] * (0.72 if handbrake else 1.0)
        turn_rate = (24.0 + 34.0 * speed_factor) * handling
        if vehicle["kind"] == "bike":
            turn_rate *= 1.12
        self.player_yaw += steer * turn_rate * dt
        self.player_visual["root"].rotation_y = self.player_yaw
        if vehicle["kind"] == "bike":
            self.player_visual["root"].rotation_z = -steer * min(28, self.player_speed * 0.10)
        else:
            self.player_visual["root"].rotation_z = -steer * (4.0 if handbrake else 1.7)

        yaw_rad = math.radians(self.player_yaw)
        forward = Vec3(math.sin(yaw_rad), 0, math.cos(yaw_rad))
        # Escala de mundo arcade. O velocímetro mostra o valor configurado,
        # enquanto o limite físico de deslocamento evita saltos de milhares de unidades.
        world_speed = min(self.player_speed, 760.0) * 0.047
        if handbrake:
            world_speed *= 0.82
        self.player_visual["root"].position += forward * world_speed * dt
        self.player_visual["root"].y = -0.04
        for wheel in self.player_visual["wheels"]:
            wheel.rotation_x += world_speed * dt * 120
        for flame in self.player_visual["flames"]:
            flame.enabled = self.nitro_active

        # Penalidade e recuperação ao sair da superfície asfaltada.
        px = self.player_visual["root"].x
        pz = self.player_visual["root"].z
        idx, distance, progress = nearest_track_point(self.track_path, px, pz)
        if distance > ROAD_WIDTH * 0.5 - 1.0:
            self.player_speed = max(0.0, self.player_speed - (22.0 + distance * 0.6) * dt)
            if distance > ROAD_WIDTH * 0.5 + 7:
                cx, cz, _ = sample_track(self.track_path, progress)
                correction = Vec3(cx - px, 0, cz - pz)
                if correction.length() > 0.001:
                    self.player_visual["root"].position += correction.normalized() * min(9 * dt, correction.length())

        # Contagem de voltas por passagem na linha de largada.
        count = len(self.track_path.points)
        if self.last_track_index > count * 0.78 and idx < count * 0.22:
            self.player_laps += 1
        elif self.last_track_index < count * 0.22 and idx > count * 0.78 and self.player_laps > 0:
            self.player_laps -= 1
        self.last_track_index = idx
        self.player_progress = self.player_laps * self.track_path.length + progress

    def update_opponents(self, dt: float):
        for opponent in self.opponents:
            # Velocidade varia suavemente para criar disputa de posições.
            desired = opponent["speed"] * 0.047
            opponent["progress"] += desired * dt
            x, z, yaw = sample_track(self.track_path, opponent["progress"])
            a = math.radians(yaw)
            normal = Vec3(-math.cos(a), 0, math.sin(a))
            lane = opponent["lane"] + math.sin(opponent["progress"] * 0.035) * opponent["offset"]
            root = opponent["visual"]["root"]
            root.position = Vec3(x, -0.04, z) + normal * lane
            root.rotation_y = yaw
            if opponent["vehicle"]["kind"] == "bike":
                root.rotation_z = math.sin(opponent["progress"] * 0.035) * 7
            for wheel in opponent["visual"]["wheels"]:
                wheel.rotation_x += desired * dt * 120

        # Colisões entre os próprios rivais: eles se afastam e perdem um pouco de progresso.
        for i in range(len(self.opponents)):
            for j in range(i + 1, len(self.opponents)):
                a = self.opponents[i]
                b = self.opponents[j]
                pa = a["visual"]["root"].position
                pb = b["visual"]["root"].position
                dist = math.hypot(pa.x - pb.x, pa.z - pb.z)
                if dist < 2.7:
                    sign = 1 if a["lane"] <= b["lane"] else -1
                    a["lane"] = clamp(a["lane"] - sign * 0.8, -5.5, 5.5)
                    b["lane"] = clamp(b["lane"] + sign * 0.8, -5.5, 5.5)
                    a["progress"] -= 0.45
                    b["progress"] -= 0.45

        # Colisões entre o veículo do jogador e os rivais.
        self.collision_cooldown = max(0.0, self.collision_cooldown - dt)
        if self.collision_cooldown <= 0 and self.player_visual:
            player_pos = self.player_visual["root"].position
            for opponent in self.opponents:
                other = opponent["visual"]["root"].position
                dist = math.hypot(player_pos.x - other.x, player_pos.z - other.z)
                radius = 2.35 if opponent["vehicle"]["kind"] == "bike" else 3.0
                if dist < radius:
                    away = Vec3(player_pos.x - other.x, 0, player_pos.z - other.z)
                    if away.length() < 0.001:
                        away = Vec3(1, 0, 0)
                    else:
                        away = away.normalized()
                    self.player_visual["root"].position += away * (radius - dist + 0.25)
                    self.player_speed *= 0.58
                    self.player_yaw += random.choice([-1, 1]) * 5.5
                    opponent["progress"] -= 2.4
                    self.collision_cooldown = 0.72
                    self.impact_flash = 0.42
                    self.impact_text = "COLISÃO!"
                    break

    def update_camera(self, dt: float):
        if not self.player_visual:
            return
        root = self.player_visual["root"]
        yaw = math.radians(self.player_yaw)
        forward = Vec3(math.sin(yaw), 0, math.cos(yaw))
        if self.camera_mode == 0:
            target = root.position - forward * 15 + Vec3(0, 6.7, 0)
            focus = root.position + forward * 5 + Vec3(0, 1.1, 0)
        else:
            target = root.position + Vec3(0, 2.45, 0) + forward * 0.6
            focus = root.position + forward * 14 + Vec3(0, 1.8, 0)
        camera.position += (target - camera.position) * min(1.0, dt * 5.5)
        camera.look_at(focus)
        camera.fov = 82 + min(self.player_speed / 95.0, 12)

    def update_hud(self, dt: float):
        if not self.hud:
            return
        total = self.player_laps * self.track_path.length + self.player_progress % self.track_path.length
        # Use progresso absoluto do veículo para comparar com os rivais.
        ranked = [(self.player_progress, "player")] + [(o["progress"], o) for o in self.opponents]
        ranked.sort(key=lambda item: item[0], reverse=True)
        self.race_position = next(i + 1 for i, item in enumerate(ranked) if item[1] == "player")
        self.hud["position"].text = f"POSIÇÃO  {self.race_position}/7"
        self.hud["lap"].text = f"VOLTA  {min(self.player_laps + 1, LAPS_TO_WIN)}/{LAPS_TO_WIN}"
        minutes = int(self.race_time // 60)
        seconds = self.race_time % 60
        self.hud["time"].text = f"TEMPO  {minutes:02d}:{seconds:05.2f}"
        self.hud["speed"].text = f"{int(self.player_speed):03d}"
        if self.nitro_remaining > 0:
            self.hud["nitro"].text = f"NITRO  {self.nitro_remaining:0.1f}s  (SHIFT)"
            self.hud["nitro"].color = color.rgb32(255, 194, 72)
        else:
            self.hud["nitro"].text = "NITRO  ESGOTADO" if self.selected_vehicle().get("nitro_speed") else "SEM NITRO"
            self.hud["nitro"].color = color.rgb32(175, 187, 199)
        if self.impact_flash > 0:
            self.impact_flash = max(0, self.impact_flash - dt)
            self.hud["impact"].text = self.impact_text
        else:
            self.hud["impact"].text = ""

    def finish_race(self):
        self.state = "finished"
        # Créditos por posição; valores do jogo, sem dinheiro real.
        rewards = {1: 26000, 2: 19000, 3: 14000, 4: 9000, 5: 6500, 6: 4000, 7: 2500}
        self.finish_reward = rewards.get(self.race_position, 2500)
        self.credits += self.finish_reward
        self.save_game()
        self.clear_ui()
        self.ui_panel((0, 0, 0.01), (1.0, 0.72), color.rgba32(5, 12, 24, 226))
        self.ui_text("CORRIDA FINALIZADA", (0, 0.23), scale=1.8, tint=color.rgb32(77, 220, 242))
        self.ui_text(f"POSIÇÃO FINAL: {self.race_position}º LUGAR", (0, 0.08), scale=1.15, tint=color.white)
        self.ui_text(f"RECOMPENSA: $ {self.finish_reward:,}".replace(",", "."), (0, -0.01), scale=1.0, tint=color.rgb32(255, 217, 101))
        self.ui_text(f"SALDO: $ {self.credits:,}".replace(",", "."), (0, -0.09), scale=0.85, tint=color.rgb32(190, 208, 220))
        self.ui_button("CORRER NOVAMENTE", (0, -0.22), self.start_race, scale=(0.38, 0.075), tint=color.rgb32(8, 135, 157))
        self.ui_button("MENU PRINCIPAL", (0, -0.33), self.show_menu, scale=(0.38, 0.065))

    # ---------- Pausa, entrada e atualização ----------
    def show_pause(self):
        self.state = "paused"
        self.clear_ui()
        self.ui_panel((0, 0, 0.01), (0.70, 0.68), color.rgba32(5, 12, 24, 236))
        self.ui_text("PAUSADO", (0, 0.18), scale=1.8, tint=color.rgb32(73, 220, 241))
        self.ui_text("ESC para continuar  •  C para alternar câmera", (0, 0.07), scale=0.76, tint=color.white)
        self.ui_button("CONTINUAR", (0, -0.06), self.resume_race, scale=(0.38, 0.07), tint=color.rgb32(8, 135, 157))
        self.ui_button("REINICIAR CORRIDA", (0, -0.17), self.start_race, scale=(0.38, 0.065))
        self.ui_button("VOLTAR AO MENU", (0, -0.28), self.show_menu, scale=(0.38, 0.065), tint=color.rgb32(70, 47, 51))

    def resume_race(self):
        self.state = "race"
        self.clear_ui()
        self.build_hud()

    def input(self, key):
        if key == "escape":
            if self.state == "race":
                self.show_pause()
            elif self.state == "paused":
                self.resume_race()
            return
        if self.state == "race" and key == "c":
            self.camera_mode = (self.camera_mode + 1) % 2
        if self.state == "race" and key == "r":
            self.start_race()

    def update(self):
        dt = min(time.dt, 0.05)
        if self.state in ("menu", "garage") and self.preview:
            self.preview["root"].rotation_y += 13 * dt
        elif self.state == "race":
            self.race_time += dt
            self.update_player(dt)
            self.update_opponents(dt)
            self.update_camera(dt)
            self.update_hud(dt)
            if self.player_laps >= LAPS_TO_WIN:
                self.finish_race()


game = None

def update():
    if game is not None:
        game.update()

def input(key):
    if game is not None:
        game.input(key)

if __name__ == "__main__":
    ApexVelocity3D()
