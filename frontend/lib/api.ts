export type TileDTO = { q: number; r: number; terrain: string };
export type UnitDTO = {
  id: number;
  owner: number;
  type: string;
  q: number;
  r: number;
  health: number;
  moves_remaining: number;
};
export type CityDTO = {
  id: number;
  owner: number;
  name: string;
  q: number;
  r: number;
  population: number;
  food_stored: number;
  production_stored: number;
  production_queue: string[];
};
export type CivDTO = {
  id: number;
  name: string;
  leader_name: string;
  is_human: boolean;
  gold: number;
  science: number;
  culture: number;
  known_techs: string[];
  researching: string | null;
};
export type GameStateDTO = {
  id: number;
  turn: number;
  map_radius: number;
  tiles: TileDTO[];
  civs: CivDTO[];
  cities: CityDTO[];
  units: UnitDTO[];
};

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export const api = {
  createGame: (radius = 5, seed = 0) =>
    req<GameStateDTO>("/games", {
      method: "POST",
      body: JSON.stringify({ radius, seed }),
    }),
  getGame: (id: number) => req<GameStateDTO>(`/games/${id}`),
  endTurn: (id: number) =>
    req<GameStateDTO>(`/games/${id}/turn`, { method: "POST" }),
  move: (id: number, unit_id: number, q: number, r: number) =>
    req<GameStateDTO>(`/games/${id}/actions/move`, {
      method: "POST",
      body: JSON.stringify({ unit_id, q, r }),
    }),
  attack: (id: number, attacker_id: number, defender_id: number) =>
    req<GameStateDTO>(`/games/${id}/actions/attack`, {
      method: "POST",
      body: JSON.stringify({ attacker_id, defender_id }),
    }),
  foundCity: (id: number, unit_id: number, name: string) =>
    req<GameStateDTO>(`/games/${id}/actions/found`, {
      method: "POST",
      body: JSON.stringify({ unit_id, name }),
    }),
  research: (id: number, civ_id: number, tech_id: string) =>
    req<GameStateDTO>(`/games/${id}/actions/research`, {
      method: "POST",
      body: JSON.stringify({ civ_id, tech_id }),
    }),
};
