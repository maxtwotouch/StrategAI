import { GameStateDTO, MessageDTO } from "./api";
import type { LeaderActionCategory } from "./assetApi";

export type TurnEvent = {
  id: string;
  turn: number;
  kind:
    | "city_founded"
    | "tech_completed"
    | "unit_created"
    | "unit_lost"
    | "city_grew"
    | "structure_built"
    | "civ_met"
    | "stance_changed"
    | "message_received"
    | "turn_summary";
  text: string;
  civIds: number[];
  actionCategory: LeaderActionCategory;
  actionDescription: string;
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
        civIds: [city.owner],
        actionCategory: "construction",
        actionDescription: `${civName(next, city.owner)} oversees the founding of ${city.name}, with settlers raising banners and workers marking the first streets of a new city. ${sceneAccent(turn)}`,
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
          civIds: [civ.id],
          actionCategory: "scientific",
          actionDescription: `${civName(next, civ.id)} celebrates a breakthrough in ${capitalize(tech.replaceAll("_", " "))}, with scholars presenting instruments, scrolls, and new plans before their ruler. ${sceneAccent(turn)}`,
        });
      }
    }
  }

  const prevUnitIds = new Set(prev.units.map((u) => u.id));
  for (const unit of next.units) {
    if (prevUnitIds.has(unit.id)) continue;
    events.push({
      id: `unit-created-${unit.id}-${turn}`,
      turn,
      kind: "unit_created",
      text: `${civName(next, unit.owner)} trained a ${unit.type}`,
      civIds: [unit.owner],
      actionCategory: "military",
      actionDescription: `${civName(next, unit.owner)} musters a newly trained ${unit.type} formation, with armor being strapped on, banners lifted, weapons checked, and officers preparing the troops for campaign orders. ${sceneAccent(turn)}`,
    });
  }

  const prevCityById = new Map(prev.cities.map((city) => [city.id, city]));
  for (const city of next.cities) {
    const before = prevCityById.get(city.id);
    if (!before) continue;
    if (city.population > before.population) {
      events.push({
        id: `city-grew-${city.id}-${turn}`,
        turn,
        kind: "city_grew",
        text: `${city.name} grew to population ${city.population}`,
        civIds: [city.owner],
        actionCategory: "construction",
        actionDescription: `${civName(next, city.owner)} oversees the busy growth of ${city.name}, with masons raising timber scaffolds, families entering new homes, market stalls opening, and workers expanding the settlement streets. ${sceneAccent(turn)}`,
      });
    }
  }

  const structureKey = (structure: GameStateDTO["structures"][number]): string =>
    `${structure.city_id}:${structure.category}:${structure.q}:${structure.r}`;
  const prevStructureKeys = new Set(prev.structures.map(structureKey));
  for (const structure of next.structures) {
    if (prevStructureKeys.has(structureKey(structure))) continue;
    const city = next.cities.find((candidate) => candidate.id === structure.city_id);
    events.push({
      id: `structure-${structure.city_id}-${structure.category}-${turn}`,
      turn,
      kind: "structure_built",
      text: `${civName(next, structure.owner)} built ${structure.category}`,
      civIds: [structure.owner],
      actionCategory: "construction",
      actionDescription: `${civName(next, structure.owner)} directs construction crews near ${city?.name ?? "a growing city"}, with stone blocks, wooden cranes, scaffolding, and laborers completing a new ${structure.category} district. ${sceneAccent(turn)}`,
    });
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
            civIds: [lost.owner],
            actionCategory: "crisis",
            actionDescription: `${civName(next, lost.owner)} responds to the loss of a ${lost.type} unit, standing in a tense war council as messengers report the battlefield disaster. ${sceneAccent(turn)}`,
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
        civIds: humanCivId !== null ? [humanCivId, id] : [id],
        actionCategory: "diplomatic",
        actionDescription: `${humanCivId !== null ? civName(next, humanCivId) : "A newly encountered leader"} meets ${civName(next, id)} for the first time, with envoys, banners, and cautious ceremony between rival courts. ${sceneAccent(turn)}`,
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
        civIds: humanCivId !== null ? [humanCivId, s.other_civ_id] : [s.other_civ_id],
        actionCategory: s.stance === "war" ? "military" : "diplomatic",
        actionDescription:
          s.stance === "war"
            ? `${civName(next, s.other_civ_id)} enters a state of war, with leaders confronting each other across a tense campaign table as banners and weapons surround them.`
            : `${civName(next, s.other_civ_id)} shifts diplomatic stance to ${s.stance}, with leaders negotiating terms in a formal audience chamber.`,
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
        civIds: [m.from_civ_id, m.to_civ_id],
        actionCategory:
          m.kind === "threat" || m.kind === "declare_war"
            ? "military"
            : m.kind.includes("alliance") || m.kind.includes("peace")
              ? "diplomatic"
              : "cultural",
        actionDescription: `${civName(next, m.from_civ_id)} sends a ${m.kind.replaceAll("_", " ")} message to ${civName(next, m.to_civ_id)}: "${truncate(m.text, 180)}" ${sceneAccent(turn)}`,
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

function sceneAccent(turn: number): string {
  const accents = [
    "Compose it outdoors at dawn with mist, half-built palisades, and long shadows.",
    "Compose it at night by torchlight with sparks, smoke, and urgent movement.",
    "Compose it in a rain-soaked courtyard with muddy ground and wind-torn banners.",
    "Compose it inside a busy workshop with tools, timber, stone dust, and warm firelight.",
    "Compose it on a hilltop overlooking the frontier with maps, scouts, and distant campfires.",
    "Compose it in a crowded city square with citizens, carts, livestock, and raised standards.",
  ];
  return accents[turn % accents.length];
}
