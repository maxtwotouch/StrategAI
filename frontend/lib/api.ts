export type TileDTO = {
  q: number;
  r: number;
  terrain: string;
  resource: string | null;
  feature: string | null;
  river: boolean;
  improvement: string | null;
  food: number;
  production: number;
  gold: number;
};
export type WorkOrderDTO = {
  q: number;
  r: number;
  improvement: string;
  turns_remaining: number;
};
export type UnitDTO = {
  id: number;
  owner: number;
  type: string;
  q: number;
  r: number;
  health: number;
  moves_remaining: number;
  work_order: WorkOrderDTO | null;
};
export type WorkedTileDTO = { q: number; r: number };
export type CityDTO = {
  id: number;
  owner: number;
  name: string;
  q: number;
  r: number;
  population: number;
  food_stored: number;
  production_stored: number;
  health: number;
  max_health: number;
  is_capital: boolean;
  buildings: string[];
  production_queue: string[];
  border_radius: number;
  culture_stored: number;
  worked_tiles: WorkedTileDTO[];
  purchased_structures: string[];
};
export type CivDTO = {
  id: number;
  name: string;
  leader_name: string;
  is_human: boolean;
  gold: number;
  gold_income: number;
  gold_upkeep: number;
  science: number;
  culture: number;
  known_techs: string[];
  researching: string | null;
  score: number;
};
export type TileOwnerDTO = {
  q: number;
  r: number;
  city_id: number;
};
export type MessageDTO = {
  from_civ_id: number;
  to_civ_id: number;
  turn: number;
  kind: string;
  text: string;
};
export type StanceDTO = {
  other_civ_id: number;
  stance: string;
  relationship: number;
  truce_active: boolean;
  truce_until: number | null;
};

export type DiplomaticEventDTO = {
  turn: number;
  kind: string;
  actor_civ_id: number;
  target_civ_id: number;
  summary: string;
  relationship_delta: number;
};

export type StandingDTO = {
  civ_id: number;
  name: string;
  score: number;
};
export type GameStateDTO = {
  id: number;
  turn: number;
  current_civ_id: number;
  map_radius: number;
  tiles: TileDTO[];
  civs: CivDTO[];
  cities: CityDTO[];
  units: UnitDTO[];
  known_civ_ids: number[];
  messages: MessageDTO[];
  inbox: MessageDTO[];
  stances: StanceDTO[];
  visible_tile_keys: string[];
  tile_owner: TileOwnerDTO[];
  diplomatic_events: DiplomaticEventDTO[];
  standings: StandingDTO[];
  score_threshold: number;
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
  createGame: (radius = 5, seed = 0, human_name = "Athens") =>
    req<GameStateDTO>("/games", {
      method: "POST",
      body: JSON.stringify({ radius, seed, human_name }),
    }),
  getGame: (id: number) => req<GameStateDTO>(`/games/${id}`),
  endTurn: (id: number) =>
    req<GameStateDTO>(`/games/${id}/turn`, { method: "POST" }),
  resolveTurn: (id: number) =>
    req<GameStateDTO>(`/games/${id}/turn/resolve`, { method: "POST" }),
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
  build: (id: number, civ_id: number, city_id: number, unit_type: string) =>
    req<GameStateDTO>(`/games/${id}/actions/build`, {
      method: "POST",
      body: JSON.stringify({ civ_id, city_id, unit_type }),
    }),
  cancelBuild: (id: number, civ_id: number, city_id: number, index: number) =>
    req<GameStateDTO>(`/games/${id}/actions/cancel-build`, {
      method: "POST",
      body: JSON.stringify({ civ_id, city_id, index }),
    }),
  purchaseStructure: (
    id: number,
    civ_id: number,
    city_id: number,
    category: string,
  ) =>
    req<GameStateDTO>(`/games/${id}/actions/purchase-structure`, {
      method: "POST",
      body: JSON.stringify({ civ_id, city_id, category }),
    }),
  improve: (id: number, unit_id: number, improvement: string) =>
    req<GameStateDTO>(`/games/${id}/actions/improve`, {
      method: "POST",
      body: JSON.stringify({ unit_id, improvement }),
    }),
  sendMessage: (
    id: number,
    from_civ_id: number,
    to_civ_id: number,
    kind: string,
    text: string,
  ) =>
    req<GameStateDTO>(`/games/${id}/actions/message`, {
      method: "POST",
      body: JSON.stringify({ from_civ_id, to_civ_id, kind, text }),
    }),
};
