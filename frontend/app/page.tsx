"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SquareMap } from "@/components/SquareMap";
import {
  absoluteAssetUrl,
  generateLeaderAction,
  generateLeaderMultiAction,
  listLeaders,
} from "@/lib/assetApi";
import { CityDTO, GameStateDTO, TileDTO, UnitDTO, api } from "@/lib/api";
import { CIV_COLORS, hexDistance, tileKey } from "@/lib/hex";
import {
  LOCALES,
  LOCALE_LABELS,
  Locale,
  TFunction,
  TranslateParams,
  TranslationKey,
  useI18n,
} from "@/lib/i18n";
import { TurnEvent, diffTurnEvents } from "@/lib/turnEvents";
import { AssetManifest, CivInput, resolveManifest } from "@/lib/assetManifest";
import { ARCHETYPE_OPTIONS, CULTURE_OPTIONS, STRUCTURE_CATEGORIES } from "@/lib/assetMapping";
import {
  buildCustomLeaderParams,
  leaderParamsFor,
  sceneCinematicsFor,
} from "@/lib/leaderMapping";
import { useAudio } from "@/lib/useAudio";

type PendingAction = { kind: "found"; unit: UnitDTO } | null;
type TurnScene = {
  eventId: string;
  turn: number;
  /** Translation key + params for the scene caption. */
  textKey: TranslationKey;
  textParams?: TranslateParams;
  url: string;
};

// localStorage key for the player's cinematic-recap preference.
const CINEMATIC_PREF_KEY = "inf3600:cinematic";

// Each turn resolution shows a single scene. When several events happen in one
// turn we pick the most cinematic one by this priority (lower = preferred).
const TURN_EVENT_PRIORITY: Record<TurnEvent["kind"], number> = {
  stance_changed: 0,
  civ_met: 1,
  city_founded: 2,
  tech_completed: 3,
  unit_lost: 4,
  structure_built: 5,
  city_grew: 6,
  unit_created: 7,
  message_received: 8,
  turn_summary: 9,
};
type Setup = {
  radius: number;
  seed: number;
  humanName: string;
  leaderName: string;
  archetype: string;
  culture: string;
  leaderDescription: string;
};

function AudioGlyph({ muted }: { muted: boolean }) {
  return (
    <svg
      className="audio-toggle__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        className="audio-toggle__speaker"
        d="M4.5 9.25h3.35l5.05-4.2v13.9l-5.05-4.2H4.5z"
      />
      {!muted && (
        <>
          <path className="audio-toggle__wave" d="M15.5 8.1c1.1.9 1.7 2.25 1.7 3.9s-.6 3-1.7 3.9" />
          <path className="audio-toggle__wave audio-toggle__wave--outer" d="M18 5.8c1.75 1.55 2.75 3.75 2.75 6.2S19.75 16.65 18 18.2" />
        </>
      )}
      {muted && <path className="audio-toggle__slash" d="M16.2 8.1l4.1 7.8M20.3 8.1l-4.1 7.8" />}
    </svg>
  );
}

// Toggles the cinematic turn-recap images. Picture-frame glyph with a sun and
// hills; slashed when recaps are turned off.
function SceneGlyph({ enabled }: { enabled: boolean }) {
  return (
    <svg
      className="audio-toggle__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <rect className="audio-toggle__wave" x="3.5" y="5.5" width="17" height="13" rx="2" />
      <circle className="audio-toggle__speaker" cx="8.5" cy="10" r="1.5" />
      <path className="audio-toggle__wave" d="M4.5 17.5l4-4 2.5 2.5 3.5-4 5 5.5" />
      {!enabled && <path className="audio-toggle__slash" d="M5 5l14 14" />}
    </svg>
  );
}

type TechDef = {
  id: string;
  cost: number;
  prerequisites: string[];
};

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000_000);
}

function placedStructureKey(cityId: number, category: string, q: number, r: number): string {
  return `${cityId}:${category}:${tileKey(q, r)}`;
}

