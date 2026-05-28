"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { SquareMap } from "@/components/SquareMap";
import { CityDTO, GameStateDTO, TileDTO, UnitDTO, api } from "@/lib/api";
import {
  CIV_COLORS,
  FEATURE_LABEL,
  RESOURCE_LABEL,
  hexDistance,
  tileKey,
} from "@/lib/hex";
import { TurnEvent, diffTurnEvents } from "@/lib/turnEvents";

type PendingAction = { kind: "found"; unit: UnitDTO } | null;
type Setup = { radius: number; seed: number; humanName: string };
type MapViewMode = "global" | "local";

type TechDef = {
  id: string;
  name: string;
  cost: number;
  prerequisites: string[];
};

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000_000);
}

const TECHS: TechDef[] = [
  { id: "agriculture", name: "Agriculture", cost: 20, prerequisites: [] },
  { id: "pottery", name: "Pottery", cost: 20, prerequisites: [] },
  { id: "mining", name: "Mining", cost: 25, prerequisites: [] },
  { id: "fishing", name: "Fishing", cost: 20, prerequisites: [] },
  { id: "archery", name: "Archery", cost: 25, prerequisites: [] },
  { id: "animal_husbandry", name: "Animal Husbandry", cost: 35, prerequisites: ["agriculture"] },
  { id: "trapping", name: "Trapping", cost: 35, prerequisites: ["pottery"] },
  { id: "bronze_working", name: "Bronze Working", cost: 55, prerequisites: ["mining"] },
  { id: "sailing", name: "Sailing", cost: 45, prerequisites: ["fishing"] },
  { id: "wheel", name: "The Wheel", cost: 55, prerequisites: ["animal_husbandry"] },
  { id: "masonry", name: "Masonry", cost: 55, prerequisites: ["mining"] },
  { id: "writing", name: "Writing", cost: 75, prerequisites: ["pottery"] },
  { id: "horseback_riding", name: "Horseback Riding", cost: 70, prerequisites: ["animal_husbandry"] },
  { id: "currency", name: "Currency", cost: 80, prerequisites: ["bronze_working"] },
  { id: "calendar", name: "Calendar", cost: 70, prerequisites: ["pottery", "agriculture"] },
  { id: "iron_working", name: "Iron Working", cost: 120, prerequisites: ["bronze_working"] },
  { id: "mathematics", name: "Mathematics", cost: 110, prerequisites: ["currency"] },
  { id: "construction", name: "Construction", cost: 100, prerequisites: ["masonry"] },
  { id: "philosophy", name: "Philosophy", cost: 120, prerequisites: ["writing"] },
  { id: "astronomy", name: "Astronomy", cost: 130, prerequisites: ["mathematics", "sailing"] },
];

type BuildableUnit = {
  id: string;
  label: string;
  cost: number;
  requires: string | null;
};

const BUILDABLE_UNITS: BuildableUnit[] = [
  { id: "warrior", label: "Warrior", cost: 10, requires: null },
  { id: "scout", label: "Scout", cost: 8, requires: null },
  { id: "settler", label: "Settler", cost: 15, requires: null },
  { id: "worker", label: "Worker", cost: 10, requires: null },
  { id: "archer", label: "Archer", cost: 15, requires: "archery" },
  { id: "horseman", label: "Horseman", cost: 22, requires: "horseback_riding" },
  { id: "swordsman", label: "Swordsman", cost: 30, requires: "iron_working" },
];

const IMPROVEMENT_OPTIONS = [
  { id: "farm", label: "Farm", desc: "+1 food on plains / grassland" },
  { id: "mine", label: "Mine", desc: "+1 production on hills" },
  { id: "road", label: "Road", desc: "Connect tiles" },
];

const MESSAGE_KINDS = [
  { id: "chat", label: "Chat" },
  { id: "threat", label: "Threat" },
  { id: "offer_peace", label: "Offer Peace" },
  { id: "accept_peace", label: "Accept Peace" },
  { id: "declare_war", label: "Declare War" },
  { id: "propose_alliance", label: "Propose Alliance" },
  { id: "accept_alliance", label: "Accept Alliance" },
  { id: "reject", label: "Reject" },
];

