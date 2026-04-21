import { GameStateDTO, MessageDTO } from "./api";

export type TurnEvent = {
  id: string;
  turn: number;
  kind:
    | "city_founded"
    | "tech_completed"
    | "unit_lost"
    | "civ_met"
    | "stance_changed"
    | "message_received";
  text: string;
};

interface DiffInput {
  prev: GameStateDTO;
  next: GameStateDTO;
  humanCivId: number | null;
}

function civName(state: GameStateDTO, id: number): string {
  return state.civs.find((c) => c.id === id)?.name ?? `Civ ${id}`;
}

function messageKey(m: MessageDTO): string {
  return `${m.turn}:${m.from_civ_id}:${m.to_civ_id}:${m.kind}:${m.text}`;
}

export function diffTurnEvents({ prev, next, humanCivId }: DiffInput): TurnEvent[] {
  const events: TurnEvent[] = [];
  const turn = next.turn;

  const prevCityIds = new Set(prev.cities.map((c) => c.id));
  for (const city of next.cities) {
    if (!prevCityIds.has(city.id)) {
      events.push({
        id: `city-${city.id}`,
        turn,
        kind: "city_founded",
        text: `${civName(next, city.owner)} founded ${city.name}`,
      });
    }
  }

  for (const civ of next.civs) {
    const before = prev.civs.find((c) => c.id === civ.id);
    if (!before) continue;
    const beforeKnown = new Set(before.known_techs);
    for (const tech of civ.known_techs) {
      if (!beforeKnown.has(tech)) {
        events.push({
          id: `tech-${civ.id}-${tech}-${turn}`,
          turn,
          kind: "tech_completed",
          text: `${civName(next, civ.id)} discovered ${capitalize(tech.replaceAll("_", " "))}`,
        });
      }
    }
  }

  if (humanCivId !== null) {
    const prevHumanUnitIds = new Set(
      prev.units.filter((u) => u.owner === humanCivId).map((u) => u.id),
    );
    const nextHumanUnitIds = new Set(
      next.units.filter((u) => u.owner === humanCivId).map((u) => u.id),
    );
    for (const id of prevHumanUnitIds) {
      if (!nextHumanUnitIds.has(id)) {
        const lost = prev.units.find((u) => u.id === id);
        if (lost) {
          events.push({
            id: `lost-${id}-${turn}`,
            turn,
            kind: "unit_lost",
            text: `Lost ${lost.type} #${id}`,
          });
        }
      }
    }
  }

  const prevKnown = new Set(prev.known_civ_ids);
  for (const id of next.known_civ_ids) {
    if (!prevKnown.has(id)) {
      events.push({
        id: `met-${id}-${turn}`,
        turn,
        kind: "civ_met",
        text: `Met ${civName(next, id)}`,
      });
    }
  }

  const prevStance = new Map(prev.stances.map((s) => [s.other_civ_id, s.stance]));
  for (const s of next.stances) {
    const before = prevStance.get(s.other_civ_id);
    if (before && before !== s.stance) {
      events.push({
        id: `stance-${s.other_civ_id}-${turn}`,
        turn,
        kind: "stance_changed",
        text: `${civName(next, s.other_civ_id)} → ${capitalize(s.stance)}`,
      });
    }
  }

  const prevMsgKeys = new Set(prev.messages.map(messageKey));
  if (humanCivId !== null) {
    for (const m of next.messages) {
      if (m.to_civ_id !== humanCivId) continue;
      if (prevMsgKeys.has(messageKey(m))) continue;
      events.push({
        id: `msg-${m.from_civ_id}-${turn}-${events.length}`,
        turn,
        kind: "message_received",
        text: `${civName(next, m.from_civ_id)} (${m.kind}): ${truncate(m.text, 60)}`,
      });
    }
  }

  return events;
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : value.slice(0, max - 1) + "…";
}
