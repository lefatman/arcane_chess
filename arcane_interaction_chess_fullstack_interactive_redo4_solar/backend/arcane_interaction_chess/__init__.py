"""Arcane Interaction Chess (backend).

- core: interaction-driven chess engine (pieces define movement)
- arcane: elements/items/abilities system
- api: stable JSON-oriented facade for UIs
- formats/tools: FEN/SAN/PGN/perft/UCI helpers
"""

from . import core, arcane, api
from .fen import parse_fen, game_to_fen, STARTPOS_FEN
from .perft import perft, perft_divide
from .san import to_san
from .pgn import moves_to_pgn

__all__ = [
    "core","arcane","api",
    "parse_fen","game_to_fen","STARTPOS_FEN",
    "perft","perft_divide",
    "to_san",
    "moves_to_pgn",
]