export default function HomePage() {
  const [state, setState] = useState<GameStateDTO | null>(null);
  const [selectedUnit, setSelectedUnit] = useState<UnitDTO | null>(null);
  const [hoveredTile, setHoveredTile] = useState<TileDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction>(null);
  const [cityName, setCityName] = useState("");
  const [setup, setSetup] = useState<Setup>(() => ({
    radius: 20,
    seed: randomSeed(),
    humanName: "Athens",
  }));
  const [messageTargetId, setMessageTargetId] = useState<number | null>(null);
  const [messageKind, setMessageKind] = useState("chat");
  const [messageText, setMessageText] = useState("");
  const [activeConversationCivId, setActiveConversationCivId] = useState<number | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [chronicleCollapsed, setChronicleCollapsed] = useState(false);
  const [mapViewMode, setMapViewMode] = useState<MapViewMode>("local");
  const [bannerEvents, setBannerEvents] = useState<TurnEvent[] | null>(null);
  const [eventLog, setEventLog] = useState<TurnEvent[]>([]);
  const prevStateRef = useRef<GameStateDTO | null>(null);
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadGame = async (nextSetup: Setup) => {
    setBusy(true);
    setError(null);
    try {
      const next = await api.createGame(
        nextSetup.radius,
        nextSetup.seed,
        nextSetup.humanName,
      );
      setState(next);
      setSelectedUnit(null);
      setHoveredTile(null);
      setPending(null);
      setCityName("");
      setMessageTargetId(null);
      setMessageKind("chat");
      setMessageText("");
      setActiveConversationCivId(null);
      setHasStarted(true);
      setMapViewMode("local");
      setBannerEvents(null);
      setEventLog([]);
      prevStateRef.current = next;
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setBusy(false);
    }
  };

  const beginGame = () => {
    const nextSetup = { ...setup, seed: randomSeed() };
    setSetup(nextSetup);
    void loadGame(nextSetup);
  };

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    return () => {
      if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    };
  }, []);

  const humanCiv = useMemo(
    () => state?.civs.find((c) => c.is_human) ?? null,
    [state],
  );

  const humanCities = useMemo(
    () => (state && humanCiv ? state.cities.filter((c) => c.owner === humanCiv.id) : []),
    [state, humanCiv],
  );

  const humanUnits = useMemo(
    () => (state && humanCiv ? state.units.filter((u) => u.owner === humanCiv.id) : []),
    [state, humanCiv],
  );

  const isHumanTurn = useMemo(
    () => Boolean(state && humanCiv && state.current_civ_id === humanCiv.id),
    [state, humanCiv],
  );

  const otherCivs = useMemo(
    () =>
      state && humanCiv
        ? state.civs.filter(
            (c) => c.id !== humanCiv.id && state.known_civ_ids.includes(c.id),
          )
        : [],
    [state, humanCiv],
  );

  const visibleTiles = useMemo(
    () => new Set(state?.visible_tile_keys ?? []),
    [state?.visible_tile_keys],
  );

  const activeVisibleTiles = useMemo(
    () => (mapViewMode === "global" ? new Set<string>() : visibleTiles),
    [mapViewMode, visibleTiles],
  );

  useEffect(() => {
    if (messageTargetId !== null) return;
    if (otherCivs.length === 0) return;
    setMessageTargetId(otherCivs[0].id);
  }, [messageTargetId, otherCivs]);

  // Drawer is closed by default — only opens when the player clicks a leader.
  useEffect(() => {
    if (activeConversationCivId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveConversationCivId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeConversationCivId]);

  useEffect(() => {
    if (activeConversationCivId === null) return;
    setMessageTargetId(activeConversationCivId);
  }, [activeConversationCivId]);

  const selectedCity = useMemo(() => {
    if (!state || !selectedUnit) return null;
    return (
      state.cities.find(
        (city) => city.q === selectedUnit.q && city.r === selectedUnit.r,
      ) ?? null
    );
  }, [state, selectedUnit]);

  const reachable = useMemo<Set<string>>(() => {
    const result = new Set<string>();
    if (!state || !selectedUnit || selectedUnit.moves_remaining <= 0) return result;
    const here = { q: selectedUnit.q, r: selectedUnit.r };
    for (const t of state.tiles) {
      if (hexDistance(here, { q: t.q, r: t.r }) === 1) {
        result.add(tileKey(t.q, t.r));
      }
    }
    return result;
  }, [state, selectedUnit]);

  const availableTechs = useMemo(() => {
    if (!humanCiv) return [];
    const known = new Set(humanCiv.known_techs);
    return TECHS.filter(
      (tech) =>
        !known.has(tech.id) &&
        tech.prerequisites.every((prereq) => known.has(prereq)),
    );
  }, [humanCiv]);

  const buildableUnits = useMemo(() => {
    if (!humanCiv) return [];
    const known = new Set(humanCiv.known_techs);
    return BUILDABLE_UNITS.filter((u) => u.requires === null || known.has(u.requires));
  }, [humanCiv]);

  const currentResearch = useMemo(() => {
    if (!humanCiv?.researching) return null;
    return TECHS.find((tech) => tech.id === humanCiv.researching) ?? null;
  }, [humanCiv]);

  const selectedProductionCity = useMemo(() => {
    if (!humanCities.length) return null;
    return selectedCity && selectedCity.owner === humanCiv?.id ? selectedCity : humanCities[0];
  }, [humanCities, selectedCity, humanCiv]);

  const activeConversation = useMemo(() => {
    if (!state || !humanCiv || activeConversationCivId === null) return [];
    return state.messages.filter(
      (message) =>
        (message.from_civ_id === humanCiv.id && message.to_civ_id === activeConversationCivId) ||
        (message.to_civ_id === humanCiv.id && message.from_civ_id === activeConversationCivId),
    );
  }, [state, humanCiv, activeConversationCivId]);

  const activeConversationCiv = useMemo(
    () => otherCivs.find((civ) => civ.id === activeConversationCivId) ?? null,
    [otherCivs, activeConversationCivId],
  );

  const activeStance = useMemo(
    () =>
      activeConversationCivId === null
        ? null
        : state?.stances.find((item) => item.other_civ_id === activeConversationCivId) ?? null,
    [state?.stances, activeConversationCivId],
  );

  const activeDiplomaticEvents = useMemo(() => {
    if (activeConversationCivId === null) return [];
    return (state?.diplomatic_events ?? []).filter(
      (event) =>
        event.actor_civ_id === activeConversationCivId ||
        event.target_civ_id === activeConversationCivId,
    );
  }, [state?.diplomatic_events, activeConversationCivId]);

  const availableMessageKinds = useMemo(() => {
    const truceBlocksHostility = activeStance?.truce_active ?? false;
    return MESSAGE_KINDS.filter((kind) => {
      if (!truceBlocksHostility) return true;
      return kind.id !== "declare_war" && kind.id !== "threat";
    });
  }, [activeStance]);

  const inboxCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const message of state?.inbox ?? []) {
      counts.set(message.from_civ_id, (counts.get(message.from_civ_id) ?? 0) + 1);
    }
    return counts;
  }, [state?.inbox]);

  const totalInbox = useMemo(() => state?.inbox.length ?? 0, [state?.inbox]);

  useEffect(() => {
    if (availableMessageKinds.some((kind) => kind.id === messageKind)) return;
    setMessageKind(availableMessageKinds[0]?.id ?? "chat");
  }, [availableMessageKinds, messageKind]);

  const mapFocusHex = useMemo(() => {
    if (selectedUnit) return { q: selectedUnit.q, r: selectedUnit.r };
    const firstHumanCity = humanCities[0];
    if (firstHumanCity) return { q: firstHumanCity.q, r: firstHumanCity.r };
    const firstHumanUnit = humanUnits[0];
    if (firstHumanUnit) return { q: firstHumanUnit.q, r: firstHumanUnit.r };
    return null;
  }, [selectedUnit, humanCities, humanUnits]);

  const hoveredUnit = useMemo(() => {
    if (!state || !hoveredTile) return null;
    return state.units.find((u) => u.q === hoveredTile.q && u.r === hoveredTile.r) ?? null;
  }, [state, hoveredTile]);

  const hoveredCity = useMemo(() => {
    if (!state || !hoveredTile) return null;
    return state.cities.find((c) => c.q === hoveredTile.q && c.r === hoveredTile.r) ?? null;
  }, [state, hoveredTile]);

  const ingestEvents = (next: GameStateDTO) => {
    const prev = prevStateRef.current;
    if (!prev || prev.id !== next.id) {
      prevStateRef.current = next;
      return;
    }
    if (prev.turn === next.turn) {
      prevStateRef.current = next;
      return;
    }
    const events = diffTurnEvents({
      prev,
      next,
      humanCivId: humanCiv?.id ?? null,
    });
    prevStateRef.current = next;
    if (events.length === 0) return;
    setEventLog((current) => [...events, ...current].slice(0, 80));
    setBannerEvents(events);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    bannerTimerRef.current = setTimeout(() => setBannerEvents(null), 4500);
  };

  const run = async (fn: () => Promise<GameStateDTO>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      ingestEvents(next);
      setState(next);
      if (selectedUnit) {
        const updated = next.units.find((u) => u.id === selectedUnit.id) ?? null;
        setSelectedUnit(updated);
      }
      if (hoveredTile) {
        const updatedTile =
          next.tiles.find((t) => t.q === hoveredTile.q && t.r === hoveredTile.r) ?? null;
        setHoveredTile(updatedTile);
      }
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setBusy(false);
    }
  };

  const endTurn = () => state && run(() => api.resolveTurn(state.id));

  const submitFoundCity = () => {
    if (!state || !pending || !cityName.trim() || !isHumanTurn) return;
    const unit = pending.unit;
    const name = cityName.trim();
    setPending(null);
    setCityName("");
    run(() => api.foundCity(state.id, unit.id, name));
  };

  const openFoundCity = () => {
    if (!selectedUnit || selectedUnit.type !== "settler") return;
    setPending({ kind: "found", unit: selectedUnit });
    setCityName(`City ${(state?.cities.length ?? 0) + 1}`);
  };

  const chooseResearch = async (techId: string) => {
    if (!state || !humanCiv || !techId || !isHumanTurn) return;
    await run(() => api.research(state.id, humanCiv.id, techId));
  };

  const queueProduction = async (cityId: number, unitType: string) => {
    if (!state || !humanCiv || !isHumanTurn) return;
    await run(() => api.build(state.id, humanCiv.id, cityId, unitType));
  };

  const startImprovement = async (unitId: number, improvement: string) => {
    if (!state || !humanCiv || !isHumanTurn) return;
    await run(() => api.improve(state.id, unitId, improvement));
  };

  const sendMessage = async () => {
    if (!state || !humanCiv || !messageTargetId || !messageText.trim() || !isHumanTurn) return;
    if (
      activeStance?.truce_active &&
      (messageKind === "declare_war" || messageKind === "threat")
    ) {
      setError(
        `Truce in force until turn ${activeStance.truce_until}. Hostile messages are blocked.`,
      );
      return;
    }
    const text = messageText.trim();
    await run(() =>
      api.sendMessage(state.id, humanCiv.id, messageTargetId, messageKind, text),
    );
    setMessageText("");
  };

  const onTileClick = (q: number, r: number) => {
    if (!state || !selectedUnit || !isHumanTurn) return;
    const here = { q: selectedUnit.q, r: selectedUnit.r };
    if (hexDistance(here, { q, r }) !== 1) return;
    const occupant = state.units.find((u) => u.q === q && u.r === r);
    if (occupant && occupant.owner !== selectedUnit.owner) {
      if (!canAttackOwner(state, selectedUnit.owner, occupant.owner)) {
        setError("You must declare war before attacking this civilization.");
        return;
      }
      run(() => api.attack(state.id, selectedUnit.id, occupant.id));
      return;
    }
    run(() => api.move(state.id, selectedUnit.id, q, r));
  };

  const onUnitClick = (u: UnitDTO) => {
    if (!state) return;
    if (!isHumanTurn && u.owner === humanCiv?.id) {
      setSelectedUnit(u);
      return;
    }
    if (selectedUnit && u.id !== selectedUnit.id && u.owner !== selectedUnit.owner) {
      const here = { q: selectedUnit.q, r: selectedUnit.r };
      if (hexDistance(here, { q: u.q, r: u.r }) === 1) {
        if (!canAttackOwner(state, selectedUnit.owner, u.owner)) {
          setError("You must declare war before attacking this civilization.");
          return;
        }
        run(() => api.attack(state.id, selectedUnit.id, u.id));
        return;
      }
    }
    setSelectedUnit(u);
  };

  const humanColor = humanCiv ? CIV_COLORS[humanCiv.id % CIV_COLORS.length] : "#b08a44";
  const highlightedTileKey = hoveredTile ? tileKey(hoveredTile.q, hoveredTile.r) : null;
  const needsResearch = humanCiv !== null && !currentResearch && availableTechs.length > 0;
  const needsProduction =
    humanCities.length > 0 && selectedProductionCity?.production_queue.length === 0;
  const needsSelection = humanUnits.length > 0 && !selectedUnit && isHumanTurn;
  const nextObjective = !humanCities.length
    ? "Settle your first city on secure terrain."
    : needsResearch
      ? "Select the next technology before the next turn."
      : needsProduction
        ? `Queue production in ${selectedProductionCity?.name ?? "your city"}.`
        : totalInbox > 0
          ? "Review diplomatic replies from rival leaders."
          : needsSelection
            ? "Select a unit and issue a field order."
            : "Expand your borders and pressure rival factions.";
  const researchProgress = currentResearch
    ? Math.min(humanCiv?.science ?? 0, currentResearch.cost)
    : 0;

  if (!hasStarted) {
    return (
      <main className="start-screen">
        <div className="start-screen__veil" />
        <section className="start-screen__panel">
          <div className="plate-label">Inf-3600 Strategy Sandbox</div>
          <h1>Forge a Civilization.</h1>
          <p className="start-screen__copy">
            Command a modern 4X campaign with a map-first interface built for fast tactical
            reading, deliberate expansion, and tense turn-to-turn decisions.
          </p>

          <div className="start-screen__grid">
            <label className="field">
              <span className="field-label">Civilization Name</span>
              <input
                type="text"
                maxLength={40}
                value={setup.humanName}
                onChange={(e) =>
                  setSetup((prev) => ({
                    ...prev,
                    humanName: e.target.value,
                  }))
                }
                placeholder="Athens"
              />
            </label>
            <label className="field">
              <span className="field-label">Map Radius</span>
              <input
                type="number"
                min={2}
                max={32}
                value={setup.radius}
                onChange={(e) =>
                  setSetup((prev) => ({
                    ...prev,
                    radius: Number(e.target.value) || prev.radius,
                  }))
                }
              />
            </label>
          </div>

          <div className="start-screen__meta">
            <span>Fresh seed each session</span>
            <span>Single-screen command table</span>
            <span>Mouse-first tactical play</span>
          </div>

          <div className="start-screen__actions">
            <button className="button-primary" onClick={beginGame} disabled={busy}>
              {busy ? "Generating World..." : "Begin Campaign"}
            </button>
          </div>
        </section>
        {error && <div className="toast">{error}</div>}
      </main>
    );
  }

  if (!state) {
    return (
      <main className="start-screen">
        <div className="start-screen__veil" />
        <section className="start-screen__panel start-screen__panel--loading">
          <div className="spinner" />
          <p className="start-screen__copy">
            Surveying the land, placing the first capitals, and opening the campaign map.
          </p>
        </section>
        {error && <div className="toast">{error}</div>}
      </main>
    );
  }

  return (
    <main className="war-room">
      <header className="war-room__topbar">
        <div className="empire-badge">
          <div className="empire-badge__seal" style={{ background: humanColor }}>
            {humanCiv?.name?.slice(0, 1) ?? "A"}
          </div>
          <div className="empire-badge__copy">
            <div className="empire-badge__name">{humanCiv?.name ?? "Civilization"}</div>
            <div className="empire-badge__sub">
              {humanCiv?.leader_name ?? "Unknown Leader"}
            </div>
            <div className="empire-badge__sub empire-badge__objective">
              {nextObjective}
            </div>
          </div>
        </div>

        <div className="war-room__metrics">
          <TopMetric label="Science" value={humanCiv?.science ?? 0} />
          <TopMetric
            label="Gold"
            value={humanCiv?.gold ?? 0}
            delta={formatNetDelta(
              (humanCiv?.gold_income ?? 0) - (humanCiv?.gold_upkeep ?? 0),
            )}
          />
          <TopMetric label="Culture" value={humanCiv?.culture ?? 0} />
          <TopMetric
            label="Score"
            value={humanCiv?.score ?? 0}
            delta={`/ ${state.score_threshold}`}
          />
          <TopMetric label="Cities" value={humanCities.length} />
        </div>

        <div className="war-room__turnbox">
          <div className="map-mode-toggle" role="tablist" aria-label="Map view mode">
            <button
              type="button"
              className={`map-mode-toggle__button${mapViewMode === "global" ? " is-active" : ""}`}
              onClick={() => setMapViewMode("global")}
            >
              Global
            </button>
            <button
              type="button"
              className={`map-mode-toggle__button${mapViewMode === "local" ? " is-active" : ""}`}
              onClick={() => setMapViewMode("local")}
            >
              Local
            </button>
          </div>
          <div className="turn-box__meta">
            <span className="plate-label">Turn</span>
            <strong>{state.turn}</strong>
            <span className={`turn-state${isHumanTurn ? " is-live" : ""}`}>
              {isHumanTurn
                ? "Your Move"
                : `${state.civs.find((c) => c.id === state.current_civ_id)?.name ?? "AI"} Acting`}
            </span>
          </div>
          <button className="button-primary end-turn" onClick={endTurn} disabled={busy || !isHumanTurn}>
            {busy ? "Resolving..." : "End Turn"}
          </button>
        </div>
      </header>

      <section className="war-room__layout">
        <aside className="war-room__rail war-room__rail--left">
          <Panel label="Minimap" title={`Turn ${state.turn}`}>
            <MiniMap tiles={state.tiles} visibleTiles={activeVisibleTiles} focusHex={mapFocusHex} />
          </Panel>

          <Panel
            label={selectedUnit ? `Selected · ${capitalize(selectedUnit.type)}` : "Selection"}
            title={selectedUnit ? `${capitalize(selectedUnit.type)} #${selectedUnit.id}` : "No Unit Selected"}
          >
            {selectedUnit ? (
              <div className="selection-stack">
                <div className="selection-hero">
                  <div
                    className="selection-hero__glyph"
                    style={{ background: CIV_COLORS[selectedUnit.owner % CIV_COLORS.length] }}
                  >
                    {selectedUnit.type.slice(0, 1).toUpperCase()}
                  </div>
                  <div>
                    <div className="selection-hero__tile">
                      Tile {selectedUnit.q}, {selectedUnit.r}
                    </div>
                    <div className="selection-hero__sub">
                      {selectedCity ? `Garrisoned in ${selectedCity.name}` : "Field formation"}
                    </div>
                  </div>
                </div>

                <div className="stat-grid">
                  <MetricStat
                    label="Health"
                    value={`${selectedUnit.health}/${maxHealthFor(selectedUnit.type)}`}
                  />
                  <MetricStat label="Moves" value={selectedUnit.moves_remaining} />
                  <MetricStat label="Owner" value={state.civs[selectedUnit.owner]?.name ?? "Unknown"} />
                </div>

                <div className="selection-actions">
                  <button onClick={() => setSelectedUnit(null)}>Clear</button>
                  {selectedUnit.type === "settler" && (
                    <button
                      className="button-primary"
                      onClick={openFoundCity}
                      disabled={busy || !isHumanTurn}
                    >
                      Found City
                    </button>
                  )}
                </div>

                {selectedUnit.type === "worker" && (
                  <>
                    <div className="plate-label">Build Improvement</div>
                    {selectedUnit.work_order ? (
                      <EmptyCopy>
                        Building {selectedUnit.work_order.improvement} —{" "}
                        {selectedUnit.work_order.turns_remaining} turn(s) left.
                      </EmptyCopy>
                    ) : (
                      <div className="list-stack">
                        {IMPROVEMENT_OPTIONS.map((opt) => (
                          <button
                            key={opt.id}
                            className="list-row"
                            onClick={() => startImprovement(selectedUnit.id, opt.id)}
                            disabled={busy || !isHumanTurn}
                            title={opt.desc}
                          >
                            <span>{opt.label}</span>
                            <span>{opt.desc}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <EmptyCopy>
                Select a unit on the map to reveal field orders, movement options, and city actions.
              </EmptyCopy>
            )}
          </Panel>
        </aside>

        <section className="war-room__mapstage">
          <div className="map-frame">
            <SquareMap
              state={state}
              selectedUnitId={selectedUnit?.id ?? null}
              reachable={reachable}
              highlightedTileKey={highlightedTileKey}
              focusHex={mapFocusHex}
              humanCivId={humanCiv?.id ?? null}
              visibleTiles={activeVisibleTiles}
              onTileClick={onTileClick}
              onTileHover={(q, r) =>
                setHoveredTile(state.tiles.find((t) => t.q === q && t.r === r) ?? null)
              }
              onUnitClick={onUnitClick}
            />

            {bannerEvents && bannerEvents.length > 0 && (
              <div className="map-banner">
                <div className="plate-label">Turn Chronicle</div>
                <ul>
                  {bannerEvents.slice(0, 4).map((event) => (
                    <li key={event.id}>
                      <span className={`log-kind log-kind--${event.kind}`}>{event.kind}</span>
                      <span>{event.text}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {hoveredTile && (
              <div className="terrain-readout">
                <div className="terrain-readout__title">
                  {capitalize(hoveredTile.terrain)}
                  {hoveredTile.feature && (
                    <span> · {FEATURE_LABEL[hoveredTile.feature] ?? hoveredTile.feature}</span>
                  )}
                </div>
                <div className="terrain-readout__yields">
                  <YieldLine label="Food" value={hoveredTile.food} />
                  <YieldLine label="Prod" value={hoveredTile.production} />
                  <YieldLine label="Gold" value={hoveredTile.gold} />
                </div>
                {hoveredTile.resource && (
                  <div className="terrain-readout__sub">
                    Resource · {RESOURCE_LABEL[hoveredTile.resource] ?? hoveredTile.resource}
                  </div>
                )}
                {(hoveredUnit || hoveredCity) && (
                  <div className="terrain-readout__sub">
                    {hoveredUnit
                      ? `${capitalize(hoveredUnit.type)} · ${state.civs[hoveredUnit.owner]?.name ?? "Unknown"} · HP ${hoveredUnit.health}`
                      : `${hoveredCity?.name ?? "City"} · pop ${hoveredCity?.population ?? 0}`}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        <aside className="war-room__rail war-room__rail--right">
          <Panel
            label={`Research · ${currentResearch ? currentResearch.name : "Awaiting Order"}`}
            title={currentResearch ? `${researchProgress} / ${currentResearch.cost}` : "Choose Technology"}
          >
            {currentResearch && (
              <div className="progress-shell">
                <div
                  className="progress-shell__fill"
                  style={{
                    width: `${Math.min(100, (researchProgress / currentResearch.cost) * 100)}%`,
                  }}
                />
              </div>
            )}
            <div className="list-stack scroll-list">
              {availableTechs.length === 0 ? (
                <EmptyCopy>No available technologies. Expand prerequisites or finish the current research.</EmptyCopy>
              ) : (
                availableTechs.map((tech) => (
                  <button
                    key={tech.id}
                    className="list-row"
                    onClick={() => chooseResearch(tech.id)}
                    disabled={busy || !isHumanTurn || humanCiv?.researching === tech.id}
                  >
                    <span>{tech.name}</span>
                    <span>{tech.cost}</span>
                  </button>
                ))
              )}
            </div>
          </Panel>

          <Panel
            label={`City · ${selectedProductionCity?.name ?? "No City"}`}
            title={
              selectedProductionCity
                ? `${selectedProductionCity.production_stored} stored production`
                : "Found a city first"
            }
          >
            {selectedProductionCity ? (
              <>
                <div className="city-brief">
                  <MetricStat label="Population" value={selectedProductionCity.population} />
                  <MetricStat label="Queue" value={selectedProductionCity.production_queue[0] ?? "Idle"} />
                  <MetricStat label="Border" value={`R${selectedProductionCity.border_radius ?? 1}`} />
                  <MetricStat
                    label="Culture"
                    value={
                      selectedProductionCity.border_radius >= 3
                        ? `${selectedProductionCity.culture_stored ?? 0} / max`
                        : `${selectedProductionCity.culture_stored ?? 0} / ${
                            selectedProductionCity.border_radius >= 2 ? 30 : 10
                          }`
                    }
                  />
                </div>
                <div className="list-stack scroll-list">
                  {buildableUnits.map((unit) => (
                    <button
                      key={unit.id}
                      className="list-row"
                      onClick={() => queueProduction(selectedProductionCity.id, unit.id)}
                      disabled={busy || !isHumanTurn}
                    >
                      <span>{unit.label}</span>
                      <span>{unit.cost} prod</span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <EmptyCopy>Your first settlement unlocks production orders and population growth.</EmptyCopy>
            )}
          </Panel>

          <Panel label="Other Leaders" title={`${otherCivs.length} met`}>
            <div className="leader-stack">
              {otherCivs.length === 0 ? (
                <EmptyCopy>No rival leaders discovered yet.</EmptyCopy>
              ) : (
                otherCivs.map((civ) => {
                  const stanceEntry = state.stances.find(
                    (item) => item.other_civ_id === civ.id,
                  );
                  const stance = stanceEntry?.stance ?? "peace";
                  const relationship = stanceEntry?.relationship ?? 0;
                  const truceActive = stanceEntry?.truce_active ?? false;
                  const truceUntil = stanceEntry?.truce_until;
                  const inboxCount = inboxCounts.get(civ.id) ?? 0;
                  return (
                    <button
                      key={civ.id}
                      type="button"
                      className={`leader-row${activeConversationCivId === civ.id ? " is-active" : ""}`}
                      onClick={() => setActiveConversationCivId(civ.id)}
                    >
                      <span
                        className="leader-row__portrait"
                        style={{ background: CIV_COLORS[civ.id % CIV_COLORS.length] }}
                      >
                        {civ.name.slice(0, 1)}
                      </span>
                      <span className="leader-row__body">
                        <strong>{civ.name}</strong>
                        <span>
                          {capitalize(stance)}
                          {" · "}
                          <span style={{ color: relationshipColor(relationship) }}>
                            {relationship >= 0 ? "+" : ""}
                            {relationship} {relationshipLabel(relationship)}
                          </span>
                          {truceActive ? ` · Truce T${truceUntil}` : ""}
                          {inboxCount > 0 ? ` · ${inboxCount} new` : ""}
                        </span>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </Panel>

          <Panel label="Standings" title={`Goal · ${state.score_threshold}`}>
            <div className="list-stack">
              {state.standings.map((entry) => {
                const isMe = humanCiv?.id === entry.civ_id;
                return (
                  <div
                    key={entry.civ_id}
                    className="list-row"
                    style={{ cursor: "default", fontWeight: isMe ? 700 : 400 }}
                  >
                    <span>
                      {entry.name}
                      {isMe ? " (you)" : ""}
                    </span>
                    <span>
                      {entry.score} / {state.score_threshold}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </aside>
      </section>

      <section
        className={`war-room__chronicle${chronicleCollapsed ? " is-collapsed" : ""}`}
      >
        <div className="chronicle-tabs">
          <div className="chronicle-tab is-active">Events</div>
          {totalInbox > 0 && (
            <button
              type="button"
              className="chronicle-tab chronicle-tab--badge"
              onClick={() => {
                if (otherCivs[0]) setActiveConversationCivId(otherCivs[0].id);
              }}
              title="Open diplomacy drawer"
            >
              Inbox ({totalInbox})
            </button>
          )}
          <button
            type="button"
            className="chronicle-collapse"
            onClick={() => setChronicleCollapsed((c) => !c)}
            aria-label={chronicleCollapsed ? "Expand chronicle" : "Collapse chronicle"}
            title={chronicleCollapsed ? "Expand" : "Collapse"}
          >
            {chronicleCollapsed ? "▴ Show" : "▾ Hide"}
          </button>
        </div>

        {!chronicleCollapsed && (
          <div className="chronicle-grid">
            {eventLog.length === 0 ? (
              <EmptyCopy>No events recorded yet. Resolve a turn to populate the chronicle.</EmptyCopy>
            ) : (
              eventLog.slice(0, 9).map((event) => (
                <div key={event.id} className="log-row">
                  <span className={`log-kind log-kind--${event.kind}`}>{event.kind}</span>
                  <p>{event.text}</p>
                  <span className="log-turn">T-{event.turn}</span>
                </div>
              ))
            )}
          </div>
        )}
      </section>

      {pending?.kind === "found" && (
        <div
          className="modal-backdrop"
          onClick={() => {
            setPending(null);
            setCityName("");
          }}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="plate-label">New Settlement</div>
            <h2>Name Your City</h2>
            <input
              type="text"
              value={cityName}
              onChange={(e) => setCityName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitFoundCity();
                if (e.key === "Escape") {
                  setPending(null);
                  setCityName("");
                }
              }}
              placeholder="e.g. Athens"
              autoFocus
            />
            <div className="modal-actions">
              <button
                onClick={() => {
                  setPending(null);
                  setCityName("");
                }}
              >
                Cancel
              </button>
              <button className="button-primary" onClick={submitFoundCity} disabled={!cityName.trim()}>
                Found City
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diplomacy drawer — slides in from the right when a leader is selected. */}
      <aside
        className={`diplomacy-drawer${activeConversationCivId !== null ? " is-open" : ""}`}
        aria-hidden={activeConversationCivId === null}
      >
        {activeConversationCiv && (
          <>
            <header className="diplomacy-drawer__header">
              <div className="diplomacy-drawer__heading">
                <span
                  className="leader-row__portrait diplomacy-drawer__portrait"
                  style={{ background: CIV_COLORS[activeConversationCiv.id % CIV_COLORS.length] }}
                >
                  {activeConversationCiv.name.slice(0, 1)}
                </span>
                <div>
                  <div className="plate-label">Open Channel</div>
                  <strong>{activeConversationCiv.name}</strong>
                  <div className="diplomacy-drawer__leader">
                    {activeConversationCiv.leader_name}
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="diplomacy-drawer__close"
                onClick={() => setActiveConversationCivId(null)}
                aria-label="Close diplomacy"
              >
                ×
              </button>
            </header>

            {activeStance && (
              <div className="thread-pills">
                <span className="thread-pill">
                  <span className="thread-pill__label">Status</span>
                  {capitalize(activeStance.stance)}
                </span>
                <span
                  className="thread-pill"
                  style={{ color: relationshipColor(activeStance.relationship) }}
                >
                  <span className="thread-pill__label">Rel</span>
                  {activeStance.relationship >= 0 ? "+" : ""}
                  {activeStance.relationship} {relationshipLabel(activeStance.relationship)}
                </span>
                {activeStance.truce_active && (
                  <span className="thread-pill">
                    <span className="thread-pill__label">Truce</span>
                    until T{activeStance.truce_until}
                  </span>
                )}
              </div>
            )}

            <div className="diplomacy-drawer__messages">
              {activeConversation.length === 0 ? (
                <EmptyCopy>No messages exchanged. Send the first diplomatic signal.</EmptyCopy>
              ) : (
                [...activeConversation].reverse().map((message, index) => (
                  <MessageCard
                    key={`${message.turn}-${message.from_civ_id}-${message.to_civ_id}-${index}`}
                    message={message}
                    civs={state?.civs ?? []}
                    humanCivId={humanCiv?.id ?? null}
                  />
                ))
              )}
            </div>

            <div className="diplomacy-drawer__composer">
              <label className="field">
                <span className="field-label">Tone</span>
                <select value={messageKind} onChange={(e) => setMessageKind(e.target.value)}>
                  {availableMessageKinds.map((kind) => (
                    <option key={kind.id} value={kind.id}>
                      {kind.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Message</span>
                <input
                  type="text"
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  placeholder={`Reply to ${activeConversationCiv.name}`}
                />
              </label>
              {activeStance?.truce_active && (
                <div className="empty-copy">
                  Truce until turn {activeStance.truce_until}. Threats and war declarations are disabled.
                </div>
              )}
              <button
                className="button-primary"
                onClick={sendMessage}
                disabled={busy || !isHumanTurn || !messageText.trim()}
              >
                Send
              </button>
            </div>

            {activeDiplomaticEvents.length > 0 && (
              <details className="incidents-details">
                <summary>
                  Recent Incidents ({activeDiplomaticEvents.length})
                </summary>
                <div className="list-stack">
                  {[...activeDiplomaticEvents].reverse().slice(0, 8).map((event, index) => (
                    <div
                      key={`${event.turn}-${event.kind}-${index}`}
                      className="list-row"
                      style={{ cursor: "default" }}
                    >
                      <span>
                        T{event.turn} · {capitalize(event.kind)}
                      </span>
                      <span>
                        {event.relationship_delta >= 0 ? "+" : ""}
                        {event.relationship_delta}
                      </span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </aside>

      {error && <div className="toast">{error}</div>}
    </main>
  );
}

function Panel({
  label,
  title,
  children,
}: {
  label: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel__head">
        <span className="plate-label">{label}</span>
        <span className="panel__title">{title}</span>
      </div>
      <div className="panel__body">{children}</div>
    </section>
  );
}

function TopMetric({
  label,
  value,
  delta,
}: {
  label: string;
  value: number;
  delta?: string;
}) {
  return (
    <div className="top-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      {delta && <em>{delta}</em>}
    </div>
  );
}

function MetricStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function YieldLine({ label, value }: { label: string; value: number }) {
  return (
    <span className="yield-line">
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function EmptyCopy({ children }: { children: React.ReactNode }) {
  return <p className="empty-copy">{children}</p>;
}

function MiniMap({
  tiles,
  visibleTiles,
  focusHex,
}: {
  tiles: GameStateDTO["tiles"];
  visibleTiles: Set<string>;
  focusHex: { q: number; r: number } | null;
}) {
  if (tiles.length === 0) return <div className="minimap" />;

  const qs = tiles.map((tile) => tile.q);
  const rs = tiles.map((tile) => tile.r);
  const minQ = Math.min(...qs);
  const maxQ = Math.max(...qs);
  const minR = Math.min(...rs);
  const maxR = Math.max(...rs);
  const width = maxQ - minQ + 1;
  const height = maxR - minR + 1;
  const tileMap = new Map(tiles.map((tile) => [tileKey(tile.q, tile.r), tile]));

  return (
    <div
      className="minimap"
      style={{
        gridTemplateColumns: `repeat(${width}, minmax(0, 1fr))`,
      }}
    >
      {Array.from({ length: width * height }, (_, index) => {
        const q = minQ + (index % width);
        const r = minR + Math.floor(index / width);
        const key = tileKey(q, r);
        const tile = tileMap.get(key);
        const visible = visibleTiles.size === 0 || visibleTiles.has(key);
        const focused = focusHex?.q === q && focusHex?.r === r;
        return (
          <span
            key={key}
            className={`minimap__cell${tile ? "" : " is-empty"}${visible ? " is-visible" : ""}${focused ? " is-focused" : ""}`}
            data-terrain={tile?.terrain ?? "void"}
          />
        );
      })}
    </div>
  );
}

function MessageCard({
  message,
  civs,
  humanCivId,
}: {
  message: GameStateDTO["messages"][number];
  civs: GameStateDTO["civs"];
  humanCivId?: number | null;
}) {
  const from = civs.find((civ) => civ.id === message.from_civ_id);
  const to = civs.find((civ) => civ.id === message.to_civ_id);
  const direction =
    humanCivId !== null && humanCivId !== undefined
      ? message.from_civ_id === humanCivId
        ? "Sent"
        : "Received"
      : null;
  return (
    <article className={`message-card${direction === "Sent" ? " is-sent" : ""}`}>
      <div className="message-card__meta">
        <strong>
          {from?.name ?? `Civ ${message.from_civ_id}`} to {to?.name ?? `Civ ${message.to_civ_id}`}
        </strong>
        <span>
          T{message.turn}
          {direction ? ` · ${direction}` : ""}
        </span>
      </div>
      <div className="message-card__kind">{capitalize(message.kind)}</div>
      <p>{message.text}</p>
    </article>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");
}

function formatNetDelta(net: number): string {
  if (net > 0) return `+${net} / t`;
  if (net < 0) return `${net} / t`;
  return "0 / t";
}

// Mirrors UNIT_STATS.max_health from the backend. Keep in sync with
// backend/app/engine/models.py.
const UNIT_MAX_HEALTH: Record<string, number> = {
  settler: 10,
  warrior: 20,
  scout: 10,
  worker: 10,
  archer: 20,
  horseman: 20,
  swordsman: 25,
};

function maxHealthFor(type: string): number {
  return UNIT_MAX_HEALTH[type] ?? 20;
}

function canAttackOwner(
  state: GameStateDTO,
  attackerOwner: number,
  defenderOwner: number,
): boolean {
  if (attackerOwner === defenderOwner) return false;
  const stance = state.stances.find((entry) => entry.other_civ_id === defenderOwner);
  return stance?.stance === "war";
}

function relationshipLabel(score: number): string {
  if (score <= -60) return "Furious";
  if (score <= -30) return "Hostile";
  if (score <= -10) return "Cold";
  if (score < 10) return "Neutral";
  if (score < 30) return "Warm";
  if (score < 60) return "Friendly";
  return "Devoted";
}

function relationshipColor(score: number): string {
  if (score <= -30) return "#d97a6a";
  if (score < 10) return "#bba27a";
  if (score < 30) return "#dfca85";
  return "#8fcf7a";
}

function formatError(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
