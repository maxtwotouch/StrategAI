# StrategAI — Frontend & UI Guide

How the Next.js app is organized, the lifecycle of a game session, and where
each piece of UI lives. For game rules see
[GAMEPLAY.md](GAMEPLAY.md); for asset integration see
[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md).

---

## 1. App Structure

```
frontend/
├── app/
│   ├── page.tsx          single client page; owns all game state
│   ├── layout.tsx        Next.js root layout
│   └── globals.css       global styles, design tokens, all UI surfaces
├── components/
│   ├── SquareMap.tsx     SVG-rendered map (drag/zoom, tiles, units, cities)
│   └── mapTypes.ts       StrategyMapProps
├── lib/
│   ├── api.ts            game backend client + DTOs
│   ├── hex.ts            grid math + TERRAIN/UNIT/IMPROVEMENT glyph tables
│   ├── turnEvents.ts     diff prev/next GameState → TurnEvent[]
│   ├── assetApi.ts       asset service client (POST /leader, etc.)
│   ├── assetManifest.ts  resolveManifest() + per-game cache
│   ├── assetMapping.ts   game taxonomy → asset enums (units, structures, elevation)
│   ├── leaderMapping.ts  deterministic leader → enum/description map
│   └── useAudio.ts       intro swell + ambient bed, mute toggle, fades
└── .env.local            NEXT_PUBLIC_API_URL + NEXT_PUBLIC_ASSET_API_URL
```

State is intentionally centralized in `app/page.tsx` — drilling props beats
context for this app size and keeps the data flow legible.

---

## 2. Session Lifecycle

```
┌──────────────────────────────────────────────────────────────┐
│                    StartScreen                                │
│  Civilization Name · Leader Name · Archetype · Culture        │
│  Description · Map Radius · "Begin Campaign"                  │
└──────────────────────────────────────────────────────────────┘
                            │ click
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   LoadingScreen                               │
│  spinner · "Surveying the land…"                              │
│  "Conjuring world art… 8/16"  ← assetProgress                 │
│                                                               │
│  Behind the scenes:                                           │
│   1. api.createGame()      → backend builds map               │
│   2. resolveManifest({ … }) → asset service POSTs             │
└──────────────────────────────────────────────────────────────┘
                            │ both resolved
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   IntroScreen                                 │
│  Full-bleed splash backdrop (your civ's splash art),          │
│  Ken Burns zoom 12s, dark radial vignette                     │
│  Chapter I · {Civ Name} · "Under the reign of {Leader}"       │
│  Epic line · "Begin the Age" CTA                              │
│  Dismiss: click backdrop / CTA / Esc / Enter / Space          │
└──────────────────────────────────────────────────────────────┘
                            │ introDismissed=true
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     WarRoom                                   │
│  (the main play surface, see §3)                              │
└──────────────────────────────────────────────────────────────┘
```

`loadGame()` in `page.tsx` resets `introDismissed`, `assets`, and selection
state at every "Begin Campaign". The audio hook (`useAudio`) plays the intro
swell as soon as the user clicks, then crossfades to the ambient bed when the
intro screen is dismissed.

---

## 3. War Room Layout

