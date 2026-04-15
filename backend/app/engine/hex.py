"""Axial hex coordinate math. Immutable, pure functions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Hex:
    q: int
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    def __add__(self, other: "Hex") -> "Hex":
        return Hex(self.q + other.q, self.r + other.r)

    def __sub__(self, other: "Hex") -> "Hex":
        return Hex(self.q - other.q, self.r - other.r)


HEX_DIRECTIONS: tuple[Hex, ...] = (
    Hex(1, 0),
    Hex(1, -1),
    Hex(0, -1),
    Hex(-1, 0),
    Hex(-1, 1),
    Hex(0, 1),
)


def hex_distance(a: Hex, b: Hex) -> int:
    d = a - b
    return (abs(d.q) + abs(d.r) + abs(d.s)) // 2


def hex_neighbors(h: Hex) -> list[Hex]:
    return [h + d for d in HEX_DIRECTIONS]


def hex_range(center: Hex, radius: int) -> list[Hex]:
    if radius < 0:
        return []
    tiles: list[Hex] = []
    for dq in range(-radius, radius + 1):
        r_min = max(-radius, -dq - radius)
        r_max = min(radius, -dq + radius)
        for dr in range(r_min, r_max + 1):
            tiles.append(Hex(center.q + dq, center.r + dr))
    return tiles
