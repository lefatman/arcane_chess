from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Set

class ElementId(int, Enum):
    WATER = 0
    FIRE = 1
    EARTH = 2
    AIR = 3
    LIGHTNING = 4

class ItemId(int, Enum):
    MULTITASKERS_SCHEDULE = 1
    POISONED_DAGGER = 2
    DUAL_ADEPTS_GLOVES = 3
    TRIPLE_ADEPTS_GLOVES = 4
    HEADMASTER_RING = 5
    POT_OF_HUNGER = 6
    SOLAR_NECKLACE = 7

class AbilityId(int, Enum):
    BLOCK_PATH = 1
    STALWART = 2
    BELLIGERENT = 3
    REDO = 4
    DOUBLE_KILL = 5
    QUANTUM_KILL = 6
    CHAIN_KILL = 7
    NECROMANCER = 8

class AbilityScope(str, Enum):
    ARMY_WIDE = "army-wide"

class AbilityCategory(str, Enum):
    DEFENSIVE = "defensive"
    OFFENSIVE = "offensive"

class CardinalDir(str, Enum):
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"

ITEM_SLOT_COST: Dict[ItemId, int] = {
    ItemId.MULTITASKERS_SCHEDULE: 1,
    ItemId.POISONED_DAGGER: 1,
    ItemId.DUAL_ADEPTS_GLOVES: 1,
    ItemId.TRIPLE_ADEPTS_GLOVES: 2,
    ItemId.HEADMASTER_RING: 3,
    ItemId.POT_OF_HUNGER: 1,
    ItemId.SOLAR_NECKLACE: 1,
}

@dataclass(frozen=True)
class AbilityDef:
    ability_id: AbilityId
    name: str
    scope: AbilityScope
    category: AbilityCategory
    consumable: bool

ABILITY_DEFS: Dict[AbilityId, AbilityDef] = {
    AbilityId.BLOCK_PATH: AbilityDef(AbilityId.BLOCK_PATH, "Block Path", AbilityScope.ARMY_WIDE, AbilityCategory.DEFENSIVE, False),
    AbilityId.STALWART: AbilityDef(AbilityId.STALWART, "Stalwart", AbilityScope.ARMY_WIDE, AbilityCategory.DEFENSIVE, False),
    AbilityId.BELLIGERENT: AbilityDef(AbilityId.BELLIGERENT, "Belligerent", AbilityScope.ARMY_WIDE, AbilityCategory.DEFENSIVE, False),
    AbilityId.REDO: AbilityDef(AbilityId.REDO, "Redo", AbilityScope.ARMY_WIDE, AbilityCategory.DEFENSIVE, True),
    AbilityId.DOUBLE_KILL: AbilityDef(AbilityId.DOUBLE_KILL, "Double Kill", AbilityScope.ARMY_WIDE, AbilityCategory.OFFENSIVE, False),
    AbilityId.QUANTUM_KILL: AbilityDef(AbilityId.QUANTUM_KILL, "Quantum Kill", AbilityScope.ARMY_WIDE, AbilityCategory.OFFENSIVE, False),
    AbilityId.CHAIN_KILL: AbilityDef(AbilityId.CHAIN_KILL, "Chain Kill", AbilityScope.ARMY_WIDE, AbilityCategory.OFFENSIVE, False),
    AbilityId.NECROMANCER: AbilityDef(AbilityId.NECROMANCER, "Necromancer", AbilityScope.ARMY_WIDE, AbilityCategory.OFFENSIVE, True),
}

DEFENSIVE_ABILITIES: Set[AbilityId] = {a for a, d in ABILITY_DEFS.items() if d.category is AbilityCategory.DEFENSIVE}
OFFENSIVE_ABILITIES: Set[AbilityId] = {a for a, d in ABILITY_DEFS.items() if d.category is AbilityCategory.OFFENSIVE}