```
┌─ topbar ──────────────────────────────────────────────────────────────────┐
│ EmpireBadge (clickable→Sovereign overlay) │ Metrics │ Audio · Global/Local │
│  ┌────┐ Civ Name                          │ Sci 12  │ 🔊  ┌─────┬─────┐    │
│  │img│ Leader Name                        │ Gold 47 │     │GLOB │LOCAL│    │
│  └────┘ Next objective hint               │ Cult 8  │     └─────┴─────┘    │
│                                           │ Score   │     Turn 14          │
│                                           │ Cities  │     [End Turn]       │
├───────────┬─────────────────────────────────┬───────────────────────────────┤
│ Left rail │              Map                │ Right rail                    │
│ (260px)   │  ┌─────────────────────────┐    │ (260px)                       │
│           │  │                         │    │                               │
│ Minimap   │  │   SquareMap (SVG)       │    │ Research panel                │
│           │  │   drag to pan           │    │  current tech progress        │
│ Selection │  │   wheel to zoom         │    │  available techs              │
│  unit     │  │   click tile to act     │    │                               │
│  actions  │  │                         │    │ Cities list                   │
│  improve  │  │   hover → terrain       │    │  click row → open City Drawer │
│  found    │  │   readout overlay       │    │                               │
│           │  └─────────────────────────┘    │ Other Leaders                 │
│           │  Turn Chronicle banner          │  click row → Diplo Audience   │
│           │  (briefly during turn changes)  │                               │
│           │                                 │ Standings                     │
├───────────┴─────────────────────────────────┴───────────────────────────────┤
│                            Chronicle (events log)                            │
└───────────────────────────────────────────────────────────────────────────┘
```

### Topbar

- **Empire Badge** (left). Click anywhere on it → opens the **Sovereign
  Portrait Overlay**. The badge shows the human civ's profile portrait if the
  manifest resolved one; otherwise falls back to the civ's first initial in
  the gold hex seal.
- **Metrics**. Science (total), Gold (with `+net/turn` delta), Culture,
  Score (vs threshold), Cities (count).
- **Audio toggle**. `🔊` / `🔇`. Persists in `localStorage` under
  `inf3600:audioMuted`.
- **Map mode toggle**. `Global` ignores fog; `Local` shows visible-tile fog.
- **Turn box**. Turn counter, "Your Move" / "{Civ} Acting" label, **End Turn**.

### Left rail

- **Minimap**. A canvas thumbnail of the map; tinted by terrain, brighter for
  visible tiles, with a focus dot on the selected unit/city.
- **Selection panel**. When a unit is selected: stats, owner, action buttons
  (Found City for Settlers, Build Improvement for Workers, Clear).

### Center

The map plus two overlays:
- **Turn Chronicle banner** appears briefly when a turn flips, summarizing
  the top events (kills, foundings, diplomacy).
- **Terrain readout** appears at the bottom edge when hovering a tile —
  terrain name + feature, food/prod/gold yields, resource label, occupant
  unit/city summary.

### Right rail

- **Research panel**. Progress bar + scroll list of techs whose prerequisites
  are met. Click a tech to start researching it.
- **Cities list**. Compact rows (name + capital ★ + `pop · queue head`). Click
  a row to open the City Drawer; the active city row is highlighted.
- **Other Leaders**. Compact rows for each met rival: portrait or initial,
  civ name, stance + relationship + truce badge + unread inbox count. Click
  to open the Diplomatic Audience.
- **Standings**. The score table; your row is bolded.

### Chronicle (bottom)

Collapsible event log fed by `lib/turnEvents.ts`. Each row: event kind
(`combat`, `diplomacy`, `production`, etc.) · short text · turn number.
Caps at 80 most-recent events; banner shows the top 4 per turn flip.

---

## 4. The Map

Component: `components/SquareMap.tsx`. Renders an SVG `<svg>` containing
layered `<g>` groups (bottom-up):

1. **Color fill** — `TERRAIN_COLORS[tile.terrain]` per tile, with a
   deterministic 14-step jitter so adjacent same-type tiles vary slightly.
2. **Terrain sprite layer** — when `assets.terrain[tile.terrain]` is
   resolved, an `<image>` is drawn fill-tile. `onError` adds the URL to
   `failedHrefs` and drops it next render, falling back to the color fill.
3. **Elevation overlay** — for `hills` and `mountain`, a separate transparent
   `<image>` sits on top of the base tile.
4. **Rivers, feature glyphs, resource badges, improvement glyphs, worked-tile
   markers, grid lines.**
5. **Fog overlay** — semi-opaque rect over any tile not in `visibleTiles`.
6. **Borders** — your golden ring + thinner rival-colored rings derived from
   `tile_owner`.
