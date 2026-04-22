"""Grid coordinate math for an 8-directional square grid.

Historically this module implemented axial hex coordinates; it now implements
a square grid where each cell has eight neighbors (king's moves). The ``Hex``
class name and the ``q``/``r`` field names are retained across the codebase
and the wire format to avoid a mass rename. Semantically ``q`` is column
(x) and ``r`` is row (y).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Hex:
    q: int
    r: int

    def __add__(self, other: "Hex") -> "Hex":
        return Hex(self.q + other.q, self.r + other.r)

    def __sub__(self, other: "Hex") -> "Hex":
        return Hex(self.q - other.q, self.r - other.r)


HEX_DIRECTIONS: tuple[Hex, ...] = (
    Hex(1, 0),    # E
    Hex(1, -1),   # NE
    Hex(0, -1),   # N
    Hex(-1, -1),  # NW
    Hex(-1, 0),   # W
    Hex(-1, 1),   # SW
    Hex(0, 1),    # S
    Hex(1, 1),    # SE
)


def hex_distance(a: Hex, b: Hex) -> int:
    """Chebyshev distance — one step covers any of the 8 neighbors."""
    return max(abs(a.q - b.q), abs(a.r - b.r))


def hex_neighbors(h: Hex) -> list[Hex]:
    return [h + d for d in HEX_DIRECTIONS]


def hex_range(center: Hex, radius: int) -> list[Hex]:
    """All cells within Chebyshev distance ``radius`` — a (2r+1)×(2r+1) square."""
    if radius < 0:
        return []
    tiles: list[Hex] = []
    for dq in range(-radius, radius + 1):
        for dr in range(-radius, radius + 1):
            tiles.append(Hex(center.q + dq, center.r + dr))
    return tiles
