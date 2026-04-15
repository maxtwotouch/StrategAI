"use client";

import { useEffect, useMemo, useState } from "react";

import { HexMap } from "@/components/HexMap";
import { GameStateDTO, UnitDTO, api } from "@/lib/api";
import { CIV_COLORS, hexDistance } from "@/lib/hex";

type PendingAction = { kind: "found"; unit: UnitDTO } | null;

export default function HomePage() {
  const [state, setState] = useState<GameStateDTO | null>(null);
  const [selectedUnit, setSelectedUnit] = useState<UnitDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction>(null);
  const [cityName, setCityName] = useState("");

  useEffect(() => {
    api
      .createGame(5, 1)
      .then(setState)
      .catch((e: unknown) => setError(formatError(e)));
  }, []);

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  const reachable = useMemo<Set<string>>(() => {
    const result = new Set<string>();
    if (!state || !selectedUnit || selectedUnit.moves_remaining <= 0) return result;
    const here = { q: selectedUnit.q, r: selectedUnit.r };
    for (const t of state.tiles) {
      if (hexDistance(here, { q: t.q, r: t.r }) === 1) {
        result.add(`${t.q},${t.r}`);
      }
    }
    return result;
  }, [state, selectedUnit]);

  const run = async (fn: () => Promise<GameStateDTO>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      setState(next);
      if (selectedUnit) {
        const updated = next.units.find((u) => u.id === selectedUnit.id) ?? null;
        setSelectedUnit(updated);
      }
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setBusy(false);
    }
  };

  const endTurn = () => state && run(() => api.endTurn(state.id));

  const submitFoundCity = () => {
    if (!state || !pending || !cityName.trim()) return;
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

  const onTileClick = (q: number, r: number) => {
    if (!state || !selectedUnit) return;
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
    if (
      selectedUnit &&
      u.id !== selectedUnit.id &&
      u.owner !== selectedUnit.owner
    ) {
      const here = { q: selectedUnit.q, r: selectedUnit.r };
      if (hexDistance(here, { q: u.q, r: u.r }) === 1) {
        run(() => api.attack(state.id, selectedUnit.id, u.id));
        return;
      }
    }
    setSelectedUnit(u);
  };

  if (!state && !error) {
    return (
      <main style={{ padding: "4rem 2rem", textAlign: "center" }}>
        <div className="spinner" />
        <p className="muted">Summoning your civilization…</p>
      </main>
    );
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "1.25rem 1.5rem 2rem",
        maxWidth: 1400,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          marginBottom: "1.25rem",
          paddingBottom: "1rem",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <h1
          style={{
            fontSize: "1.4rem",
            color: "var(--accent-strong)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          AI Civilization
        </h1>
        {state && (
          <span className="turn-badge">⏳ Turn {state.turn}</span>
        )}
        <div style={{ flex: 1 }} />
        {selectedUnit && (
          <span className="faint" style={{ marginRight: "0.5rem" }}>
            {selectedUnit.type} #{selectedUnit.id} · {selectedUnit.moves_remaining} moves
          </span>
        )}
        {selectedUnit && selectedUnit.type === "settler" && (
          <button onClick={openFoundCity} disabled={busy}>
            🏛 Found City
          </button>
        )}
        <button className="primary" onClick={endTurn} disabled={busy || !state}>
          End Turn →
        </button>
      </header>

      {state && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 300px",
            gap: "1.25rem",
          }}
        >
          <div
            className="card"
            style={{ padding: 0, overflow: "hidden" }}
          >
            <HexMap
              state={state}
              selectedUnitId={selectedUnit?.id ?? null}
              reachable={reachable}
              onTileClick={onTileClick}
              onUnitClick={onUnitClick}
            />
          </div>
          <div
            style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
          >
            {selectedUnit && (
              <div className="card">
                <h2>Selected Unit</h2>
                <div className="stat-row">
                  <span className="muted">Type</span>
                  <strong style={{ textTransform: "capitalize" }}>
                    {selectedUnit.type}
                  </strong>
                </div>
                <div className="stat-row">
                  <span className="muted">Owner</span>
                  <span>
                    <span
                      className="civ-badge"
                      style={{
                        background: CIV_COLORS[selectedUnit.owner % CIV_COLORS.length],
                      }}
                    />
                    {state.civs[selectedUnit.owner]?.name}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="muted">Health</span>
                  <strong>{selectedUnit.health}</strong>
                </div>
                <div className="stat-row">
                  <span className="muted">Moves</span>
                  <strong>{selectedUnit.moves_remaining}</strong>
                </div>
                <div className="stat-row">
                  <span className="muted">Position</span>
                  <span className="faint">
                    ({selectedUnit.q}, {selectedUnit.r})
                  </span>
                </div>
              </div>
            )}

            <div className="card">
              <h2>Civilizations</h2>
              {state.civs.map((c) => (
                <div
                  key={c.id}
                  style={{
                    padding: "0.5rem 0",
                    borderBottom: "1px dashed var(--border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span
                      className="civ-badge"
                      style={{
                        background: CIV_COLORS[c.id % CIV_COLORS.length],
                      }}
                    />
                    <strong>{c.name}</strong>
                    {c.is_human && (
                      <span
                        style={{
                          marginLeft: "0.4rem",
                          fontSize: "0.7rem",
                          color: "var(--accent)",
                          border: "1px solid var(--accent)",
                          padding: "0 0.35rem",
                          borderRadius: 3,
                        }}
                      >
                        YOU
                      </span>
                    )}
                  </div>
                  <div className="faint" style={{ marginLeft: 18 }}>
                    {c.leader_name} · 🧪 {c.science} · {c.known_techs.length} techs
                  </div>
                </div>
              ))}
            </div>

            <div className="card">
              <h2>Cities</h2>
              {state.cities.length === 0 ? (
                <p className="faint" style={{ margin: 0 }}>
                  No cities founded yet. Select a settler to build one.
                </p>
              ) : (
                state.cities.map((c) => (
                  <div key={c.id} style={{ padding: "0.4rem 0" }}>
                    <div>
                      <span
                        className="civ-badge"
                        style={{
                          background: CIV_COLORS[c.owner % CIV_COLORS.length],
                        }}
                      />
                      <strong>{c.name}</strong>
                      <span className="faint"> · pop {c.population}</span>
                    </div>
                    <div className="faint" style={{ marginLeft: 18 }}>
                      🌾 {c.food_stored} · 🔨 {c.production_stored}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="card">
              <h2>Controls</h2>
              <p className="faint" style={{ margin: 0, lineHeight: 1.6 }}>
                Click a unit to select. Dashed tiles show where you can move.
                Click an adjacent enemy to attack.
              </p>
            </div>
          </div>
        </div>
      )}

      {pending?.kind === "found" && (
        <div
          className="modal-backdrop"
          onClick={() => {
            setPending(null);
            setCityName("");
          }}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Name your city</h2>
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
              <button
                className="primary"
                onClick={submitFoundCity}
                disabled={!cityName.trim()}
              >
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

function formatError(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