7. **Reachable highlight** — when a unit is selected, a 1-tile yellow tint on
   adjacent tiles.
8. **Cities** — building image (faction-color ring) when art is available;
   otherwise a colored card. Name label below.
9. **Units** — sprite + faction-color dot anchor when art is available;
   otherwise the colored rect + glyph. Selection ring above; work-order
   improvement badge below.
10. **Hover/highlight outlines** + transparent **hit zones** that own all
    pointer events.

### Interactions

- **Drag** with left mouse to pan. Pan deltas batch into one `requestAnimationFrame`
  per frame so fast cursor sweeps stay smooth.
- **Wheel** to zoom around the cursor (cursor-anchored — pixel under cursor
  stays put).
- **Click** a unit → select it (your own units only; rival units are click-
  through unless you have one of yours selected adjacent for an attack).
- **Click** an adjacent tile (with a unit selected) → move there.
- **Click** an adjacent rival unit (with one of yours selected) → attack
  (requires `war` stance).
- **Click** a human-owned city tile (with no selected unit, or your selected
  unit isn't adjacent) → opens the City Drawer.

The defensive guard in `onTileClick` (and the explicit owner check in
`onUnitClick`) prevents accidentally commanding rival units.

---

## 5. Drawers & Overlays

### City Drawer (slide-in from the right)

Opens when:
- A row in the right-rail **Cities** list is clicked, **or**
- A human-owned city tile is clicked on the map.

Dismiss: `×` button, Esc, click another city.

Contains:
- City name + capital badge + tile coords.
- **6 metric stats** in a 2×2 grid: Population, Health, Food, Production,
  Border (R1/R2/R3), Culture (current / threshold).
- **Production Queue** section — list of queued items; head shows `▶ Item`
  with current `production_stored`. Each row has a red `×` cancel button
  (head row warns the click forfeits stored production).
- **Build Order** — clickable list of every buildable unit. Disabled when
  it's not your turn or a request is in flight.
- **Structures** — current gold display, then the 4 asset-API categories
  (Production Hall / Fortification / Housing District / Sacred Site) as
  buy-rows. Disabled state shows `✓ Built` when owned, or the price when you
  can't afford it.
- **Buildings** (collapsible details) — list of completed queue-built
  buildings (Granary, Library, etc.).

CSS classes: `.city-drawer*` in `globals.css`. Positioned `position: fixed;
right: 0; width: min(420px, 100vw)`. Slides via `transform: translateX`.

### Diplomatic Audience (full-screen overlay)

Replaces the older slide-in drawer. Opens when a row in the right-rail
**Other Leaders** panel is clicked.

Visual:
- **Backdrop**: the rival's splash art at full bleed, dimmed via radial
  + linear gradients for legibility. If no splash is resolved yet, a dark
  gradient still backs the panel.
- **Panel**: centered parchment card (`rgba(245, 238, 219, 0.95)` with backdrop
  blur). Black-on-cream typography.
- **Hero**: 96px portrait + `Civ Name` (display font) + leader name + stance
  pills (Status · Rel score + label · Truce until Tn).
- **Messages**: scrollable thread of `MessageCard`s with sent/received
  treatment.
- **Composer**: Tone select (filtered to allowed kinds if truce is active)
  + Message input + Send button.
- **Recent Incidents** (collapsible) — `DiplomaticEvent` rows with deltas.

Dismiss: `× Return` top-right, Esc, click anywhere outside the panel.

### Sovereign Portrait Overlay

Reuses the intro-screen classes. Opens by clicking the Empire Badge.

Same visual language as the intro screen (full-bleed splash + Ken Burns +
gradient vignette + rise-in panel animation), with:
- "Sovereign" plate label instead of "Chapter I"
- Civ Name + Leader Name + the user's own leader description (or a neutral
  default) + `× Return` button.

Dismiss: `× Return`, Esc, click anywhere outside the panel.

