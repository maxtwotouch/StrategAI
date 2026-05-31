"""Deterministic civilization-specific city names."""

from __future__ import annotations

from app.engine.models import GameState


CITY_NAME_ROSTERS: dict[str, tuple[str, ...]] = {
    "Athens": (
        "Athens",
        "Sparta",
        "Corinth",
        "Thebes",
        "Argos",
        "Delphi",
    ),
    "Mongolia": (
        "Karakorum",
        "Khanbalyk",
        "Beshbalik",
        "Sarai",
        "Almaliq",
        "Avarga",
    ),
    "Egypt": (
        "Memphis",
        "Thebes",
        "Alexandria",
        "Heliopolis",
        "Elephantine",
        "Avaris",
    ),
    "India": (
        "Delhi",
        "Pataliputra",
        "Varanasi",
        "Ujjain",
        "Mathura",
        "Takshashila",
    ),
}


def city_name_for(
    civ_name: str,
    civ_id: int,
    *,
    used_names: set[str],
    founded_count: int,
) -> str:
    """Return the next unused non-placeholder city name for a civilization."""
    trimmed = civ_name.strip()
    roster = CITY_NAME_ROSTERS.get(trimmed, ())
    for name in roster:
        if name not in used_names:
            return name

    base = trimmed or f"Civ {civ_id}"
    candidates = (
        f"New {base}",
        f"{base} Harbor",
        f"{base} Heights",
        f"{base} Crossing",
        f"{base} Wellspring",
    )
    for name in candidates:
        if name not in used_names:
            return name

    index = founded_count + 1
    name = f"{base} {index}"
    while name in used_names:
        index += 1
        name = f"{base} {index}"
    return name


def next_city_name(state: GameState, civ_id: int) -> str:
    civ = next((c for c in state.civs if c.id == civ_id), None)
    civ_name = civ.name if civ is not None else ""
    owned_cities = state.cities_for(civ_id)
    return city_name_for(
        civ_name,
        civ_id,
        used_names={city.name for city in state.cities},
        founded_count=len(owned_cities),
    )


def next_city_name_from_view(view: dict, civ_id: int) -> str:
    self_view = view.get("self", {})
    civ_name = self_view.get("name") if isinstance(self_view, dict) else None
    visible_cities = view.get("visible_cities", [])
    owned_city_names = {
        city.get("name")
        for city in visible_cities
        if isinstance(city, dict) and city.get("owner") == civ_id
    }
    used_names = {
        city.get("name")
        for city in visible_cities
        if isinstance(city, dict) and isinstance(city.get("name"), str)
    }
    return city_name_for(
        civ_name if isinstance(civ_name, str) else "",
        civ_id,
        used_names={name for name in used_names if isinstance(name, str)},
        founded_count=len(owned_city_names),
    )
