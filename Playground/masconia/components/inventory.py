"""
Componente de inventário e equipamento.

Gerencia:
  • Slots de inventário (mochila)
  • Slots de equipamento (mãos, corpo, etc.)
  • Cálculo de bônus de equipamento
  • Moedas (Alma do Dragão = persistente, ouro = intra-run)

Design decision: Inventário usa dicionário de slots em vez de lista
para garantir que só haja um item por slot de equipamento.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from utils.constants import EquipmentSlot


@dataclass
class Inventory:
    """
    Inventário e equipamentos de uma entidade.

    Attributes:
        items: Lista de itens na mochila.
        equipped: Dict slot→item atualmente equipado.
        gold: Ouro intra-run (perdido ao morrer).
        dragon_souls: Alma do Dragão (persistente entre runs).
        max_slots: Capacidade da mochila.
    """
    items: List[Dict[str, Any]] = field(default_factory=list)
    equipped: Dict[EquipmentSlot, Dict[str, Any]] = field(default_factory=dict)
    gold: int = 0
    dragon_souls: int = 0
    max_slots: int = 20

    def add_item(self, item: Dict[str, Any]) -> bool:
        """Adiciona item à mochila. Retorna False se cheio."""
        if len(self.items) >= self.max_slots:
            return False
        self.items.append(item)
        return True

    def remove_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Remove item da mochila pelo ID. Retorna o item ou None."""
        for i, item in enumerate(self.items):
            if item.get("id") == item_id:
                return self.items.pop(i)
        return None

    def equip(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Equipa um item. Retorna o item anteriormente equipado no slot,
        ou None se o slot estava vazio.
        """
        slot_str = item.get("slot", "main_hand")
        # Mapeia string para enum
        slot = EquipmentSlot[slot_str.upper()] if hasattr(EquipmentSlot, slot_str.upper()) else None
        if slot is None:
            return None

        # Se for two_hands, desequipa off_hand também
        if slot == EquipmentSlot.TWO_HANDS:
            self.unequip(EquipmentSlot.OFF_HAND)

        previous = self.equipped.get(slot)
        self.equipped[slot] = item
        return previous

    def unequip(self, slot: EquipmentSlot) -> Optional[Dict[str, Any]]:
        """Desequipa item de um slot. Retorna o item removido."""
        return self.equipped.pop(slot, None)

    def get_equipped_bonus(self, bonus_type: str) -> int:
        """Soma bônus de todos os itens equipados (ex: 'ac_bonus')."""
        total = 0
        for item in self.equipped.values():
            total += item.get(bonus_type, 0)
        return total

    def get_weapon_damage(self) -> str:
        """Retorna a expressão de dano da arma equipada."""
        weapon = self.equipped.get(EquipmentSlot.MAIN_HAND)
        if weapon:
            return weapon.get("damage", "1d4")
        # Desarmado
        return "1d4"

    def get_weapon_damage_type(self) -> str:
        """Retorna o tipo de dano da arma equipada."""
        weapon = self.equipped.get(EquipmentSlot.MAIN_HAND)
        if weapon:
            return weapon.get("damage_type", "bludgeoning")
        return "bludgeoning"

    def add_gold(self, amount: int):
        self.gold += amount

    def add_dragon_souls(self, amount: int):
        self.dragon_souls += amount

    def spend_gold(self, amount: int) -> bool:
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def __repr__(self):
        return f"Inventory(items={len(self.items)}, equipped={len(self.equipped)}, gold={self.gold}, souls={self.dragon_souls})"