---

## 6. Audio

`lib/useAudio.ts` manages two `HTMLAudioElement`s:

| Track | File | When | Default volume |
|---|---|---|---:|
| intro | `public/audio/intro.mp3` | Begin Campaign → intro dismiss | 0.60 |
| ambient | `public/audio/ambient.mp3` | Intro dismiss → forever (loops) | 0.22 |

API surface:

```ts
const { muted, toggleMute, startIntro, startAmbient } = useAudio();
```

- `startIntro()` is called inside the **Begin Campaign click handler** — that's
  the user gesture that unlocks audio under browser autoplay rules. Plays the
  intro track and ramps it in over 1.2s.
- `startAmbient()` is called inside `dismissIntro()` — fires whether the
  user clicks the CTA, taps the backdrop, or hits Esc/Enter/Space. Crossfades
  intro → ambient over 2.4s.
- `toggleMute()` flips mute on both elements; the choice persists in
  `localStorage` under `inf3600:audioMuted`.

Missing files are tolerated: `audio.play()` returns a rejected promise which
is silently caught. Volume ramps are clamped to `[0, 1]` to avoid
`IndexSizeError` when overlapping fades land slightly negative due to float
drift.

Tuning knobs at the top of `lib/useAudio.ts`:
`INTRO_SRC`, `AMBIENT_SRC`, `INTRO_VOLUME`, `AMBIENT_VOLUME`,
`INTRO_FADE_IN_MS`, `CROSSFADE_MS`.

---

## 7. Diff-Driven Turn Chronicle

`lib/turnEvents.ts:diffTurnEvents({ prev, next, humanCivId })` returns a list
of `TurnEvent { id, kind, text, turn }`. Called from `ingestEvents` inside
every `run()` action wrapper in `page.tsx`. Events feed both:

- The **banner** above the map — top 4 events for 4.5s.
- The **Chronicle** at the bottom — keeps the last 80 events.

Kinds include `combat`, `diplomacy`, `production`, `growth`, `research`,
`exploration`, `bankruptcy`, etc. (the full list lives in `turnEvents.ts`).

---

## 8. Styling Notes

- All theme tokens live as CSS custom properties on `:root` in `globals.css`
  (`--ink`, `--accent`, `--panel`, spacing scale, shadows, font stacks).
- Display font: `Baskerville` (serif) for headings, leader names, panel
  titles. Body: `Avenir Next`.
- The map uses inline SVG with `shape-rendering: crispEdges` to avoid
  blurry tile edges at fractional zoom levels.
- Hover/selection/focus states use `:hover:not(:disabled)` and
  `:focus-visible` so accessibility is preserved without visual noise.
- Inputs in the start screen use a white-bg/black-text variant for
  legibility on the dark panel; the Diplomatic Audience adopts the parchment
  treatment for the same reason.

---

## 9. Where to Hook In

| Adding a... | Where to wire it |
|---|---|
| New unit type | `BUILDABLE_UNITS` in `page.tsx`, `UNIT_GLYPH`/`UNIT_LABEL` in `lib/hex.ts`, plus backend `UnitType` enum. |
| New tech | Mirror in the `TECHS` constant in `page.tsx` and add it to `backend/app/engine/research.py`. |
| New right-rail panel | Add a `<Panel>` block inside `.war-room__rail--right`. |
| New overlay | Mirror the `.diplomacy-audience*` or `.intro-screen*` CSS pattern; render at the bottom of the `<main className="war-room">` JSX. |
| New asset family | Extend `AssetManifest`, add a `generate*` in `assetApi.ts`, fan out a `mapLimit` batch in `assetManifest.ts`, and consume the resolved URL in `SquareMap.tsx` or wherever it surfaces. |
| New turn-event kind | Emit it from the backend turn report, then handle it in `turnEvents.ts` (`diffTurnEvents`) and add a CSS class `.log-kind--{kind}`. |
