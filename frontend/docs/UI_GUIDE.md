# StrategAI — Frontend & UI Guide

How the Next.js app is organized, the lifecycle of a game session, and where
each piece of UI lives. For game rules see
[../../GAMEPLAY.md](../../GAMEPLAY.md); for asset integration see
[../../docs/ASSET_INTEGRATION.md](../../docs/ASSET_INTEGRATION.md).

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
│   ├── assetManifest.ts  resolveManifest() per-game asset resolver
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
│ EmpireBadge (clickable→Sovereign overlay) │ Metrics │ Audio · Turn box     │
│  ┌────┐ Civ Name                          │ Sci 12  │ speaker icon         │
│  │img│ Leader Name                        │ Gold 47 │ Turn 14              │
│  └────┘ Next objective hint               │ Cult 8  │ [End Turn]           │
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
│  improve  │  │   diplomatic ribbon →   │    │  click row → open City Drawer │
│  found    │  │     met-leader avatars  │    │                               │
│           │  │     on right edge       │    │ Standings                     │
│           │  └─────────────────────────┘    │  goal score + per-civ progress│
│           │  Turn Chronicle banner          │                               │
│           │  (briefly during turn changes)  │                               │
├───────────┴─────────────────────────────────┴───────────────────────────────┤
│                            Chronicle (events log)                            │
└───────────────────────────────────────────────────────────────────────────┘
```

### Topbar

- **Empire Badge** (left). Click anywhere on it → opens the **Sovereign
  Portrait Overlay**. The badge shows the human civ's profile portrait if the
  manifest resolved one; otherwise falls back to the civ's first initial in a
  large faction-color circular seal.
- **Metrics**. Science (total), Gold (with `+net/turn` delta), Culture,
  Score (vs threshold), Cities (count).
- **Audio toggle**. A compact SVG speaker control with unmuted/muted states.
  Persists in `localStorage` under `inf3600:audioMuted`.
- **Turn box**. Turn counter, "Your Move" / "{Civ} Acting" label, **End Turn**.

### Left rail

- **Minimap**. A compact grid thumbnail of the explored map; tinted by
  terrain, brighter for visible tiles, with a focus outline on the selected
  unit/city. It is capped to a small centered footprint so it does not push the
  rail downward.
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
- **Standings**. The score table; your row is bolded.

The "Other Leaders" right-rail panel that used to live here has been replaced
by the **Diplomatic Ribbon** floating on the map (see §4.1 below). Met-leader
interaction now happens entirely on the map surface.

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
8. **Placed structures** — purchased structure art on the tile where the
   player dropped it; fallback is a compact colored building marker.
9. **Cities** — city center marker with faction-color styling and name label.
10. **Units** — sprite + faction-color dot anchor when art is available;
   otherwise the colored rect + glyph. Selection ring above; work-order
   improvement badge below.
11. **Hover/highlight outlines** + transparent **hit zones** that own all
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

### 4.1 Diplomatic Ribbon (met-leader portraits on the map)

Civ-style vertical column of leader portraits pinned to the **right edge of
the map area**, below the zoom/Recenter HUD. Lives inside `.map-frame` as
absolutely-positioned siblings of the SVG, defined in `app/page.tsx` and
styled by `.leader-ribbon*` rules in `globals.css`.

For each met civ:
- **56px circle** (44px on viewports ≤ 1100px) with the leader's profile or
  splash art (`object-position: center 20%` biases the crop toward the face
  region of cinematic splashes).
- Faction color as the background fallback when no art is loaded yet.
- **Ring border colored by the diplomatic relationship** (red → hostile,
  gold → neutral, green → friendly) using the same `relationshipColor` palette
  the audience uses for its pills.
- A small **stance dot** in the bottom-right reinforces the ring color (which
  can be hard to read over dark splash crops).
- **Dashed gold halo** when a truce is active.
- **Gold count pill** at the top-right for unread inbox messages from that
  civ.
- **Active outline** when the Diplomatic Audience is open with that civ.

Interaction: click an avatar → `setActiveConversationCivId(civ.id)` → opens
the Diplomatic Audience. Hover gets a `title=` tooltip with name + leader
name + stance + relationship + truce/inbox counts.

The ribbon animates in (`leader-ribbon-fade-in`, 320ms) when it first appears
and each avatar lifts slightly on hover.

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
  draggable buy-rows. Drag an enabled row onto an empty tile inside that city's
  borders to purchase/place it. Disabled state shows `✓ Built` when owned, or
  the price when you can't afford it.
- **Buildings** (collapsible details) — list of completed queue-built
  buildings (Granary, Library, etc.).

CSS classes: `.city-drawer*` in `globals.css`. Positioned `position: fixed;
right: 0; width: min(420px, 100vw)`. Slides via `transform: translateX`.

### Diplomatic Audience (full-screen overlay)

Replaces the older slide-in drawer. Opens by clicking a leader avatar in the
**Diplomatic Ribbon** on the map edge.

Visual:
- **Backdrop**: the rival's splash art at full bleed. A radial vignette is
  biased to the right (`ellipse at 68% 40%`) so the brightest spot of the
  lighting lands on the exposed portion of the splash; the panel side gets a
  gentle darken to anchor it. If no splash is resolved yet, a dark gradient
  still backs the panel.
- **Panel**: translucent parchment card (`rgba(245, 238, 219, 0.82)` with
  12px `backdrop-filter` blur + saturate). **Anchored bottom-left**
  (`align-items: flex-end; justify-content: flex-start; margin: 0 0 3vh 3vw`),
  width `min(560px, 90vw)`, max-height 82vh — so the splash art dominates the
  upper-right of the screen rather than being covered. Black-on-cream
  typography stays legible against any backdrop tone thanks to the blur.
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

`lib/useAudio.ts` manages one `HTMLAudioElement` with a playlist:

| Track | File | When | Default volume |
|---|---|---|---:|
| playlist | `public/audio/ambient.mp3` | Begin Campaign → intro dismiss | 0.60 |
| playlist | `public/audio/bards-tale.mp3` | Auto-advances after current track ends | 0.22 |
| playlist | `public/audio/medieval-battle.mp3` | Auto-advances after current track ends | 0.22 |

The bundled music comes from OpenGameArt. Attribution and license details are recorded in
`public/audio/ATTRIBUTION.md`.

API surface:

```ts
const { muted, toggleMute, startIntro, startAmbient } = useAudio();
```

- `startIntro()` is called inside the **Begin Campaign click handler** — that's
  the user gesture that unlocks audio under browser autoplay rules. Starts the
  playlist and ramps it in over 1.2s.
- `startAmbient()` is called inside `dismissIntro()` — fires whether the
  user clicks the CTA, taps the backdrop, or hits Esc/Enter/Space. It lowers the
  live track to ambient volume over 2.4s.
- `toggleMute()` flips mute on the music element; the choice persists in
  `localStorage` under `inf3600:audioMuted`.

Missing files are tolerated: `audio.play()` returns a rejected promise which
is silently caught. Volume ramps are clamped to `[0, 1]` to avoid
`IndexSizeError` when overlapping fades land slightly negative due to float
drift.

Tuning knobs at the top of `lib/useAudio.ts`:
`MUSIC_TRACKS`, `INTRO_VOLUME`, `AMBIENT_VOLUME`,
`INTRO_FADE_IN_MS`, `CROSSFADE_MS`.

---

## 7. Diff-Driven Turn Chronicle

`lib/turnEvents.ts:diffTurnEvents({ prev, next, humanCivId })` returns a list
of `TurnEvent { id, kind, text, turn }`. Called from `ingestEvents` inside
every `run()` action wrapper in `page.tsx`. Events feed both:

- The **banner** above the map — top 4 events for 4.5s.
- The **Chronicle** at the bottom — keeps the last 80 events.

Kinds include city founding, completed research, lost units, met civilizations,
stance changes, and received messages. The full list lives in `turnEvents.ts`.

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