function shuffled<T>(items: T[]): T[] {
  const next = [...items];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

// Names are resolved from `locales/*.json` via `tech.<id>` (see tEnum).
const TECHS: TechDef[] = [
  { id: "agriculture", cost: 20, prerequisites: [] },
  { id: "pottery", cost: 20, prerequisites: [] },
  { id: "mining", cost: 25, prerequisites: [] },
  { id: "fishing", cost: 20, prerequisites: [] },
  { id: "archery", cost: 25, prerequisites: [] },
  { id: "animal_husbandry", cost: 35, prerequisites: ["agriculture"] },
  { id: "trapping", cost: 35, prerequisites: ["pottery"] },
  { id: "bronze_working", cost: 55, prerequisites: ["mining"] },
  { id: "sailing", cost: 45, prerequisites: ["fishing"] },
  { id: "wheel", cost: 55, prerequisites: ["animal_husbandry"] },
  { id: "masonry", cost: 55, prerequisites: ["mining"] },
  { id: "writing", cost: 75, prerequisites: ["pottery"] },
  { id: "horseback_riding", cost: 70, prerequisites: ["animal_husbandry"] },
  { id: "currency", cost: 80, prerequisites: ["bronze_working"] },
  { id: "calendar", cost: 70, prerequisites: ["pottery", "agriculture"] },
  { id: "iron_working", cost: 120, prerequisites: ["bronze_working"] },
  { id: "mathematics", cost: 110, prerequisites: ["currency"] },
  { id: "construction", cost: 100, prerequisites: ["masonry"] },
  { id: "philosophy", cost: 120, prerequisites: ["writing"] },
  { id: "astronomy", cost: 130, prerequisites: ["mathematics", "sailing"] },
];

const TECH_EMOJIS: Record<string, string> = {
  agriculture: "🌾",
  pottery: "🏺",
  mining: "⛏️",
  fishing: "🎣",
  archery: "🏹",
  animal_husbandry: "🐎",
  trapping: "🪤",
  bronze_working: "🛡️",
  sailing: "⛵",
  wheel: "🛞",
  masonry: "🧱",
  writing: "📜",
  horseback_riding: "🐴",
  currency: "🪙",
  calendar: "🗓️",
  iron_working: "⚒️",
  mathematics: "📐",
  construction: "🏗️",
  philosophy: "🧠",
  astronomy: "🔭",
};

type BuildableUnit = {
  id: string;
  cost: number;
  requires: string | null;
};

// Labels are resolved from `locales/*.json` via `unit.<id>` (see tEnum).
const BUILDABLE_UNITS: BuildableUnit[] = [
  { id: "warrior", cost: 10, requires: null },
  { id: "scout", cost: 8, requires: null },
  { id: "settler", cost: 15, requires: null },
  { id: "worker", cost: 10, requires: null },
  { id: "archer", cost: 15, requires: "archery" },
  { id: "horseman", cost: 22, requires: "horseback_riding" },
  { id: "swordsman", cost: 30, requires: "iron_working" },
];

const STRUCTURE_GOLD_COST = 15;
const STRUCTURE_PRODUCTION_BONUS = 2;

const IMPROVEMENT_OPTIONS: ReadonlyArray<{
  id: string;
  labelKey: TranslationKey;
  hintKey: TranslationKey;
}> = [
  { id: "farm", labelKey: "improvement.farm", hintKey: "improvement.farm.hint" },
  { id: "mine", labelKey: "improvement.mine", hintKey: "improvement.mine.hint" },
  { id: "road", labelKey: "improvement.road", hintKey: "improvement.road.hint" },
];

const MESSAGE_KINDS: ReadonlyArray<{ id: string; labelKey: TranslationKey }> = [
  { id: "chat", labelKey: "messageKind.chat" },
  { id: "threat", labelKey: "messageKind.threat" },
  { id: "offer_peace", labelKey: "messageKind.offer_peace" },
  { id: "accept_peace", labelKey: "messageKind.accept_peace" },
  { id: "declare_war", labelKey: "messageKind.declare_war" },
  { id: "propose_alliance", labelKey: "messageKind.propose_alliance" },
  { id: "accept_alliance", labelKey: "messageKind.accept_alliance" },
  { id: "reject", labelKey: "messageKind.reject" },
];

// Spoken intro. Deliberately English-only: the backend renders it with a fixed
// English narrator voice (see backend/app/api/routers/audio.py), so localizing
// the script would change how the narrator sounds rather than only what it says.
function buildIntroNarration(civName: string, leaderName: string): string {
  return [
    `In the long silence before empire, the people of ${civName} gathered beneath strange stars and dreamed of dominion.`,
    `Now, beneath the hand of ${leaderName}, their first banners rise against the darkness of an unclaimed world.`,
    "Stone will answer to your will. Rivers will carry your name. Enemies yet unborn will learn to fear the sound of your drums.",
    "Found the capital. Send forth the scouts. Claim knowledge, gold, and steel before the rival thrones awaken.",
    "For from one fragile settlement may rise an empire whose shadow falls across the ages.",
  ].join(" ");
}

export default function HomePage() {
  const { locale, setLocale, t, tEnum, tPlural } = useI18n();
  const [state, setState] = useState<GameStateDTO | null>(null);
  const [selectedUnit, setSelectedUnit] = useState<UnitDTO | null>(null);
  const [hoveredTile, setHoveredTile] = useState<TileDTO | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction>(null);
  const [cityName, setCityName] = useState("");
  const [setup, setSetup] = useState<Setup>(() => ({
    radius: 20,
    seed: randomSeed(),
    humanName: "Athens",
    leaderName: "",
    archetype: "philosopher_king",
    culture: "medieval_european",
    leaderDescription: "",
  }));
  const [messageTargetId, setMessageTargetId] = useState<number | null>(null);
  const [messageKind, setMessageKind] = useState("chat");
  const [messageText, setMessageText] = useState("");
  const [activeConversationCivId, setActiveConversationCivId] = useState<number | null>(null);
  const [activeCityId, setActiveCityId] = useState<number | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [chronicleCollapsed, setChronicleCollapsed] = useState(false);
  const [bannerEvents, setBannerEvents] = useState<TurnEvent[] | null>(null);
  const [eventLog, setEventLog] = useState<TurnEvent[]>([]);
  const [assets, setAssets] = useState<AssetManifest | null>(null);
  const [placedStructureAssets, setPlacedStructureAssets] = useState<Record<string, string>>({});
  const [assetProgress, setAssetProgress] = useState<{ done: number; total: number } | null>(null);
  const [loadingSplashUrls, setLoadingSplashUrls] = useState<string[]>([]);
  const [loadingSplashIndex, setLoadingSplashIndex] = useState(0);
  const [sovereignSplashIndex, setSovereignSplashIndex] = useState(0);
  const [turnScenes, setTurnScenes] = useState<TurnScene[]>([]);
  // Player preference: show the cinematic turn-recap images, or resolve turns
  // instantly like the classic flow. Persisted across sessions; the novelty of
  // the images wears off, so it's opt-out.
  const [cinematicEnabled, setCinematicEnabled] = useState(true);
  // Base "dawn rising" scene generated once at game start. Acts as the fallback
  // image whenever a per-turn scene can't be generated.
  const [baseScene, setBaseScene] = useState<TurnScene | null>(null);
  // Prefetched scene shown on the NEXT turn resolution so End Turn paints
  // instantly. Seeded with the dawn scene at game start, then regenerated in the
  // background after each resolution from that turn's events (one-turn lag).
  const [nextScene, setNextScene] = useState<TurnScene | null>(null);
  const preparingNextSceneRef = useRef(false);
  // The single scene shown during the current turn resolution (null = still
  // generating → spinner).
  const [resolvingScene, setResolvingScene] = useState<TurnScene | null>(null);
  // True once the turn's work + scene generation finish, so the overlay can
  // show the image and a Continue button. The user dismisses it manually.
  const [turnResolved, setTurnResolved] = useState(false);
  const [pendingTurnSceneIds, setPendingTurnSceneIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [resolvingTurn, setResolvingTurn] = useState(false);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [showSovereign, setShowSovereign] = useState(false);
  const { muted, toggleMute, startIntro, playNarration, startAmbient } = useAudio();
  const introNarratedRef = useRef(false);
  const introNarrationUrlRef = useRef<string | null>(null);
  const [introNarrationStatus, setIntroNarrationStatus] = useState<
    "idle" | "generating" | "playing" | "unavailable"
  >("idle");

  const dismissIntro = () => {
    setIntroDismissed(true);
    startAmbient();
  };
  const prevStateRef = useRef<GameStateDTO | null>(null);
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadingSplashRunRef = useRef(0);

  const loadGame = async (nextSetup: Setup) => {
    const splashRun = loadingSplashRunRef.current + 1;
    loadingSplashRunRef.current = splashRun;
    setBusy(true);
    setError(null);
    setHasStarted(true);
    setState(null);
    setAssets(null);
    setPlacedStructureAssets({});
    setAssetProgress(null);
    setLoadingSplashIndex(0);
    setSovereignSplashIndex(0);
    setTurnScenes([]);
    setBaseScene(null);
    setNextScene(null);
    preparingNextSceneRef.current = false;
    setResolvingScene(null);
    setTurnResolved(false);
    setPendingTurnSceneIds(new Set());
    setResolvingTurn(false);
    setIntroDismissed(false);
    introNarratedRef.current = false;
    setIntroNarrationStatus("idle");
    setSelectedUnit(null);
    setHoveredTile(null);
    setPending(null);
    setCityName("");
    setMessageTargetId(null);
    setMessageKind("chat");
    setMessageText("");
    setActiveConversationCivId(null);
    setBannerEvents(null);
    setEventLog([]);
    void listLeaders()
      .then((leaders) => {
        if (loadingSplashRunRef.current !== splashRun) return;
        const urls = shuffled(
          leaders
            .map((leader) => leader.splash_url)
            .filter((url): url is string => Boolean(url))
            .map(absoluteAssetUrl),
        );
        setLoadingSplashUrls(urls);
      })
      .catch(() => {
        if (loadingSplashRunRef.current === splashRun) setLoadingSplashUrls([]);
      });
    try {
      const next = await api.createGame(
        nextSetup.radius,
        nextSetup.seed,
        nextSetup.humanName,
      );
      // Resolve generated assets while the load screen is up. No-op (null) when
      // NEXT_PUBLIC_ASSET_API_URL is unset, so the game still renders normally.
      const humanCustomParams = buildCustomLeaderParams({
        leaderName: nextSetup.leaderName || nextSetup.humanName,
        archetype: nextSetup.archetype,
        culture: nextSetup.culture,
        description: nextSetup.leaderDescription,
      });
      // Use civ_roster so we resolve art for AI civs even before the human
      // has met them. state.civs is filtered by fog of war and only contains
      // discovered civs, which is the wrong set for pre-generation.
      const roster = next.civ_roster.length > 0 ? next.civ_roster : next.civs;
      const civs: CivInput[] = roster.map((c) => {
        const base: CivInput = { civId: c.id, leaderName: c.leader_name };
        return c.is_human ? { ...base, customLeaderParams: humanCustomParams } : base;
      });
      const leaders: CivInput[] = roster.map((c) => {
        const base: CivInput = { civId: c.id, leaderName: c.leader_name };
        return c.is_human ? { ...base, customLeaderParams: humanCustomParams } : base;
      });
      let manifest: AssetManifest | null = null;
      try {
        manifest = await resolveManifest(
          {
            gameId: next.id,
            terrains: next.tiles.map((t) => t.terrain),
            civs,
            leaders,
          },
          { onProgress: (done, total) => setAssetProgress({ done, total }) },
        );
      } catch {
        // Asset service unreachable — fall back to built-in rendering.
      }
      setAssets(manifest);
      setState(next);
      prevStateRef.current = next;
      // Generate the "dawn rising" base scene in the background (only if recaps
      // are enabled). It becomes the fallback/first image for turn resolutions.
      if (cinematicEnabled) {
        void generateBaseDawnScene(manifest, next, humanCustomParams);
      }
    } catch (e: unknown) {
      setError(toAppError(e));
      setHasStarted(false);
      setLoadingSplashUrls([]);
    } finally {
      setBusy(false);
      setAssetProgress(null);
    }
  };

  const beginGame = () => {
    // The button click is the user gesture that unlocks audio playback.
    startIntro();
    const nextSetup = { ...setup, seed: randomSeed() };
    setSetup(nextSetup);
    void loadGame(nextSetup);
  };

  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  // Restore the cinematic-recap preference once on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem(CINEMATIC_PREF_KEY);
      if (stored !== null) setCinematicEnabled(stored === "1");
    } catch {
      // localStorage unavailable — keep the default (on).
    }
  }, []);

  const toggleCinematic = (): void => {
    setCinematicEnabled((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(CINEMATIC_PREF_KEY, next ? "1" : "0");
      } catch {
        // Persisting is best-effort.
      }
      return next;
    });
  };

  useEffect(() => {
    let cancelled = false;
    void listLeaders()
      .then((leaders) => {
        if (cancelled) return;
        const urls = shuffled(
          leaders
            .map((leader) => leader.splash_url)
            .filter((url): url is string => Boolean(url))
            .map(absoluteAssetUrl),
        );
        setLoadingSplashUrls(urls);
      })
      .catch(() => {
        if (!cancelled) setLoadingSplashUrls([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (state || loadingSplashUrls.length <= 1) return;
    const timer = setInterval(() => {
      setLoadingSplashIndex((index) => (index + 1) % loadingSplashUrls.length);
    }, 6500);
    return () => clearInterval(timer);
  }, [loadingSplashUrls.length, state]);

  useEffect(() => {
    if (!resolvingTurn || loadingSplashUrls.length <= 1) return;
    const timer = setInterval(() => {
      setLoadingSplashIndex((index) => (index + 1) % loadingSplashUrls.length);
    }, 6500);
    return () => clearInterval(timer);
  }, [loadingSplashUrls.length, resolvingTurn]);

  useEffect(() => {
    if (!showSovereign || loadingSplashUrls.length <= 1) return;
    const timer = setInterval(() => {
      setSovereignSplashIndex((index) => (index + 1) % loadingSplashUrls.length);
    }, 7000);
    return () => clearInterval(timer);
  }, [loadingSplashUrls.length, showSovereign]);

  useEffect(() => {
    return () => {
      if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!state || introDismissed) return;
    const onKey = (e: KeyboardEvent) => {
      const isActivationKey = e.key === "Enter" || e.key === " ";
      // Enter/Space belong to the focused control — the language switch, the
      // replay button, or the CTA all handle their own activation, so the
      // shortcut must not steal them. Esc always closes the intro.
      if (isActivationKey && isInteractiveTarget(e.target)) return;
      if (e.key === "Escape" || isActivationKey) {
        e.preventDefault();
        dismissIntro();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [introDismissed, state]);

  useEffect(() => {
    return () => {
      if (introNarrationUrlRef.current) {
        URL.revokeObjectURL(introNarrationUrlRef.current);
      }
    };
  }, []);

  const playIntroNarration = useCallback(
    async (civName: string, leaderName: string) => {
      if (muted) {
        setIntroNarrationStatus("idle");
        return;
      }
      setIntroNarrationStatus("generating");
      try {
        const audio = await api.generateIntroNarration(
          buildIntroNarration(civName, leaderName),
        );
        if (introNarrationUrlRef.current) {
          URL.revokeObjectURL(introNarrationUrlRef.current);
        }
        const url = URL.createObjectURL(audio);
        introNarrationUrlRef.current = url;
        playNarration(url);
        setIntroNarrationStatus("playing");
      } catch {
        setIntroNarrationStatus("unavailable");
      }
    },
    [muted, playNarration],
  );

  useEffect(() => {
    if (!state || introDismissed || introNarratedRef.current) return;
    const civ = state.civs.find((c) => c.is_human);
    const civName = civ?.name ?? setup.humanName;
    const leaderName = setup.leaderName.trim() || civ?.leader_name || civName;
    introNarratedRef.current = true;
    void playIntroNarration(civName, leaderName);
  }, [
    introDismissed,
    playIntroNarration,
    setup.humanName,
    setup.leaderName,
    state,
  ]);

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

  const activeVisibleTiles = visibleTiles;

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

  // City drawer is closed by default — opens when a city is clicked (map or rail).
  useEffect(() => {
    if (activeCityId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveCityId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeCityId]);

  useEffect(() => {
    if (!showSovereign) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowSovereign(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showSovereign]);

  const activeCity = useMemo(
    () =>
      activeCityId !== null
        ? state?.cities.find((c) => c.id === activeCityId) ?? null
        : null,
    [activeCityId, state],
  );

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

  const activeLeaderSplash = useMemo(
    () =>
      activeConversationCivId !== null
        ? assets?.leaders[activeConversationCivId]?.splashUrl ?? null
        : null,
    [assets, activeConversationCivId],
  );

  const generatedTurnSceneByEventId = useMemo(
    () => new Map(turnScenes.map((scene) => [scene.eventId, scene])),
    [turnScenes],
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

  const ingestEvents = (next: GameStateDTO): TurnEvent[] => {
    const prev = prevStateRef.current;
    if (!prev || prev.id !== next.id) {
      prevStateRef.current = next;
      return [];
    }
    if (prev.turn === next.turn) {
      prevStateRef.current = next;
      return [];
    }
    const events = diffTurnEvents({
      prev,
      next,
      humanCivId: humanCiv?.id ?? null,
    });
    prevStateRef.current = next;
    if (events.length === 0) return [];
    setEventLog((current) => [...events, ...current].slice(0, 80));
    setBannerEvents(events);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    bannerTimerRef.current = setTimeout(() => setBannerEvents(null), 4500);
    return events;
  };

  const preloadImage = (url: string): Promise<void> =>
    new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve();
      img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
      img.src = url;
    });

  const queueTurnSummaryScenes = async (
    events: TurnEvent[],
    next: GameStateDTO,
  ): Promise<TurnScene[]> => {
    if (!assets) return [];
    const existingIds = new Set(turnScenes.map((scene) => scene.eventId));
    const selected = events
      .filter((event) => !existingIds.has(event.id) && !pendingTurnSceneIds.has(event.id))
      .filter((event) =>
        event.civIds.some((civId) => Boolean(assets.leaders[civId]?.leaderId)),
      )
      .slice(0, 2);
    if (selected.length === 0) return [];

    setPendingTurnSceneIds((current) => {
      const nextSet = new Set(current);
      for (const event of selected) nextSet.add(event.id);
      return nextSet;
    });

    const scenes = (
      await Promise.all(selected.map((event) => generateTurnSummaryScene(event, next)))
    ).filter((scene): scene is TurnScene => Boolean(scene));
    return scenes;
  };

  const buildFallbackTurnSummaryEvent = (next: GameStateDTO): TurnEvent => {
    const nextHumanCiv = next.civ_roster.find((civ) => civ.is_human) ?? null;
    const nextOtherCivs = next.civ_roster.filter((civ) => !civ.is_human);
    const preContact =
      nextOtherCivs.length === 0 ||
      !next.known_civ_ids.some((id) => id !== nextHumanCiv?.id);
    const sceneVariants: Array<{
      actionCategory: TurnEvent["actionCategory"];
      textKey: TranslationKey;
      description: (leaderName: string, civName: string) => string;
    }> = [
      {
        actionCategory: "military",
        textKey: "event.summary.military",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} inspects newly mustered troops in a torchlit courtyard, with soldiers tightening armor straps, smiths handing over fresh weapons, horses stamping nearby, and campaign banners rising behind them. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
      {
        actionCategory: "construction",
        textKey: "event.summary.construction",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} stands before a growing construction site, pointing across scaffolding, cranes, stone blocks, timber frames, and workers raising a new district under urgent civic orders. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
      {
        actionCategory: "exploration",
        textKey: "event.summary.exploration",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} studies a large frontier map with scouts, compass tools, muddy boots, and travel packs scattered nearby, preparing expeditions toward unknown lands. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
      {
        actionCategory: "scientific",
        textKey: "event.summary.scientific",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} listens as scholars demonstrate a new discovery with brass instruments, scrolls, diagrams, and candlelit calculations spread across a busy observatory chamber. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
      {
        actionCategory: "cultural",
        textKey: "event.summary.cultural",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} presides over a civic ceremony with musicians, artisans, embroidered banners, ceremonial gifts, and citizens gathered around a monument under warm festival light. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
      {
        actionCategory: "crisis",
        textKey: "event.summary.crisis",
        description: (leaderName, civName) =>
          `${leaderName} of ${civName} reacts to urgent messengers in a tense command chamber, with scattered reports, overturned maps, anxious officers, storm light at the windows, and immediate decisions being made. No rival ruler is present; this scene focuses only on the player's leader and their own civilization.`,
      },
    ];
    const variant = sceneVariants[(next.turn + next.id) % sceneVariants.length];
    const civIds: number[] = [];
    const primary =
      nextHumanCiv ??
      next.civ_roster.find((civ) => Boolean(assets?.leaders[civ.id]?.leaderId)) ??
      next.civ_roster[0];
    if (primary) civIds.push(primary.id);
    const visibleRival =
      nextOtherCivs.find((civ) => Boolean(assets?.leaders[civ.id]?.leaderId)) ??
      next.civ_roster.find(
        (civ) => !civ.is_human && Boolean(assets?.leaders[civ.id]?.leaderId),
      );
    if (
      !preContact &&
      variant.actionCategory === "diplomatic" &&
      visibleRival &&
      !civIds.includes(visibleRival.id)
    ) {
      civIds.push(visibleRival.id);
    }
    if (civIds.length === 0 && next.civ_roster[0]) {
      civIds.push(next.civ_roster[0].id);
    }
    const primaryName = primary?.name ?? setup.humanName;
    const leaderName =
      primary?.is_human
        ? setup.leaderName.trim() || primary.leader_name
        : primary?.leader_name ?? "the ruler";
    return {
      id: `summary-${next.id}-${next.turn}`,
      turn: next.turn,
      kind: "turn_summary",
      textKey: variant.textKey,
      civIds,
      actionCategory: variant.actionCategory,
      actionDescription: `${variant.description(leaderName, primaryName)} ${turnSceneAccent(next.turn)}`,
    };
  };

  const generateTurnSummaryScene = async (
    event: TurnEvent,
    next: GameStateDTO,
  ): Promise<TurnScene | null> => {
    try {
      if (!assets) return null;
      const uniqueCivIds = [...new Set(event.civIds)];
      const leaderIds = uniqueCivIds
        .map((civId) => assets.leaders[civId]?.leaderId)
        .filter((id): id is string => Boolean(id));
      if (leaderIds.length === 0) return null;

      const primaryCivId =
        uniqueCivIds.find((civId) => assets.leaders[civId]?.leaderId) ?? uniqueCivIds[0];
      const primaryCiv =
        next.civ_roster.find((civ) => civ.id === primaryCivId) ??
        next.civs.find((civ) => civ.id === primaryCivId);
      if (!primaryCiv) return null;
      const baseParams =
        primaryCiv.is_human
          ? buildCustomLeaderParams({
              leaderName: setup.leaderName || primaryCiv.leader_name,
              archetype: setup.archetype,
              culture: setup.culture,
              description: setup.leaderDescription,
            })
          : leaderParamsFor(primaryCiv.leader_name);
      // Vary lighting and mood per scene by event category and turn so repeated
      // scenes for the same leader don't all look identical (see
      // sceneCinematicsFor). Identity fields (archetype/culture/description)
      // stay fixed for visual consistency.
      const primaryParams: typeof baseParams = {
        ...baseParams,
        ...sceneCinematicsFor(event.actionCategory, event.turn),
      };

      const result =
        leaderIds.length > 1
          ? await generateLeaderMultiAction(
              primaryParams,
              leaderIds.slice(0, 2),
              event.actionCategory,
              event.actionDescription,
            )
          : await generateLeaderAction(
              primaryParams,
              leaderIds[0],
              event.actionCategory,
              event.actionDescription,
            );
      await preloadImage(result.url);
      const scene: TurnScene = {
        eventId: event.id,
        turn: event.turn,
        textKey: event.textKey,
        textParams: event.textParams,
        url: result.url,
      };
      setTurnScenes((current) => {
        if (current.some((scene) => scene.eventId === event.id)) return current;
        return [scene, ...current].slice(0, 12);
      });
      return scene;
    } catch {
      // Action-scene generation is decorative; the text chronicle remains authoritative.
      return null;
    } finally {
      setPendingTurnSceneIds((current) => {
        const nextSet = new Set(current);
        nextSet.delete(event.id);
        return nextSet;
      });
    }
  };

  // Generate the one-time "dawn rising" base scene for the human civilization.
  // Best-effort: a failure just means turn resolutions fall back to no image.
  const generateBaseDawnScene = async (
    manifest: AssetManifest | null,
    next: GameStateDTO,
    humanParams: ReturnType<typeof buildCustomLeaderParams>,
  ): Promise<void> => {
    if (!manifest) return;
    const human = next.civ_roster.find((civ) => civ.is_human) ?? null;
    const leaderId = human ? manifest.leaders[human.id]?.leaderId : undefined;
    if (!human || !leaderId) return;
    try {
      const params = { ...humanParams, timeOfDay: "dawn", mood: "hopeful" };
      const description =
        `${params.leaderName} stands upon a rise at first light, surveying their ` +
        `newborn civilization awakening below — smoke curling from the first ` +
        `hearths, banners catching the morning wind, citizens stirring to begin ` +
        `the day's labor, and the wide unwritten land stretching toward the ` +
        `horizon. No rival ruler is present; this scene focuses only on the ` +
        `player's leader and their own people.`;
      const result = await generateLeaderAction(
        params,
        leaderId,
        "exploration",
        description,
      );
      await preloadImage(result.url);
      const dawn: TurnScene = {
        eventId: "base-dawn",
        turn: next.turn,
        textKey: "resolution.dawnScene",
        url: result.url,
      };
      setBaseScene(dawn);
      // Seed the prefetch buffer so the very first End Turn paints instantly.
      setNextScene((current) => current ?? dawn);
    } catch {
      // Decorative — no base scene just means no fallback image.
    }
  };

  // Choose the single most cinematic event to depict for a turn resolution,
  // restricted to events whose leaders actually have generated portraits.
  const selectPrimaryTurnEvent = (events: TurnEvent[]): TurnEvent | null => {
    if (!assets) return null;
    const generatable = events.filter((event) =>
      event.civIds.some((civId) => Boolean(assets.leaders[civId]?.leaderId)),
    );
    if (generatable.length === 0) return null;
    return [...generatable].sort(
      (a, b) =>
        (TURN_EVENT_PRIORITY[a.kind] ?? 99) - (TURN_EVENT_PRIORITY[b.kind] ?? 99),
    )[0];
  };

  // Apply fog-of-war filtering, fall back to a synthesized summary event, then
  // pick the single event to depict. Shared by live resolution and prefetch.
  const pickResolutionEvent = (
    events: TurnEvent[],
    next: GameStateDTO,
  ): TurnEvent | null => {
    const human = next.civ_roster.find((civ) => civ.is_human) ?? null;
    const hasMetRival =
      human === null || next.known_civ_ids.some((civId) => civId !== human.id);
    const visible = hasMetRival
      ? events
      : events.filter(
          (event) =>
            human !== null &&
            event.civIds.length === 1 &&
            event.civIds[0] === human.id,
        );
    const sceneEvents =
      visible.length > 0 ? visible : [buildFallbackTurnSummaryEvent(next)];
    return selectPrimaryTurnEvent(sceneEvents) ?? sceneEvents[0] ?? null;
  };

  // Background prefetch: generate the scene to show on the NEXT End Turn from
  // the turn that just resolved, so it's preloaded and instant when needed.
  const prepareNextScene = async (
    events: TurnEvent[],
    next: GameStateDTO,
  ): Promise<void> => {
    if (!assets || preparingNextSceneRef.current) return;
    preparingNextSceneRef.current = true;
    try {
      const event = pickResolutionEvent(events, next);
      const scene = event ? await generateTurnSummaryScene(event, next) : null;
      if (scene) setNextScene(scene);
    } finally {
      preparingNextSceneRef.current = false;
    }
  };

  // User-driven dismissal of the turn-resolution overlay (no auto-timeout).
  const dismissResolution = (): void => {
    setResolvingTurn(false);
    setTurnResolved(false);
    setResolvingScene(null);
  };

  const run = async (fn: () => Promise<GameStateDTO>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      const events = ingestEvents(next);
      setState(next);
      void queueTurnSummaryScenes(events, next);
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
      setError(toAppError(e));
    } finally {
      setBusy(false);
    }
  };

  const endTurn = async () => {
    if (!state) return;
    // Classic flow when the player has turned recaps off (or there's no asset
    // server): resolve instantly with no cinematic overlay.
    if (!assets || !cinematicEnabled) {
      await run(() => api.resolveTurn(state.id));
      return;
    }
    // Paint the prefetched scene immediately so the overlay feels instant; only
    // fall back to a spinner if nothing has been prepared yet.
    setResolvingScene(nextScene ?? baseScene);
    setTurnResolved(false);
    setBusy(true);
    setResolvingTurn(true);
    setError(null);
    try {
      const next = await api.resolveTurn(state.id);
      const events = ingestEvents(next);
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
      // Prefetch the scene for the NEXT resolution from this turn's events so
      // the following End Turn is instant too.
      void prepareNextScene(events, next);
    } catch (e: unknown) {
      setError(toAppError(e));
    } finally {
      // Backend work is done — enable Continue; the user dismisses when ready.
      setTurnResolved(true);
      setBusy(false);
    }
  };

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
    setCityName(t("city.defaultName", { number: (state?.cities.length ?? 0) + 1 }));
  };

  const chooseResearch = async (techId: string) => {
    if (!state || !humanCiv || !techId || !isHumanTurn) return;
    await run(() => api.research(state.id, humanCiv.id, techId));
  };

  const queueProduction = async (cityId: number, unitType: string) => {
    if (!state || !humanCiv || !isHumanTurn) return;
    await run(() => api.build(state.id, humanCiv.id, cityId, unitType));
  };

  const cancelProduction = async (cityId: number, index: number) => {
    if (!state || !humanCiv || !isHumanTurn) return;
    await run(() => api.cancelBuild(state.id, humanCiv.id, cityId, index));
  };

  const purchaseStructure = async (
    cityId: number,
    category: string,
    q: number,
    r: number,
  ) => {
    if (!state || !humanCiv || !isHumanTurn) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.purchaseStructure(state.id, humanCiv.id, cityId, category, q, r);
      ingestEvents(next);
      setState(next);

      const key = placedStructureKey(cityId, category, q, r);
      const city = next.cities.find((candidate) => candidate.id === cityId);
      const preloadedUrl =
        city && assets?.structures[city.owner]?.[category]
          ? assets.structures[city.owner][category]
          : undefined;
      if (preloadedUrl) {
        setPlacedStructureAssets((current) => ({ ...current, [key]: preloadedUrl }));
      }
    } catch (e: unknown) {
      setError(toAppError(e));
    } finally {
      setBusy(false);
    }
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
      setError({ key: "error.truceHostile", params: { turn: activeStance.truce_until ?? "?" } });
      return;
    }
    const text = messageText.trim();
    await run(() =>
      api.sendMessage(state.id, humanCiv.id, messageTargetId, messageKind, text),
    );
    setMessageText("");
  };

  const onTileClick = (q: number, r: number) => {
    if (!state) return;
    // Movement / attack only happens when you have one of your units selected,
    // it's your turn, and the clicked tile is adjacent.
    if (selectedUnit && isHumanTurn && selectedUnit.owner === humanCiv?.id) {
      const here = { q: selectedUnit.q, r: selectedUnit.r };
      if (hexDistance(here, { q, r }) === 1) {
        const occupant = state.units.find((u) => u.q === q && u.r === r);
        if (occupant && occupant.owner !== selectedUnit.owner) {
          if (!canAttackOwner(state, selectedUnit.owner, occupant.owner)) {
            setError({ key: "error.declareWar" });
            return;
          }
          run(() => api.attack(state.id, selectedUnit.id, occupant.id));
          return;
        }
        run(() => api.move(state.id, selectedUnit.id, q, r));
        return;
      }
    }
    // Otherwise, if the click landed on one of your cities, open its drawer.
    const city = state.cities.find(
      (c) => c.q === q && c.r === r && c.owner === humanCiv?.id,
    );
    if (city) setActiveCityId(city.id);
  };

  const onUnitClick = (u: UnitDTO) => {
    if (!state) return;
    // Clicking your own unit during the AI turn just previews it.
    if (!isHumanTurn && u.owner === humanCiv?.id) {
      setSelectedUnit(u);
      return;
    }
    // Clicking a rival unit while you have one of yours selected attempts an
    // attack (requires being adjacent and at war).
    if (selectedUnit && u.id !== selectedUnit.id && u.owner !== selectedUnit.owner) {
      const here = { q: selectedUnit.q, r: selectedUnit.r };
      if (hexDistance(here, { q: u.q, r: u.r }) === 1) {
        if (!canAttackOwner(state, selectedUnit.owner, u.owner)) {
          setError({ key: "error.declareWar" });
          return;
        }
        run(() => api.attack(state.id, selectedUnit.id, u.id));
        return;
      }
    }
    // Selection is restricted to your own units — never take control of a rival's.
    if (u.owner !== humanCiv?.id) return;
    setSelectedUnit(u);
  };

  const humanColor = humanCiv ? CIV_COLORS[humanCiv.id % CIV_COLORS.length] : "#b08a44";
  const highlightedTileKey = hoveredTile ? tileKey(hoveredTile.q, hoveredTile.r) : null;
  const needsResearch = humanCiv !== null && !currentResearch && availableTechs.length > 0;
  const needsProduction =
    humanCities.length > 0 && selectedProductionCity?.production_queue.length === 0;
  const needsSelection = humanUnits.length > 0 && !selectedUnit && isHumanTurn;
  const nextObjective = !humanCities.length
    ? t("objective.foundCity")
    : needsResearch
      ? t("objective.research")
      : needsProduction
        ? t("objective.production", {
            city: selectedProductionCity?.name ?? t("objective.productionFallback"),
          })
        : totalInbox > 0
          ? t("objective.inbox")
          : needsSelection
            ? t("objective.selection")
            : t("objective.expand");
  const researchProgress = currentResearch
    ? Math.min(humanCiv?.science ?? 0, currentResearch.cost)
    : 0;
  const resolvingSceneCaption = resolvingScene
    ? t(resolvingScene.textKey, resolvingScene.textParams)
    : null;

  if (!hasStarted) {
    const startSplashUrl =
      loadingSplashUrls.length > 0
        ? loadingSplashUrls[loadingSplashIndex % loadingSplashUrls.length]
        : null;
    return (
      <main className="start-screen">
        {startSplashUrl && (
          <div
            key={startSplashUrl}
            className="loading-slideshow"
            style={{ backgroundImage: `url(${startSplashUrl})` }}
          />
        )}
        <div className="start-screen__veil" />
        <section className="start-screen__panel">
          <div className="plate-label">{t("start.plate")}</div>
          <h1>{t("start.title")}</h1>
          <p className="start-screen__copy">{t("start.copy")}</p>

          <div className="start-screen__grid">
            <label className="field">
              <span className="field-label">{t("start.civilizationName")}</span>
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
                placeholder={t("start.civilizationPlaceholder")}
              />
            </label>
            <label className="field">
              <span className="field-label">{t("start.leaderName")}</span>
              <input
                type="text"
                maxLength={100}
                value={setup.leaderName}
                onChange={(e) =>
                  setSetup((prev) => ({ ...prev, leaderName: e.target.value }))
                }
                placeholder={t("start.leaderPlaceholder")}
              />
            </label>
            <label className="field">
              <span className="field-label">{t("start.archetype")}</span>
              <select
                value={setup.archetype}
                onChange={(e) =>
                  setSetup((prev) => ({ ...prev, archetype: e.target.value }))
                }
              >
                {ARCHETYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {tEnum("archetype", opt.value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">{t("start.culture")}</span>
              <select
                value={setup.culture}
                onChange={(e) =>
                  setSetup((prev) => ({ ...prev, culture: e.target.value }))
                }
              >
                {CULTURE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {tEnum("culture", opt.value)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">{t("start.mapRadius")}</span>
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

          <label className="field field--full">
            <span className="field-label">
              {t("start.leaderAppearance")}{" "}
              <small style={{ color: "var(--ink-muted)" }}>
                {t("start.leaderAppearanceCount", {
                  count: setup.leaderDescription.length,
                })}
              </small>
            </span>
            <textarea
              rows={3}
              maxLength={800}
              value={setup.leaderDescription}
              onChange={(e) =>
                setSetup((prev) => ({ ...prev, leaderDescription: e.target.value }))
              }
              placeholder={t("start.leaderAppearancePlaceholder")}
            />
          </label>

          <div className="start-screen__meta">
            <span>{t("start.metaCapital")}</span>
            <span>{t("start.metaFrontier")}</span>
            <span>{t("start.metaDiplomacy")}</span>
          </div>

          <div className="start-screen__actions">
            <button className="button-primary" onClick={beginGame} disabled={busy}>
              {busy ? t("start.generating") : t("start.begin")}
            </button>
            <LocaleSwitch locale={locale} onChange={setLocale} label={t("start.language")} />
          </div>
        </section>
        {error && <div className="toast">{t(error.key, error.params)}</div>}
      </main>
    );
  }

  if (!state) {
    const loadingSplashUrl =
      loadingSplashUrls.length > 0
        ? loadingSplashUrls[loadingSplashIndex % loadingSplashUrls.length]
        : null;
    return (
      <main className="start-screen">
        {loadingSplashUrl && (
          <div
            key={loadingSplashUrl}
            className="loading-slideshow"
            style={{ backgroundImage: `url(${loadingSplashUrl})` }}
          />
        )}
        <div className="start-screen__veil" />
        <section className="start-screen__panel start-screen__panel--loading">
          <div className="spinner" />
          <p className="start-screen__copy">{t("loading.copy")}</p>
          {assetProgress && assetProgress.total > 0 && (
            <p className="start-screen__copy">
              {t("loading.art", {
                done: assetProgress.done,
                total: assetProgress.total,
              })}
            </p>
          )}
        </section>
        {error && <div className="toast">{t(error.key, error.params)}</div>}
      </main>
    );
  }

  if (!introDismissed) {
    const humanSplash = humanCiv ? assets?.leaders[humanCiv.id]?.splashUrl : null;
    const civName = humanCiv?.name ?? setup.humanName;
    const leaderName =
      setup.leaderName.trim() || humanCiv?.leader_name || civName;
    return (
      <main className="intro-screen" aria-label={t("intro.aria", { civ: civName })}>
        <div
          className="intro-screen__bg"
          style={
            humanSplash ? { backgroundImage: `url(${humanSplash})` } : undefined
          }
          onClick={dismissIntro}
        />
        <section className="intro-screen__panel">
          <div className="plate-label intro-screen__chapter">{t("intro.chapter")}</div>
          <h1 className="intro-screen__civ">{civName}</h1>
          <div className="intro-screen__leader">
            {t("intro.reign", { leader: leaderName })}
          </div>
          <p className="intro-screen__epitaph">
            {t("intro.epitaph1")}
            <br />
            {t("intro.epitaph2")}
          </p>
          <div className="intro-screen__actions">
            <button
              type="button"
              className="button-primary intro-screen__cta"
              onClick={(e) => {
                e.stopPropagation();
                dismissIntro();
              }}
            >
              {t("intro.begin")}
            </button>
            <button
              type="button"
              className="intro-screen__replay"
              onClick={(e) => {
                e.stopPropagation();
                void playIntroNarration(civName, leaderName);
              }}
            >
              {t("intro.replay")}
            </button>
          </div>
          <div className="intro-screen__narration">
            {muted && t("intro.narrationMuted")}
            {!muted && introNarrationStatus === "idle" && t("intro.narrationReady")}
            {!muted && introNarrationStatus === "generating" &&
              t("intro.narrationGenerating")}
            {!muted && introNarrationStatus === "playing" &&
              t("intro.narrationPlaying")}
            {!muted && introNarrationStatus === "unavailable" &&
              t("intro.narrationUnavailable")}
          </div>
          <div className="intro-screen__hint">{t("intro.hint")}</div>
          <LocaleSwitch locale={locale} onChange={setLocale} label={t("start.language")} />
        </section>
        {error && <div className="toast">{t(error.key, error.params)}</div>}
      </main>
    );
  }

  return (
    <main className="war-room">
      <header className="war-room__topbar">
        <button
          type="button"
          className="empire-badge empire-badge--button"
          onClick={() => setShowSovereign(true)}
          title={t("topbar.sovereignPortrait")}
        >
          <div className="empire-badge__seal" style={{ background: humanColor }}>
            {(() => {
              if (!humanCiv) return "A";
              // Prefer the square profile; if the server's profile stage
              // failed, fall back to the splash so the badge still shows
              // real art rather than an initial.
              const portrait =
                assets?.leaders[humanCiv.id]?.profileUrl ??
                assets?.leaders[humanCiv.id]?.splashUrl;
              if (portrait) {
                return (
                  <img
                    className="leader-portrait__img"
                    src={portrait}
                    alt={setup.leaderName || humanCiv.leader_name}
                  />
                );
              }
              return humanCiv.name?.slice(0, 1) ?? "A";
            })()}
          </div>
          <div className="empire-badge__copy">
            <div className="empire-badge__name">
              {humanCiv?.name ?? t("topbar.civilizationFallback")}
            </div>
            <div className="empire-badge__sub">
              {setup.leaderName.trim() || humanCiv?.leader_name || t("topbar.leaderFallback")}
            </div>
            <div className="empire-badge__sub empire-badge__objective">
              {nextObjective}
            </div>
          </div>
        </button>

        <div className="war-room__metrics">
          <TopMetric label={t("metric.science")} value={humanCiv?.science ?? 0} />
          <TopMetric
            label={t("metric.gold")}
            value={humanCiv?.gold ?? 0}
            delta={formatNetDelta(
              (humanCiv?.gold_income ?? 0) - (humanCiv?.gold_upkeep ?? 0),
              t,
            )}
          />
          <TopMetric label={t("metric.culture")} value={humanCiv?.culture ?? 0} />
          <TopMetric
            label={t("metric.score")}
            value={humanCiv?.score ?? 0}
            delta={`/ ${state.score_threshold}`}
          />
          <TopMetric label={t("metric.cities")} value={humanCities.length} />
        </div>

        <div className="war-room__turnbox">
          <LocaleSwitch
            locale={locale}
            onChange={setLocale}
            label={t("start.language")}
            compact
          />
          <button
            type="button"
            className={`audio-toggle cinematic-toggle${cinematicEnabled ? "" : " is-off"}`}
            onClick={toggleCinematic}
            title={
              cinematicEnabled ? t("topbar.cinematicOn") : t("topbar.cinematicOff")
            }
            aria-label={
              cinematicEnabled ? t("topbar.cinematicDisable") : t("topbar.cinematicEnable")
            }
            aria-pressed={cinematicEnabled}
          >
            <SceneGlyph enabled={cinematicEnabled} />
          </button>
          <button
            type="button"
            className="audio-toggle"
            onClick={toggleMute}
            title={muted ? t("topbar.unmute") : t("topbar.mute")}
            aria-label={muted ? t("topbar.unmute") : t("topbar.mute")}
            aria-pressed={muted}
          >
            <AudioGlyph muted={muted} />
          </button>
          <div className="turn-box__meta">
            <span className="plate-label">{t("topbar.turn")}</span>
            <strong>{state.turn}</strong>
            <span className={`turn-state${isHumanTurn ? " is-live" : ""}`}>
              {isHumanTurn
                ? t("topbar.yourMove")
                : t("topbar.acting", {
                    civ:
                      state.civs.find((c) => c.id === state.current_civ_id)?.name ??
                      t("topbar.actingFallback"),
                  })}
            </span>
          </div>
          <button className="button-primary end-turn" onClick={endTurn} disabled={busy || !isHumanTurn}>
            {busy ? t("topbar.resolving") : t("topbar.endTurn")}
          </button>
        </div>
      </header>

      {resolvingTurn && (
        <div className="turn-resolution" aria-live="polite">
          {(() => {
            const backdrop =
              resolvingScene?.url ??
              baseScene?.url ??
              (loadingSplashUrls.length > 0
                ? loadingSplashUrls[loadingSplashIndex % loadingSplashUrls.length]
                : null);
            return backdrop ? (
              <div
                key={backdrop}
                className="turn-resolution__backdrop loading-slideshow"
                style={{ backgroundImage: `url(${backdrop})` }}
              />
            ) : null;
          })()}
          <div className="turn-resolution__veil" />
          <section className="turn-resolution__panel">
            <h2>
              {turnResolved
                ? t("resolution.turnBegins", { turn: state.turn })
                : t("resolution.resolvingTitle")}
            </h2>
            <div className="turn-resolution__scene-stage">
              {resolvingScene ? (
                <article
                  key={resolvingScene.eventId}
                  className="turn-resolution__scene turn-resolution__scene--featured"
                >
                  <img
                    src={resolvingScene.url}
                    alt={t("resolution.sceneAlt", { text: resolvingSceneCaption ?? "" })}
                  />
                  <p className="turn-resolution__caption">{resolvingSceneCaption}</p>
                </article>
              ) : !turnResolved ? (
                <div className="turn-resolution__empty">
                  <div className="spinner" />
                  <span>{t("resolution.resolving")}</span>
                </div>
              ) : (
                <div className="turn-resolution__empty">
                  <span>{t("resolution.done")}</span>
                </div>
              )}
            </div>
            <div className="turn-resolution__actions">
              <button
                className="button-primary"
                onClick={dismissResolution}
                disabled={!turnResolved}
              >
                {turnResolved ? t("resolution.continue") : t("resolution.resolvingAction")}
              </button>
            </div>
          </section>
        </div>
      )}

      <section className="war-room__layout">
        <aside className="war-room__rail war-room__rail--left">
          <Panel label={t("panel.minimap")} title={t("panel.turnTitle", { turn: state.turn })}>
            <MiniMap tiles={state.tiles} visibleTiles={activeVisibleTiles} focusHex={mapFocusHex} />
          </Panel>

          <Panel
            label={
              selectedUnit
                ? t("panel.selected", { unit: tEnum("unit", selectedUnit.type) })
                : t("panel.selection")
            }
            title={
              selectedUnit
                ? t("panel.unitTitle", {
                    unit: tEnum("unit", selectedUnit.type),
                    id: selectedUnit.id,
                  })
                : t("panel.noUnit")
            }
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
                      {t("selection.tile", { q: selectedUnit.q, r: selectedUnit.r })}
                    </div>
                    <div className="selection-hero__sub">
                      {selectedCity
                        ? t("selection.garrisoned", { city: selectedCity.name })
                        : t("selection.field")}
                    </div>
                  </div>
                </div>

                <div className="stat-grid">
                  <MetricStat
                    label={t("stat.health")}
                    value={`${selectedUnit.health}/${maxHealthFor(selectedUnit.type)}`}
                  />
                  <MetricStat label={t("stat.moves")} value={selectedUnit.moves_remaining} />
                  <MetricStat
                    label={t("stat.owner")}
                    value={state.civs[selectedUnit.owner]?.name ?? t("common.unknown")}
                  />
                </div>

                <div className="selection-actions">
                  <button onClick={() => setSelectedUnit(null)}>{t("common.clear")}</button>
                  {selectedUnit.type === "settler" && (
                    <button
                      className="button-primary"
                      onClick={openFoundCity}
                      disabled={busy || !isHumanTurn}
                    >
                      {t("city.found")}
                    </button>
                  )}
                </div>

                {selectedUnit.type === "worker" && (
                  <>
                    <div className="plate-label">{t("selection.buildImprovement")}</div>
                    {selectedUnit.work_order ? (
                      <EmptyCopy>
                        {tPlural("selection.workOrder", selectedUnit.work_order.turns_remaining, {
                          improvement: {
                            ns: "improvement",
                            value: selectedUnit.work_order.improvement,
                          },
                        })}
                      </EmptyCopy>
                    ) : (
                      <div className="list-stack">
                        {IMPROVEMENT_OPTIONS.map((opt) => (
                          <button
                            key={opt.id}
                            className="list-row"
                            onClick={() => startImprovement(selectedUnit.id, opt.id)}
                            disabled={busy || !isHumanTurn}
                            title={t(opt.hintKey)}
                          >
                            <span>{t(opt.labelKey)}</span>
                            <span>{t(opt.hintKey)}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <EmptyCopy>{t("selection.empty")}</EmptyCopy>
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
              assets={assets}
              placedStructureAssets={placedStructureAssets}
              t={t}
              onTileClick={onTileClick}
              onTileHover={(q, r) =>
                setHoveredTile(state.tiles.find((t) => t.q === q && t.r === r) ?? null)
              }
              onStructureDrop={purchaseStructure}
              onUnitClick={onUnitClick}
            />

            {otherCivs.length > 0 && (
              <div
                className="leader-ribbon"
                role="toolbar"
                aria-label={t("map.diplomaticRibbon")}
              >
                {otherCivs.map((civ) => {
                  const stanceEntry = state.stances.find(
                    (s) => s.other_civ_id === civ.id,
                  );
                  const stance = stanceEntry?.stance ?? "peace";
                  const relationship = stanceEntry?.relationship ?? 0;
                  const truceActive = stanceEntry?.truce_active ?? false;
                  const inboxCount = inboxCounts.get(civ.id) ?? 0;
                  const portrait =
                    assets?.leaders[civ.id]?.profileUrl ??
                    assets?.leaders[civ.id]?.splashUrl;
                  const ringColor = relationshipColor(relationship);
                  const factionColor = CIV_COLORS[civ.id % CIV_COLORS.length];
                  const isActive = activeConversationCivId === civ.id;
                  return (
                    <button
                      key={civ.id}
                      type="button"
                      className={`leader-ribbon__avatar${isActive ? " is-active" : ""}${truceActive ? " has-truce" : ""}`}
                      onClick={() => setActiveConversationCivId(civ.id)}
                      style={{
                        background: factionColor,
                        borderColor: ringColor,
                      }}
                      title={[
                        `${civ.name} · ${civ.leader_name}`,
                        [
                          `${tEnum("stance", stance)} · ${formatRelationship(relationship, t)}`,
                          truceActive ? t("map.truce") : null,
                          inboxCount > 0 ? t("map.inboxTag", { count: inboxCount }) : null,
                        ]
                          .filter((part): part is string => Boolean(part))
                          .join(" · "),
                      ].join("\n")}
                    >
                      {portrait ? (
                        <img
                          src={portrait}
                          alt={t("map.portraitAlt", { civ: civ.name })}
                        />
                      ) : (
                        <span className="leader-ribbon__initial">
                          {civ.name.slice(0, 1)}
                        </span>
                      )}
                      <span
                        className="leader-ribbon__stance"
                        aria-hidden="true"
                        style={{ background: ringColor }}
                      />
                      {inboxCount > 0 && (
                        <span
                          className="leader-ribbon__inbox"
                          aria-label={tPlural("map.unread", inboxCount)}
                        >
                          {inboxCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {bannerEvents && bannerEvents.length > 0 && (
              <div className="map-banner">
                <div className="plate-label">{t("map.turnChronicle")}</div>
                <ul>
                  {bannerEvents.slice(0, 4).map((event) => (
                    <li key={event.id}>
                      <span className={`log-kind log-kind--${event.kind}`}>
                        {tEnum("eventKind", event.kind)}
                      </span>
                      <span>{t(event.textKey, event.textParams)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {hoveredTile && (
              <div className="terrain-readout">
                <div className="terrain-readout__title">
                  {tEnum("terrain", hoveredTile.terrain)}
                  {hoveredTile.feature && (
                    <span> · {tEnum("feature", hoveredTile.feature)}</span>
                  )}
                </div>
                <div className="terrain-readout__yields">
                  <YieldLine label={t("yield.food")} value={hoveredTile.food} />
                  <YieldLine label={t("yield.production")} value={hoveredTile.production} />
                  <YieldLine label={t("yield.gold")} value={hoveredTile.gold} />
                </div>
                {hoveredTile.resource && (
                  <div className="terrain-readout__sub">
                    {t("map.resource", {
                      resource: tEnum("resource", hoveredTile.resource),
                    })}
                  </div>
                )}
                {(hoveredUnit || hoveredCity) && (
                  <div className="terrain-readout__sub">
                    {hoveredUnit
                      ? t("map.unitReadout", {
                          unit: tEnum("unit", hoveredUnit.type),
                          civ:
                            state.civs[hoveredUnit.owner]?.name ?? t("common.unknown"),
                          health: hoveredUnit.health,
                        })
                      : t("map.cityReadout", {
                          city: hoveredCity?.name ?? t("map.cityFallback"),
                          population: hoveredCity?.population ?? 0,
                        })}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        <aside className="war-room__rail war-room__rail--right">
          <Panel
            label={`${t("panel.research")} · ${
              currentResearch
                ? tEnum("tech", currentResearch.id)
                : t("panel.researchAwaiting")
            }`}
            title={
              currentResearch
                ? `${researchProgress} / ${currentResearch.cost}`
                : t("panel.chooseTechnology")
            }
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
            <div className="tech-choice-grid">
              {availableTechs.length === 0 ? (
                <EmptyCopy>{t("research.empty")}</EmptyCopy>
              ) : (
                availableTechs.map((tech) => (
                  <button
                    key={tech.id}
                    className="tech-choice"
                    onClick={() => chooseResearch(tech.id)}
                    disabled={busy || !isHumanTurn || humanCiv?.researching === tech.id}
                  >
                    <span className="tech-choice__icon" aria-hidden="true">
                      {TECH_EMOJIS[tech.id] ?? "✦"}
                    </span>
                    <span className="tech-choice__name">{tEnum("tech", tech.id)}</span>
                    <span className="tech-choice__cost">
                      {tech.cost} {t("research.costUnit")}
                    </span>
                  </button>
                ))
              )}
            </div>
          </Panel>

          <Panel
            label={t("panel.cities")}
            title={tPlural("city.count", humanCities.length)}
          >
            {humanCities.length === 0 ? (
              <EmptyCopy>{t("city.empty")}</EmptyCopy>
            ) : (
              <div className="list-stack">
                {humanCities.map((city) => (
                  <button
                    key={city.id}
                    type="button"
                    className={`list-row${activeCityId === city.id ? " is-active" : ""}`}
                    onClick={() => setActiveCityId(city.id)}
                  >
                    <span>
                      <strong>
                        {city.name}
                        {city.is_capital && (
                          <span style={{ color: "var(--accent)" }}> ★</span>
                        )}
                      </strong>
                      <div style={{ color: "var(--ink-muted)", fontSize: "0.78rem" }}>
                        {t("city.rowMeta", {
                          population: city.population,
                          queue: city.production_queue[0]
                            ? tEnum("unit", city.production_queue[0])
                            : t("common.idle"),
                        })}
                      </div>
                    </span>
                    <span style={{ color: "var(--ink-muted)" }}>›</span>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            label={t("panel.standings")}
            title={t("standings.goal", { goal: state.score_threshold })}
          >
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
                      {isMe ? ` ${t("common.you")}` : ""}
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
          <div className="chronicle-tab is-active">{t("chronicle.events")}</div>
          {totalInbox > 0 && (
            <button
              type="button"
              className="chronicle-tab chronicle-tab--badge"
              onClick={() => {
                if (otherCivs[0]) setActiveConversationCivId(otherCivs[0].id);
              }}
              title={t("chronicle.openDiplomacy")}
            >
              {t("chronicle.inbox", { count: totalInbox })}
            </button>
          )}
          <button
            type="button"
            className="chronicle-collapse"
            onClick={() => setChronicleCollapsed((c) => !c)}
            aria-label={
              chronicleCollapsed ? t("chronicle.expand") : t("chronicle.collapse")
            }
            title={
              chronicleCollapsed ? t("chronicle.expandShort") : t("chronicle.collapseShort")
            }
          >
            {chronicleCollapsed ? t("chronicle.show") : t("chronicle.hide")}
          </button>
        </div>

        {!chronicleCollapsed && (
          <div className="chronicle-grid">
            {eventLog.length === 0 ? (
              <EmptyCopy>{t("chronicle.empty")}</EmptyCopy>
            ) : (
              eventLog.slice(0, 9).map((event) => {
                const eventText = t(event.textKey, event.textParams);
                return (
                  <div key={event.id} className="log-row">
                    {generatedTurnSceneByEventId.has(event.id) && (
                      <img
                        className="log-row__scene"
                        src={generatedTurnSceneByEventId.get(event.id)?.url}
                        alt={t("chronicle.sceneAlt", { text: eventText })}
                      />
                    )}
                    <span className={`log-kind log-kind--${event.kind}`}>
                      {tEnum("eventKind", event.kind)}
                    </span>
                    <p>{eventText}</p>
                    {pendingTurnSceneIds.has(event.id) && (
                      <span className="log-row__scene-pending">
                        {t("chronicle.sceneForming")}
                      </span>
                    )}
                    <span className="log-turn">
                      {t("chronicle.turnTag", { turn: event.turn })}
                    </span>
                  </div>
                );
              })
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
            <div className="plate-label">{t("city.nameModalPlate")}</div>
            <h2>{t("city.nameModalTitle")}</h2>
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
              placeholder={t("start.civilizationPlaceholder")}
              autoFocus
            />
            <div className="modal-actions">
              <button
                onClick={() => {
                  setPending(null);
                  setCityName("");
                }}
              >
                {t("common.cancel")}
              </button>
              <button className="button-primary" onClick={submitFoundCity} disabled={!cityName.trim()}>
                {t("city.found")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diplomatic audience — full-screen overlay; the rival's splash art
          backs the conversation, their profile portrait anchors the hero. */}
      <div
        className={`diplomacy-audience${activeConversationCivId !== null ? " is-open" : ""}`}
        aria-hidden={activeConversationCivId === null}
        onClick={() => setActiveConversationCivId(null)}
      >
        {activeConversationCiv && (
          <>
            <div
              className="diplomacy-audience__bg"
              style={
                activeLeaderSplash
                  ? { backgroundImage: `url(${activeLeaderSplash})` }
                  : undefined
              }
            />
            <div
              className="diplomacy-audience__panel"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                className="diplomacy-audience__close"
                onClick={() => setActiveConversationCivId(null)}
                aria-label={t("diplomacy.close")}
              >
                {t("common.return")}
              </button>

              <header className="diplomacy-audience__hero">
                <LeaderPortrait
                  className="leader-row__portrait diplomacy-audience__portrait"
                  name={activeConversationCiv.name}
                  color={CIV_COLORS[activeConversationCiv.id % CIV_COLORS.length]}
                  url={
                    assets?.leaders[activeConversationCiv.id]?.profileUrl ??
                    assets?.leaders[activeConversationCiv.id]?.splashUrl
                  }
                />
                <div className="diplomacy-audience__heading">
                  <div className="plate-label">{t("diplomacy.audience")}</div>
                  <h2>{activeConversationCiv.name}</h2>
                  <div className="diplomacy-audience__leader">
                    {activeConversationCiv.leader_name}
                  </div>
                  {activeStance && (
                    <div className="thread-pills">
                      <span className="thread-pill">
                        <span className="thread-pill__label">
                          {t("diplomacy.status")}
                        </span>
                        {tEnum("stance", activeStance.stance)}
                      </span>
                      <span
                        className="thread-pill"
                        style={{ color: relationshipColor(activeStance.relationship) }}
                      >
                        <span className="thread-pill__label">
                          {t("diplomacy.relationship")}
                        </span>
                        {formatRelationship(activeStance.relationship, t)}
                      </span>
                      {activeStance.truce_active && (
                        <span className="thread-pill">
                          <span className="thread-pill__label">
                            {t("diplomacy.truce")}
                          </span>
                          {t("diplomacy.truceUntil", {
                            turn: activeStance.truce_until ?? "?",
                          })}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </header>

              <div className="diplomacy-audience__messages">
                {activeConversation.length === 0 ? (
                  <EmptyCopy>{t("diplomacy.empty")}</EmptyCopy>
                ) : (
                  [...activeConversation].reverse().map((message, index) => (
                    <MessageCard
                      key={`${message.turn}-${message.from_civ_id}-${message.to_civ_id}-${index}`}
                      message={message}
                      civs={state?.civs ?? []}
                      humanCivId={humanCiv?.id ?? null}
                      t={t}
                      tEnum={tEnum}
                    />
                  ))
                )}
              </div>

              <div className="diplomacy-audience__composer">
                <label className="field">
                  <span className="field-label">{t("diplomacy.tone")}</span>
                  <select value={messageKind} onChange={(e) => setMessageKind(e.target.value)}>
                    {availableMessageKinds.map((kind) => (
                      <option key={kind.id} value={kind.id}>
                        {t(kind.labelKey)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="field-label">{t("diplomacy.message")}</span>
                  <input
                    type="text"
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    placeholder={t("diplomacy.replyPlaceholder", {
                      civ: activeConversationCiv.name,
                    })}
                  />
                </label>
                {activeStance?.truce_active && (
                  <div className="empty-copy">
                    {t("diplomacy.truceBlocked", {
                      turn: activeStance.truce_until ?? "?",
                    })}
                  </div>
                )}
                <button
                  className="button-primary"
                  onClick={sendMessage}
                  disabled={busy || !isHumanTurn || !messageText.trim()}
                >
                  {t("diplomacy.send")}
                </button>
              </div>

              {activeDiplomaticEvents.length > 0 && (
                <details className="incidents-details">
                  <summary>
                    {t("diplomacy.incidents", { count: activeDiplomaticEvents.length })}
                  </summary>
                  <div className="list-stack">
                    {[...activeDiplomaticEvents].reverse().slice(0, 8).map((event, index) => (
                      <div
                        key={`${event.turn}-${event.kind}-${index}`}
                        className="list-row"
                        style={{ cursor: "default" }}
                      >
                        <span>
                          {t("diplomacy.incidentRow", {
                            turn: event.turn,
                            kind: { ns: "diplomaticEvent", value: event.kind },
                          })}
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
            </div>
          </>
        )}
      </div>

      {/* City drawer — slides in from the right when a city is clicked. */}
      <aside
        className={`city-drawer${activeCityId !== null ? " is-open" : ""}`}
        aria-hidden={activeCityId === null}
      >
        {activeCity && (
          <>
            <header className="city-drawer__header">
              <div>
                <div className="plate-label">
                  {activeCity.is_capital ? t("city.capital") : t("city.settlement")}
                </div>
                <strong className="city-drawer__name">{activeCity.name}</strong>
                <div className="city-drawer__sub">
                  {t("selection.tile", { q: activeCity.q, r: activeCity.r })}
                </div>
              </div>
              <button
                type="button"
                className="city-drawer__close"
                onClick={() => setActiveCityId(null)}
                aria-label={t("city.close")}
              >
                ×
              </button>
            </header>

            <div className="city-brief">
              <MetricStat label={t("stat.population")} value={activeCity.population} />
              <MetricStat
                label={t("stat.health")}
                value={`${activeCity.health}/${activeCity.max_health}`}
              />
              <MetricStat label={t("stat.food")} value={activeCity.food_stored} />
              <MetricStat
                label={t("stat.production")}
                value={activeCity.production_stored}
              />
              <MetricStat
                label={t("stat.border")}
                value={t("city.borderRing", { radius: activeCity.border_radius ?? 1 })}
              />
              <MetricStat
                label={t("stat.culture")}
                value={
                  activeCity.border_radius >= 3
                    ? t("city.cultureMax", { stored: activeCity.culture_stored ?? 0 })
                    : `${activeCity.culture_stored ?? 0} / ${
                        activeCity.border_radius >= 2 ? 30 : 10
                      }`
                }
              />
            </div>

            <div className="city-drawer__section">
              <div className="plate-label">{t("city.productionQueue")}</div>
              {activeCity.production_queue.length === 0 ? (
                <EmptyCopy>{t("city.queueEmpty")}</EmptyCopy>
              ) : (
                <div className="list-stack">
                  {activeCity.production_queue.map((item, idx) => (
                    <div
                      key={`${item}-${idx}`}
                      className="list-row"
                      style={{ cursor: "default" }}
                    >
                      <span>
                        {idx === 0 ? "▶ " : `${idx + 1}. `}
                        {tEnum("unit", item)}
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        {idx === 0 && (
                          <small style={{ color: "var(--ink-muted)" }}>
                            {t("city.queueStored", { stored: activeCity.production_stored })}
                          </small>
                        )}
                        <button
                          type="button"
                          className="city-drawer__cancel"
                          onClick={() => cancelProduction(activeCity.id, idx)}
                          disabled={busy || !isHumanTurn}
                          title={idx === 0 ? t("city.cancelHead") : t("city.cancelOther")}
                          aria-label={t("city.cancelOther")}
                        >
                          ×
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="city-drawer__section">
              <div className="plate-label">{t("city.buildOrder")}</div>
              {buildableUnits.length === 0 ? (
                <EmptyCopy>{t("city.buildEmpty")}</EmptyCopy>
              ) : (
                <div className="list-stack city-drawer__buildables">
                  {buildableUnits.map((unit) => (
                    <button
                      key={unit.id}
                      type="button"
                      className="list-row"
                      onClick={() => queueProduction(activeCity.id, unit.id)}
                      disabled={busy || !isHumanTurn}
                    >
                      <span>{tEnum("unit", unit.id)}</span>
                      <span>{t("city.buildCost", { cost: unit.cost })}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="city-drawer__section">
              <div className="plate-label">
                {t("city.structures", { gold: humanCiv?.gold ?? 0 })}
              </div>
              <p className="empty-copy" style={{ margin: 0 }}>
                {t("city.structuresHelp", {
                  cost: STRUCTURE_GOLD_COST,
                  bonus: STRUCTURE_PRODUCTION_BONUS,
                })}
              </p>
              <div className="list-stack">
                {STRUCTURE_CATEGORIES.map((cat) => {
                  const owned = activeCity.purchased_structures.includes(cat.id);
                  const canAfford = (humanCiv?.gold ?? 0) >= STRUCTURE_GOLD_COST;
                  const disabled = owned || !canAfford || busy || !isHumanTurn;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      className="list-row"
                      draggable={!disabled}
                      onDragStart={(event) => {
                        event.dataTransfer.effectAllowed = "copy";
                        event.dataTransfer.setData(
                          "application/x-city-structure",
                          JSON.stringify({
                            cityId: activeCity.id,
                            category: cat.id,
                          }),
                        );
                      }}
                      onClick={() =>
                        setError({ key: "error.structureDrop" })
                      }
                      disabled={disabled}
                      title={
                        owned
                          ? t("city.structureOwned")
                          : !canAfford
                            ? t("city.structureNeedGold", { cost: STRUCTURE_GOLD_COST })
                            : t("city.structureDragHint")
                      }
                    >
                      <span>
                        <strong>{tEnum("structure", cat.id)}</strong>
                        <div
                          style={{
                            color: "var(--ink-muted)",
                            fontSize: "0.78rem",
                          }}
                        >
                          {tEnum("structure", cat.id, "hint")}
                        </div>
                      </span>
                      <span>
                        {owned ? (
                          <span style={{ color: "var(--accent)" }}>
                            {t("city.structureBuilt")}
                          </span>
                        ) : (
                          t("city.structurePrice", { gold: STRUCTURE_GOLD_COST })
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {activeCity.buildings.length > 0 && (
              <details className="incidents-details">
                <summary>
                  {t("city.buildings", { count: activeCity.buildings.length })}
                </summary>
                <div className="list-stack">
                  {activeCity.buildings.map((b, i) => (
                    <div
                      key={`${b}-${i}`}
                      className="list-row"
                      style={{ cursor: "default" }}
                    >
                      <span>{tEnum("building", b)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </aside>

      {/* Sovereign portrait — opened by clicking the empire badge. */}
      {showSovereign && humanCiv && (
        <div
          className="intro-screen sovereign-overlay"
          onClick={() => setShowSovereign(false)}
        >
          {loadingSplashUrls.length > 0 && (
            <div
              key={loadingSplashUrls[sovereignSplashIndex % loadingSplashUrls.length]}
              className="loading-slideshow sovereign-overlay__slideshow"
              style={{
                backgroundImage: `url(${loadingSplashUrls[sovereignSplashIndex % loadingSplashUrls.length]})`,
              }}
            />
          )}
          <div
            className="intro-screen__bg"
            style={
              assets?.leaders[humanCiv.id]?.splashUrl
                ? {
                    backgroundImage: `url(${assets.leaders[humanCiv.id].splashUrl})`,
                  }
                : undefined
            }
          />
          <button
            type="button"
            className="sovereign-overlay__close"
            onClick={(e) => {
              e.stopPropagation();
              setShowSovereign(false);
            }}
            aria-label={t("sovereign.close")}
          >
            {t("common.return")}
          </button>
          <section
            className="intro-screen__panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="plate-label intro-screen__chapter">{t("sovereign.plate")}</div>
            <h1 className="intro-screen__civ">{humanCiv.name}</h1>
            <div className="intro-screen__leader">
              {setup.leaderName.trim() || humanCiv.leader_name}
            </div>
            <p className="intro-screen__epitaph">
              {setup.leaderDescription.trim() || t("sovereign.defaultDescription")}
            </p>
            <div className="intro-screen__hint">{t("sovereign.hint")}</div>
          </section>
        </div>
      )}

      {error && <div className="toast">{t(error.key, error.params)}</div>}
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

function LeaderPortrait({
  name,
  color,
  url,
  className,
}: {
  name: string;
  color: string;
  url?: string;
  className: string;
}) {
  return (
    <span className={className} style={{ background: color }}>
      {url ? (
        <img className="leader-portrait__img" src={url} alt={name} />
      ) : (
        name.slice(0, 1)
      )}
    </span>
  );
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
        gridTemplateRows: `repeat(${height}, minmax(0, 1fr))`,
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
  t,
  tEnum,
}: {
  message: GameStateDTO["messages"][number];
  civs: GameStateDTO["civs"];
  humanCivId?: number | null;
  t: TFunction;
  tEnum: (namespace: string, value: string | null | undefined, suffix?: string) => string;
}) {
  const from = civs.find((civ) => civ.id === message.from_civ_id);
  const to = civs.find((civ) => civ.id === message.to_civ_id);
  const direction =
    humanCivId !== null && humanCivId !== undefined
      ? message.from_civ_id === humanCivId
        ? "sent"
        : "received"
      : null;
  return (
    <article className={`message-card${direction === "sent" ? " is-sent" : ""}`}>
      <div className="message-card__meta">
        <strong>
          {t("message.fromTo", {
            from: from?.name ?? t("message.civFallback", { id: message.from_civ_id }),
            to: to?.name ?? t("message.civFallback", { id: message.to_civ_id }),
          })}
        </strong>
        <span>
          {t("message.turn", { turn: message.turn })}
          {direction
            ? ` · ${t(direction === "sent" ? "message.sent" : "message.received")}`
            : ""}
        </span>
      </div>
      <div className="message-card__kind">{tEnum("messageKind", message.kind)}</div>
      <p>{message.text}</p>
    </article>
  );
}

function formatNetDelta(net: number, t: TFunction): string {
  if (net > 0) return t("metric.goldDeltaPositive", { value: net });
  if (net < 0) return t("metric.goldDeltaNegative", { value: net });
  return t("metric.goldDeltaZero");
}

// Composition/staging variety only — lighting and time of day are owned by the
// structured time_of_day enum (sceneCinematicsFor), so these must not name a
// time of day or weather or they contradict it. Focus on props, crowd, and
// camera framing so each fallback scene still feels distinct.
function turnSceneAccent(turn: number): string {
  const accents = [
    "Fill the foreground with fresh construction dust, scattered tools, and workers mid-task for a lived-in feel.",
    "Stage urgent movement — figures hurrying, banners shifting — so the scene feels active rather than ceremonial.",
    "Add wind-stirred banners and a churned, busy ground so it reads as a working site, not a still council chamber.",
    "Crowd the foreground with timber, stone chips, and laboring figures layered in front of the leader.",
    "Spread maps over rough wooden crates with scouts gesturing toward the distance for a frontier feel.",
    "Surround the leader with carts, citizens, standards, and visible civic motion in a busy public space.",
  ];
  return accents[turn % accents.length];
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

/** Relationship band for a score, as a translation key. */
function relationshipKey(score: number): TranslationKey {
  if (score <= -60) return "relationship.furious";
  if (score <= -30) return "relationship.hostile";
  if (score <= -10) return "relationship.cold";
  if (score < 10) return "relationship.neutral";
  if (score < 30) return "relationship.warm";
  if (score < 60) return "relationship.friendly";
  return "relationship.devoted";
}

/** `+42 Friendly` / `-40 Hostile` — signed score plus its translated band. */
function formatRelationship(score: number, t: TFunction): string {
  return `${score >= 0 ? "+" : ""}${score} ${t(relationshipKey(score))}`;
}

function relationshipColor(score: number): string {
  if (score <= -30) return "#d97a6a";
  if (score < 10) return "#bba27a";
  if (score < 30) return "#dfca85";
  return "#8fcf7a";
}

/**
 * A pending error toast, held as a translation key + params rather than as
 * text: the toast then renders in whatever language is current, and an async
 * request that settles after a language switch cannot bake in a stale one.
 */
type AppError = { key: TranslationKey; params?: TranslateParams };

/**
 * Turns an API or network failure into a locale-independent toast descriptor.
 * Validation details come from the backend in English by contract, so they are
 * shown verbatim rather than guessed at.
 */
function toAppError(e: unknown): AppError {
  const message = e instanceof Error ? e.message : String(e);
  const httpMatch = /^(\d{3})\b[^:]*:\s*([\s\S]*)$/.exec(message);
  if (httpMatch) {
    return {
      key: "error.requestFailed",
      params: { status: httpMatch[1], detail: errorDetail(httpMatch[2]) },
    };
  }
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return { key: "error.network" };
  }
  return { key: "error.unexpected", params: { message } };
}

/** FastAPI errors arrive as `{"detail": "..."}`; show just the detail. */
function errorDetail(body: string): string {
  try {
    const parsed: unknown = JSON.parse(body);
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const detail = (parsed as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
  } catch {
    // Not JSON — fall through to the raw body.
  }
  return body.trim();
}

/**
 * True when a key event targets a control that owns its own activation keys
 * (buttons, links, fields), so screen-level shortcuts can stand aside.
 */
function isInteractiveTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    target.closest(
      "button, a[href], input, select, textarea, [role='button'], [contenteditable='true']",
    ) !== null
  );
}

function LocaleSwitch({
  locale,
  onChange,
  label,
  compact,
}: {
  locale: Locale;
  onChange: (locale: Locale) => void;
  label: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`locale-switch${compact ? " locale-switch--compact" : ""}`}
      role="group"
      aria-label={label}
      title={label}
    >
      {LOCALES.map((value) => {
        const active = value === locale;
        return (
          <button
            key={value}
            type="button"
            className={`locale-switch__option${active ? " is-active" : ""}`}
            onClick={() => onChange(value)}
            aria-pressed={active}
            aria-label={LOCALE_LABELS[value].name}
            title={LOCALE_LABELS[value].name}
            lang={value}
          >
            {compact ? LOCALE_LABELS[value].short : LOCALE_LABELS[value].name}
          </button>
        );
      })}
    </div>
  );
}
