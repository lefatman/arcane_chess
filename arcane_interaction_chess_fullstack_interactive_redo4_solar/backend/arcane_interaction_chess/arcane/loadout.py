from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set

from .definitions import AbilityId, ElementId, ItemId, ITEM_SLOT_COST

@dataclass(frozen=True)
class AbilitySlot:
    ability: AbilityId
    piece_type: Optional[str] = None  # e.g. "Pawn", "Knight" etc

@dataclass
class PlayerConfig:
    element: ElementId
    items: List[ItemId] = field(default_factory=list)
    abilities: List[AbilitySlot] = field(default_factory=list)

    def validate(self) -> None:
        # item slot budget (cost <=4)
        total_cost = sum(ITEM_SLOT_COST[i] for i in self.items)
        if total_cost > 4:
            raise ValueError(f"Item slot cost exceeds 4 (got {total_cost})")

        items_set = set(self.items)

        # mutual exclusions
        if ItemId.TRIPLE_ADEPTS_GLOVES in items_set:
            if ItemId.DUAL_ADEPTS_GLOVES in items_set or ItemId.HEADMASTER_RING in items_set:
                raise ValueError("Triple Adept’s Gloves blocks Dual Adept’s Gloves and Headmaster Ring")
        if ItemId.HEADMASTER_RING in items_set:
            if ItemId.DUAL_ADEPTS_GLOVES in items_set or ItemId.TRIPLE_ADEPTS_GLOVES in items_set:
                raise ValueError("Headmaster Ring blocks Dual and Triple Adept’s Gloves")

        # multitasker schedule mutually exclusive with lightning element
        if self.element is ElementId.LIGHTNING and ItemId.MULTITASKERS_SCHEDULE in items_set:
            raise ValueError("Multitasker’s Schedule is mutually exclusive with Lightning element")

        # ability slot count
        slots = self.ability_slot_count()
        if len(self.abilities) > slots:
            raise ValueError(f"Too many abilities slotted: {len(self.abilities)} > {slots}")

        # piece-type targeting constraints
        allow_piece_type = (self.element is ElementId.LIGHTNING) or (ItemId.MULTITASKERS_SCHEDULE in items_set)
        if not allow_piece_type:
            for s in self.abilities:
                if s.piece_type is not None:
                    raise ValueError("Piece-type ability targeting requires Lightning element or Multitasker’s Schedule")

    def ability_slot_count(self) -> int:
        items_set = set(self.items)
        bonus = 0
        if ItemId.DUAL_ADEPTS_GLOVES in items_set:
            bonus += 1
        if ItemId.TRIPLE_ADEPTS_GLOVES in items_set:
            bonus += 2
        if ItemId.HEADMASTER_RING in items_set:
            bonus += 3
        return 1 + bonus

    def has_item(self, item: ItemId) -> bool:
        return item in set(self.items)

    def xp_multiplier(self) -> int:
        return 2 if self.has_item(ItemId.POT_OF_HUNGER) else 1
