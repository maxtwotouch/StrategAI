"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { HexMap } from "@/components/HexMap";
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
type BottomTab = "diplomacy" | "log";

type TechDef = {
  id: string;
  name: string;
  cost: number;
  prerequisites: string[];
};

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

const BUILDABLE_UNITS = [
  { id: "warrior", label: "Warrior", cost: 10 },
  { id: "scout", label: "Scout", cost: 8 },
  { id: "settler", label: "Settler", cost: 15 },
];

const MESSAGE_KINDS = [
  { id: "chat", label: "Chat" },
  { id: "threat", label: "Threat" },
  { id: "offer_peace", label: "Offer Peace" },
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
  const [setup, setSetup] = useState<Setup>({ radius: 8, seed: 1, humanName: "Athens" });
  const [messageTargetId, setMessageTargetId] = useState<number | null>(null);
  const [messageKind, setMessageKind] = useState("chat");
  const [messageText, setMessageText] = useState("");
  const [activeConversationCivId, setActiveConversationCivId] = useState<number | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>("diplomacy");
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
      setBannerEvents(null);
      setEventLog([]);
      prevStateRef.current = next;
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setBusy(false);
    }
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

  useEffect(() => {
    if (messageTargetId !== null) return;
    if (otherCivs.length === 0) return;
    setMessageTargetId(otherCivs[0].id);
  }, [messageTargetId, otherCivs]);

  useEffect(() => {
    if (activeConversationCivId !== null) return;
    if (otherCivs.length === 0) return;
    setActiveConversationCivId(otherCivs[0].id);
  }, [activeConversationCivId, otherCivs]);

  useEffect(() => {
    if (activeConversationCivId === null) return;
    setMessageTargetId(activeConversationCivId);
  }, [activeConversationCivId]);

  const selectedCity = useMemo(() => {
    if (!state || !selectedUnit) return null;
    return state.cities.find(
      (city) => city.q === selectedUnit.q && city.r === selectedUnit.r,
    ) ?? null;
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

  const inboxCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const message of state?.inbox ?? []) {
      counts.set(message.from_civ_id, (counts.get(message.from_civ_id) ?? 0) + 1);
    }
    return counts;
  }, [state?.inbox]);

  const totalInbox = useMemo(() => state?.inbox.length ?? 0, [state?.inbox]);

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

  const sendMessage = async () => {
    if (!state || !humanCiv || !messageTargetId || !messageText.trim() || !isHumanTurn) return;
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
        run(() => api.attack(state.id, selectedUnit.id, u.id));
        return;
      }
    }
    setSelectedUnit(u);
  };

  const canFound = selectedUnit?.type === "settler";
  const highlightedTileKey = hoveredTile ? tileKey(hoveredTile.q, hoveredTile.r) : null;

  if (!hasStarted) {
    return (
      <main className="start-shell">
        <div className="start-card">
          <p className="eyebrow">Inf-3600 Strategy Sandbox</p>
          <h1 className="display-title">AI Civilization</h1>
          <p className="muted" style={{ marginBottom: "1.4rem" }}>
            Build a city, scout the world, and outwit AI-led civilizations.
          </p>
          <div className="setup-grid">
            <label className="field">
              <span className="field-label">Your Civilization</span>
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
                max={18}
                value={setup.radius}
                onChange={(e) =>
                  setSetup((prev) => ({
                    ...prev,
                    radius: Number(e.target.value) || prev.radius,
                  }))
                }
              />
            </label>
            <label className="field">
              <span className="field-label">Seed</span>
              <input
                type="number"
                value={setup.seed}
                onChange={(e) =>
                  setSetup((prev) => ({
                    ...prev,
                    seed: Number(e.target.value) || 0,
                  }))
                }
              />
            </label>
          </div>
          <div className="button-row">
            <button className="primary" onClick={() => loadGame(setup)} disabled={busy}>
              {busy ? "Carving the world..." : "Begin"}
            </button>
          </div>
        </div>
        {error && <div className="toast">{error}</div>}
      </main>
    );
  }

  if (!state) {
    return (
      <main className="start-shell">
        <div className="spinner" />
        <p className="muted">Preparing the map and summoning the first civilizations.</p>
        {error && <div className="toast">{error}</div>}
      </main>
    );
  }

  const humanColor = humanCiv ? CIV_COLORS[humanCiv.id % CIV_COLORS.length] : "#888";
  const researchProgress = currentResearch
    ? Math.min(humanCiv?.science ?? 0, currentResearch.cost)
    : 0;

  return (
    <main className="game-shell">
      <header className="game-topbar">
        <div className="topbar-left">
          <span
            className="civ-medallion"
            style={{ background: humanColor }}
            aria-hidden
          />
          <div>
            <div className="topbar-civ">{humanCiv?.name ?? "Civilization"}</div>
            <div className="topbar-leader">{humanCiv?.leader_name ?? ""}</div>
          </div>
        </div>
        <div className="topbar-center">
          <ResourcePill icon="✦" label="Science" value={humanCiv?.science ?? 0} />
          <ResourcePill icon="◈" label="Gold" value={humanCiv?.gold ?? 0} />
          <ResourcePill icon="❀" label="Culture" value={humanCiv?.culture ?? 0} />
          <ResourcePill icon="⛬" label="Cities" value={humanCities.length} />
          <ResourcePill icon="⚔" label="Units" value={humanUnits.length} />
        </div>
        <div className="topbar-right">
          <div className="turn-block">
            <span className="turn-label">Turn</span>
            <span className="turn-value">{state.turn}</span>
          </div>
          <div className="turn-status">
            {isHumanTurn ? (
              <span className="status-dot status-go">Your turn</span>
            ) : (
              <span className="status-dot status-wait">
                {state.civs.find((c) => c.id === state.current_civ_id)?.name ?? "AI"} thinking…
              </span>
            )}
          </div>
          <button className="primary end-turn" onClick={endTurn} disabled={busy || !isHumanTurn}>
            {busy ? "Resolving…" : "End Turn"}
          </button>
        </div>
      </header>

      <section className="game-body">
        <div className="map-stage-full">
          <HexMap
            state={state}
            selectedUnitId={selectedUnit?.id ?? null}
            reachable={reachable}
            highlightedTileKey={highlightedTileKey}
            focusHex={mapFocusHex}
            humanCivId={humanCiv?.id ?? null}
            visibleTiles={visibleTiles}
            onTileClick={onTileClick}
            onTileHover={(q, r) =>
              setHoveredTile(state.tiles.find((t) => t.q === q && t.r === r) ?? null)
            }
            onUnitClick={onUnitClick}
          />

          {bannerEvents && bannerEvents.length > 0 && (
            <div className="turn-banner">
              <div className="turn-banner-head">
                <span className="eyebrow">Turn {state.turn} resolved</span>
              </div>
              <ul>
                {bannerEvents.slice(0, 6).map((event) => (
                  <li key={event.id} className={`event-row event-${event.kind}`}>
                    <span className="event-bullet" />
                    <span>{event.text}</span>
                  </li>
                ))}
                {bannerEvents.length > 6 && (
                  <li className="event-row event-more">
                    +{bannerEvents.length - 6} more — see Event Log
                  </li>
                )}
              </ul>
            </div>
          )}

          {hoveredTile && (
            <div className="tile-hover-card">
              <div className="hover-title">
                {capitalize(hoveredTile.terrain)}
                {hoveredTile.feature && (
                  <span className="hover-sub">
                    · {FEATURE_LABEL[hoveredTile.feature] ?? hoveredTile.feature}
                  </span>
                )}
              </div>
              <div className="hover-row">
                <YieldChip icon="🌾" label="Food" value={hoveredTile.food} />
                <YieldChip icon="⚒" label="Prod" value={hoveredTile.production} />
                <YieldChip icon="◈" label="Gold" value={hoveredTile.gold} />
                {hoveredTile.river && <YieldChip icon="≈" label="River" value="+" />}
              </div>
              {hoveredTile.resource && (
                <div className="hover-resource">
                  ◇ {RESOURCE_LABEL[hoveredTile.resource] ?? hoveredTile.resource}
                </div>
              )}
              {hoveredUnit && (
                <div className="hover-entity">
                  <span
                    className="civ-badge"
                    style={{ background: CIV_COLORS[hoveredUnit.owner % CIV_COLORS.length] }}
                  />
                  {capitalize(hoveredUnit.type)} · {state.civs[hoveredUnit.owner]?.name ?? "?"}
                  {" · "}
                  HP {hoveredUnit.health}
                </div>
              )}
              {hoveredCity && (
                <div className="hover-entity">
                  <span
                    className="civ-badge"
                    style={{ background: CIV_COLORS[hoveredCity.owner % CIV_COLORS.length] }}
                  />
                  {hoveredCity.name} · pop {hoveredCity.population}
                </div>
              )}
              <div className="hover-coord">
                ({hoveredTile.q}, {hoveredTile.r})
              </div>
            </div>
          )}
        </div>

        <aside className="game-sidebar">
          <div className="card selection-card">
            <h2>Selection</h2>
            {selectedUnit ? (
              <div className="stack">
                <div className="entity-head">
                  <span
                    className="civ-badge"
                    style={{ background: CIV_COLORS[selectedUnit.owner % CIV_COLORS.length] }}
                  />
                  <strong style={{ textTransform: "capitalize" }}>
                    {selectedUnit.type} #{selectedUnit.id}
                  </strong>
                </div>
                <StatRow label="Owner" value={state.civs[selectedUnit.owner]?.name ?? "Unknown"} />
                <StatRow label="Health" value={selectedUnit.health} />
                <StatRow label="Moves" value={selectedUnit.moves_remaining} />
                <StatRow label="Position" value={`(${selectedUnit.q}, ${selectedUnit.r})`} />
                {selectedCity && (
                  <div className="note-box">
                    Standing inside <strong>{selectedCity.name}</strong>.
                  </div>
                )}
                <div className="button-row">
                  <button onClick={() => setSelectedUnit(null)}>Clear</button>
                  <button
                    className="primary"
                    onClick={openFoundCity}
                    disabled={busy || !canFound || !isHumanTurn}
                  >
                    Found City
                  </button>
                </div>
              </div>
            ) : (
              <p className="faint" style={{ margin: 0 }}>
                Click a unit on the map to issue commands.
              </p>
            )}
          </div>

          <div className="card">
            <h2>Research</h2>
            {currentResearch ? (
              <div className="progress-block">
                <div className="progress-label">
                  <strong>{currentResearch.name}</strong>
                  <span className="faint">
                    {researchProgress}/{currentResearch.cost}
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${Math.min(100, (researchProgress / currentResearch.cost) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            ) : (
              <p className="faint" style={{ margin: 0, marginBottom: "0.6rem" }}>
                Pick a tech to begin research.
              </p>
            )}
            <div className="tech-list">
              {availableTechs.length === 0 ? (
                <p className="faint" style={{ margin: 0 }}>
                  No available techs — meet prereqs first.
                </p>
              ) : (
                availableTechs.slice(0, 6).map((tech) => (
                  <button
                    key={tech.id}
                    className="tech-button"
                    onClick={() => chooseResearch(tech.id)}
                    disabled={busy || !isHumanTurn || humanCiv?.researching === tech.id}
                  >
                    <span>{tech.name}</span>
                    <span className="faint">{tech.cost} sci</span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="card">
            <h2>Production</h2>
            {selectedProductionCity ? (
              <div className="stack">
                <div className="note-box">
                  Queue for <strong>{selectedProductionCity.name}</strong> ·{" "}
                  {selectedProductionCity.production_stored} stored
                </div>
                {selectedProductionCity.production_queue.length > 0 && (
                  <div className="faint">
                    Queued: {selectedProductionCity.production_queue.join(" → ")}
                  </div>
                )}
                <div className="tech-list">
                  {BUILDABLE_UNITS.map((unit) => (
                    <button
                      key={unit.id}
                      className="tech-button"
                      onClick={() => queueProduction(selectedProductionCity.id, unit.id)}
                      disabled={busy || !isHumanTurn}
                    >
                      <span>{unit.label}</span>
                      <span className="faint">{unit.cost} prod</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="faint" style={{ margin: 0 }}>
                Found a city to start queueing production.
              </p>
            )}
          </div>

          <div className="card">
            <h2>Cities</h2>
            {humanCities.length === 0 ? (
              <p className="faint" style={{ margin: 0 }}>
                No cities yet — your settler is the first priority.
              </p>
            ) : (
              <div className="stack">
                {humanCities.map((city) => (
                  <CityCard key={city.id} city={city} />
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Civilizations</h2>
            <div className="stack">
              {state.civs.map((c) => (
                <div key={c.id} className="empire-row">
                  <div className="entity-head">
                    <span
                      className="civ-badge"
                      style={{ background: CIV_COLORS[c.id % CIV_COLORS.length] }}
                    />
                    <strong>{c.name}</strong>
                    {c.is_human && <span className="tag">YOU</span>}
                  </div>
                  <div className="faint">
                    {c.leader_name} · sci {c.science} · techs {c.known_techs.length}
                  </div>
                  {!c.is_human && (
                    <div className="faint">
                      {state.known_civ_ids.includes(c.id) ? "Met" : "Unmet"}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <section className="bottom-drawer card">
        <div className="drawer-tabs">
          <button
            type="button"
            className={`drawer-tab${bottomTab === "diplomacy" ? " is-active" : ""}`}
            onClick={() => setBottomTab("diplomacy")}
          >
            Diplomacy {totalInbox > 0 && <span className="tag">{totalInbox}</span>}
          </button>
          <button
            type="button"
            className={`drawer-tab${bottomTab === "log" ? " is-active" : ""}`}
            onClick={() => setBottomTab("log")}
          >
            Event Log {eventLog.length > 0 && <span className="tag">{eventLog.length}</span>}
          </button>
        </div>
        {bottomTab === "diplomacy" ? (
          <div className="diplomacy-panel">
            {otherCivs.length === 0 ? (
              <p className="faint" style={{ margin: 0 }}>
                Meet another civilization to open a diplomatic conversation.
              </p>
            ) : (
              <div className="diplomacy-layout">
                <div className="conversation-list">
                  {otherCivs.map((civ) => {
                    const stance = state.stances.find(
                      (item) => item.other_civ_id === civ.id,
                    );
                    return (
                      <button
                        key={civ.id}
                        type="button"
                        className={`conversation-row${activeConversationCivId === civ.id ? " is-active" : ""}`}
                        onClick={() => setActiveConversationCivId(civ.id)}
                      >
                        <div className="entity-head">
                          <span
                            className="civ-badge"
                            style={{ background: CIV_COLORS[civ.id % CIV_COLORS.length] }}
                          />
                          <strong>{civ.name}</strong>
                          {(inboxCounts.get(civ.id) ?? 0) > 0 && (
                            <span className="tag">{inboxCounts.get(civ.id)}</span>
                          )}
                        </div>
                        <div className="faint">
                          {civ.leader_name} · {capitalize(stance?.stance ?? "peace")}
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="conversation-pane">
                  <div className="conversation-header">
                    <div>
                      <strong>{activeConversationCiv?.name ?? "No conversation selected"}</strong>
                      {activeConversationCiv && (
                        <div className="faint">{activeConversationCiv.leader_name}</div>
                      )}
                    </div>
                    {activeConversationCiv && (
                      <span className="tag">
                        {capitalize(
                          state.stances.find(
                            (item) => item.other_civ_id === activeConversationCiv.id,
                          )?.stance ?? "peace",
                        )}
                      </span>
                    )}
                  </div>
                  <div className="conversation-thread">
                    {activeConversation.length === 0 ? (
                      <p className="faint" style={{ margin: 0 }}>
                        No messages yet. Send the first one.
                      </p>
                    ) : (
                      [...activeConversation].reverse().map((message, index) => (
                        <MessageCard
                          key={`${message.turn}-${message.from_civ_id}-${message.to_civ_id}-${index}`}
                          message={message}
                          civs={state.civs}
                          humanCivId={humanCiv?.id ?? null}
                        />
                      ))
                    )}
                  </div>
                  <div className="conversation-composer">
                    <label className="field">
                      <span className="field-label">Tone</span>
                      <select value={messageKind} onChange={(e) => setMessageKind(e.target.value)}>
                        {MESSAGE_KINDS.map((kind) => (
                          <option key={kind.id} value={kind.id}>
                            {kind.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="field-label">Reply</span>
                      <input
                        type="text"
                        value={messageText}
                        onChange={(e) => setMessageText(e.target.value)}
                        placeholder={
                          activeConversationCiv
                            ? `Reply to ${activeConversationCiv.name}`
                            : "Choose a civilization to begin"
                        }
                      />
                    </label>
                    <div className="button-row" style={{ marginTop: 0 }}>
                      <button
                        onClick={sendMessage}
                        disabled={
                          busy ||
                          !isHumanTurn ||
                          !messageText.trim() ||
                          activeConversationCivId === null
                        }
                      >
                        Send Reply
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="event-log">
            {eventLog.length === 0 ? (
              <p className="faint" style={{ margin: 0 }}>
                No events yet. End a turn to see what happens.
              </p>
            ) : (
              <ul>
                {eventLog.map((event) => (
                  <li key={event.id} className={`event-row event-${event.kind}`}>
                    <span className="tag">T{event.turn}</span>
                    <span>{event.text}</span>
                  </li>
                ))}
              </ul>
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
            <h2>Name Your City</h2>
            <input
              type="text"
              value={cityName}
              onChange={(e) => setCityName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitFoundCity();
                if (e.key === "Escape") setPending(null);
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
              <button className="primary" onClick={submitFoundCity} disabled={!cityName.trim()}>
                Found
              </button>
            </div>
          </div>
        </div>
      )}

      {error && <div className="toast">{error}</div>}
    </main>
  );
}

function ResourcePill({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <div className="resource-pill" title={label}>
      <span className="resource-icon">{icon}</span>
      <span className="resource-value">{value}</span>
      <span className="resource-label">{label}</span>
    </div>
  );
}

function YieldChip({ icon, label, value }: { icon: string; label: string; value: number | string }) {
  return (
    <span className="yield-chip" title={label}>
      <span>{icon}</span>
      <strong>{value}</strong>
    </span>
  );
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-row">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CityCard({ city }: { city: CityDTO }) {
  return (
    <div className="city-card">
      <div className="entity-head">
        <strong>{city.name}</strong>
        <span className="tag">Pop {city.population}</span>
      </div>
      <div className="faint">
        Food {city.food_stored} · Production {city.production_stored}
      </div>
      <div className="faint">
        Queue {city.production_queue.length > 0 ? city.production_queue.join(", ") : "empty"}
      </div>
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
    <div className={`message-card${direction === "Sent" ? " is-sent" : " is-received"}`}>
      <div className="entity-head">
        <strong>
          {from?.name ?? `Civ ${message.from_civ_id}`} to {to?.name ?? `Civ ${message.to_civ_id}`}
        </strong>
        <span className="tag">T{message.turn}</span>
        {direction && <span className="tag">{direction}</span>}
      </div>
      <div className="faint" style={{ marginBottom: "0.35rem" }}>
        {capitalize(message.kind)}
      </div>
      <div>{message.text}</div>
    </div>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");
}

function formatError(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
