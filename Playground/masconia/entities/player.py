"""
Player: factory para criar entidades de jogador.

Cria uma entidade ECS completa com todos os componentes necessários
baseado na classe escolhida (Guerreiro, Ladino, Mago, Clérigo).

Por que factory em vez de classe Player herdando Entity?
  → ECS: jogador é uma entidade como qualquer outra.
  → A lógica de criação fica separada da lógica de gameplay.
  → Facilita criar NPCs aliados com a mesma estrutura.
"""
import json
import os
from typing import Dict, Any, Optional

from ecs.entity import Entity
from ecs.world import World
from components.position import Position
from components.renderable import Renderable
from components.stats import Stats
from components.inventory import Inventory
from components.fighter import Fighter
from components.ai import AI  # Não usado para player, mas importado para clareza
from utils.constants import DamageType


class PlayerFactory:
    """
    Factory para criar entidades de jogador.

    Carrega dados da classe de data/classes.json e monta
    a entidade ECS com todos os componentes.
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        self._classes_data = self._load_classes()

    def _load_classes(self) -> Dict[str, Any]:
        path = os.path.join(self.data_dir, "classes.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def create_player(self, world: World, class_id: str, x: int = 0, y: int = 0) -> Entity:
        """
        Cria um jogador completo.

        Args:
            world: World ECS para registrar a entidade.
            class_id: ID da classe (warrior, rogue, mage, cleric).
            x, y: Posição inicial no grid.

        Returns:
            Entity do jogador com todos os componentes.
        """
        class_data = self._classes_data.get(class_id)
        if not class_data:
            raise ValueError(f"Classe desconhecida: {class_id}")

        entity = world.create_entity(name=class_data["name"])
        entity.add_tag("player")

        # ── Position ───────────────────────────────────────────
        entity.add_component(Position(x=x, y=y, facing="down"))

        # ── Renderable ───────────────────────────────────────
        entity.add_component(Renderable(
            sprite_path=class_data.get("sprite", "player_default.png"),
            color=self._class_color(class_id),
            z_index=20  # Jogador renderiza na frente
        ))

        # ── Stats ──────────────────────────────────────────────
        base_stats = class_data["base_stats"]
        hp_per_level = class_data.get("hp_per_level", 8)

        # HP inicial = hp_per_level + mod CON
        con_mod = (base_stats.get("con", 10) - 10) // 2
        max_hp = hp_per_level + con_mod

        # MP inicial = 10 + mod INT (para magos/clérigos)
        int_mod = (base_stats.get("int", 10) - 10) // 2
        max_mp = max(0, 10 + int_mod) if class_id in ["mage", "cleric"] else 0

        entity.add_component(Stats(
            str_=base_stats.get("str", 10),
            dex=base_stats.get("dex", 10),
            con=base_stats.get("con", 10),
            int_=base_stats.get("int", 10),
            wis=base_stats.get("wis", 10),
            cha=base_stats.get("cha", 10),
            hp=max_hp,
            max_hp=max_hp,
            mp=max_mp,
            max_mp=max_mp,
            level=1,
            ac_base=10,  # CA base sem armadura
        ))

        # ── Inventory ──────────────────────────────────────────
        entity.add_component(Inventory(
            max_slots=20,
            gold=0,
            dragon_souls=0
        ))

        # ── Fighter ────────────────────────────────────────────
        # Ataques base (desarmado + arma inicial)
        attacks = [{
            "name": "Soco",
            "hit_bonus": 0,
            "damage": "1d4",
            "damage_type": "bludgeoning"
        }]

        # Adiciona ataques da classe
        for ability in class_data.get("abilities", []):
            if not ability.get("passive"):
                attacks.append({
                    "name": ability["name"],
                    "hit_bonus": 0,
                    "damage": "1d6",  # Simplificado
                    "damage_type": self._ability_damage_type(ability["id"]),
                    "ability_id": ability["id"]
                })

        entity.add_component(Fighter(
            attacks=attacks,
            max_movement=5,  # 5 tiles por turno (D&D padrão)
            action_points=1,
            movement_left=5
        ))

        # ── Equipamento inicial ────────────────────────────────
        inv = entity.get_component(Inventory)
        for item_id in class_data.get("starting_equipment", []):
            item = self._find_item(item_id)
            if item:
                inv.add_item(item)
                inv.equip(item)

        return entity

    def _class_color(self, class_id: str) -> tuple:
        """Cor de fallback para cada classe."""
        colors = {
            "warrior": (180, 60, 60),
            "rogue": (60, 60, 80),
            "mage": (60, 60, 180),
            "cleric": (180, 160, 60),
        }
        return colors.get(class_id, (200, 200, 200))

    def _ability_damage_type(self, ability_id: str) -> str:
        """Mapeia habilidade para tipo de dano."""
        mapping = {
            "fireball": "fire",
            "power_attack": "slashing",
            "sneak_attack": "piercing",
        }
        return mapping.get(ability_id, "bludgeoning")

    def _find_item(self, item_id: str) -> Optional[Dict]:
        """Busca item em data/items.json."""
        path = os.path.join(self.data_dir, "items.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
            for category in items.values():
                for item in category:
                    if item.get("id") == item_id:
                        return item
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return None

    def __repr__(self):
        return f"PlayerFactory(classes={list(self._classes_data.keys())})"
