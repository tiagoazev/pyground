"""
Enemy: factory para criar entidades de inimigos.

Cria inimigos baseado em templates de data/enemies.json.
Suporta inimigos comuns, elites e bosses com fases.

Por que factory?
  → Dados de inimigos são externos (JSON), não hardcoded.
  → Permite spawnar variações (esqueleto com espada diferente, etc.).
  → Facilita balanceamento sem recompilar.
"""
import json
import os
from typing import Dict, Any, Optional, List

from ecs.entity import Entity
from ecs.world import World
from components.position import Position
from components.renderable import Renderable
from components.stats import Stats
from components.inventory import Inventory
from components.fighter import Fighter
from components.ai import AI
from utils.constants import DamageType


class EnemyFactory:
    """
    Factory para criar entidades de inimigos.

    Carrega templates de data/enemies.json por bioma.
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        self._enemies_data = self._load_enemies()

    def _load_enemies(self) -> Dict[str, Any]:
        path = os.path.join(self.data_dir, "enemies.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def create_enemy(self, world: World, enemy_id: str, biome: str,
                     x: int = 0, y: int = 0, is_boss: bool = False) -> Entity:
        """
        Cria um inimigo completo.

        Args:
            world: World ECS.
            enemy_id: ID do inimigo no JSON.
            biome: Bioma atual.
            x, y: Posição no grid.
            is_boss: Se True, usa dados do mini_boss/boss do bioma.

        Returns:
            Entity do inimigo.
        """
        biome_data = self._enemies_data.get(biome, {})

        if is_boss:
            template = biome_data.get("mini_boss") or biome_data.get("boss")
        else:
            template = None
            for enemy in biome_data.get("enemies", []):
                if enemy.get("id") == enemy_id:
                    template = enemy
                    break

        if not template:
            raise ValueError(f"Inimigo não encontrado: {enemy_id} em {biome}")

        entity = world.create_entity(name=template["name"])
        entity.add_tag("enemy")
        if is_boss:
            entity.add_tag("boss")

        # ── Position ───────────────────────────────────────────
        entity.add_component(Position(x=x, y=y, facing="up"))

        # ── Renderable ─────────────────────────────────────────
        entity.add_component(Renderable(
            sprite_path=template.get("sprite", "enemy_default.png"),
            color=self._enemy_color(template.get("id", "")),
            z_index=15
        ))

        # ── Stats ──────────────────────────────────────────────
        stats_data = template.get("stats", {})
        entity.add_component(Stats(
            str_=stats_data.get("str", 10),
            dex=stats_data.get("dex", 10),
            con=stats_data.get("con", 10),
            int_=stats_data.get("int", 10),
            wis=stats_data.get("wis", 10),
            cha=stats_data.get("cha", 10),
            hp=template.get("hp", 10),
            max_hp=template.get("hp", 10),
            level=max(1, int(template.get("cr", 0))),
            ac_base=template.get("ac", 10),
        ))

        # ── Inventory (para loot) ────────────────────────────────
        entity.add_component(Inventory())

        # ── Fighter ──────────────────────────────────────────────
        attacks = template.get("attacks", [])
        fighter = Fighter(
            attacks=attacks,
            max_movement=4 if template.get("ai") == "melee_slow" else 5,
            action_points=1,
            movement_left=4 if template.get("ai") == "melee_slow" else 5
        )

        # Resistências e vulnerabilidades
        for res in template.get("resistances", []):
            fighter.resistances.append(self._str_to_damage_type(res))
        for weak in template.get("weaknesses", []):
            fighter.weaknesses.append(self._str_to_damage_type(weak))

        # Fases de boss
        if is_boss and "phases" in template:
            fighter.phases = template["phases"]

        entity.add_component(fighter)

        # ── AI ───────────────────────────────────────────────────
        ai_data = template.get("ai", "melee_aggressive")
        ai = AI(
            behavior_type=ai_data,
            aggro_range=8 if is_boss else 6,
            flee_threshold=0.2 if not is_boss else 0.0,
            preferred_range=0 if "melee" in ai_data else 4
        )
        entity.add_component(ai)

        return entity

    def create_random_enemy(self, world: World, biome: str,
                            x: int = 0, y: int = 0,
                            difficulty: str = "normal") -> Entity:
        """
        Cria um inimigo aleatório do bioma.

        Args:
            difficulty: "normal", "elite", ou "boss".
        """
        biome_data = self._enemies_data.get(biome, {})

        if difficulty == "boss":
            return self.create_enemy(world, "", biome, x, y, is_boss=True)

        enemies = biome_data.get("enemies", [])
        if not enemies:
            raise ValueError(f"Nenhum inimigo definido para bioma: {biome}")

        if difficulty == "elite":
            # Pega inimigos de CR mais alto
            candidates = [e for e in enemies if e.get("cr", 0) >= 2]
            if not candidates:
                candidates = enemies
        else:
            candidates = enemies

        import random
        template = random.choice(candidates)
        return self.create_enemy(world, template["id"], biome, x, y)

    def _enemy_color(self, enemy_id: str) -> tuple:
        """Cor de fallback para inimigos."""
        colors = {
            "skeleton": (220, 220, 200),
            "zombie": (100, 140, 80),
            "wraith": (80, 80, 120),
            "crystal_slug": (100, 200, 200),
            "gem_bat": (150, 100, 200),
            "crystal_golem": (80, 150, 180),
            "kobold": (180, 120, 60),
            "drake": (200, 80, 40),
            "dragon_cultist": (150, 50, 50),
        }
        return colors.get(enemy_id, (150, 50, 50))

    def _str_to_damage_type(self, s: str) -> DamageType:
        mapping = {
            "slashing": DamageType.SLASHING,
            "piercing": DamageType.PIERCING,
            "bludgeoning": DamageType.BLUDGEONING,
            "fire": DamageType.FIRE,
            "cold": DamageType.COLD,
            "lightning": DamageType.LIGHTNING,
            "acid": DamageType.ACID,
            "poison": DamageType.POISON,
            "necrotic": DamageType.NECROTIC,
            "radiant": DamageType.RADIANT,
            "force": DamageType.FORCE,
            "thunder": DamageType.THUNDER,
            "psychic": DamageType.PSYCHIC,
        }
        return mapping.get(s.lower(), DamageType.BLUDGEONING)

    def __repr__(self):
        return f"EnemyFactory(biomes={list(self._enemies_data.keys())})"
