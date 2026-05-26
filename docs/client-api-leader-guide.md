# API Design: Civ-Style Asset Generation Service

## Thinking Protocol

**Goal**: Wrap the three-asset ComfyUI pipeline behind the simplest possible API. The client should describe *what* they want, not *how* to prompt-engineer it.

**Approach**: A split-design where structured parameters fill predictable slots, and a single natural-language field handles creative specificity. The API server holds all prompt templates, model configs, and style tails — the client provides only the differentiating information.

---

## 1. What Goes Where

### Static (Server-Side — Never Exposed to Client)

| Concern | Value | Rationale |
|---------|-------|-----------|
| Model | `flux1-dev.safetensors` | Fixed by your hardware choices |
| Resolution | 1920×1088 / 1024×1024 | Fixed by asset type |
| Steps, CFG, sampler | 8, 1.8, euler/beta | Tuned once, never changed |
| Style tail | `rich painterly oil style, by Craig Mullins and Greg Rutkowski, 8K` | Your visual brand |
| Negative prompt | Full block | Always identical |
| LoRA loading | Auto-loaded if leader has one | Server-side asset management |
| IPAdapter chain | Auto if no LoRA exists | Consistency fallback |
| Seed handling | Random, logged for reproducibility | Server-managed |
| Output format | PNG, filename convention | Fixed |

### Injected from Structured Params (Client Provides as Key-Value)

| Parameter | Type | Example | Injected Into |
|-----------|------|---------|---------------|
| `asset_type` | enum | `"splash"` `"profile"` `"action"` | Selects workflow + template |
| `archetype` | enum | `"warrior_queen"` | Pulls archetype-specific framing |
| `culture` | enum | `"ancient_egyptian"` | Injects architectural/clothing context |
| `time_of_day` | enum | `"golden_hour"` `"night"` `"dawn"` | Injects lighting |
| `mood` | enum | `"triumphant"` `"somber"` `"mystical"` `"tense"` | Injects emotional tone |
| `leader_name` | string | `"Cleopatra VII"` | Used in filenames + optional prompt injection |
| `action_category` | enum | `"military"` `"diplomatic"` `"construction"` `"scientific"` `"cultural"` | Selects action scene framing |
| `reference_leader_id` | string | `"leader_pharaoh_001"` | Pulls LoRA or reference face image |

### Natural Language (Client Provides as Free Text)

| Field | Max Chars | Where It Goes |
|-------|-----------|---------------|
| `leader_description` | 500 | The core subject: physical appearance, clothing, bearing |
| `action_description` | 500 | What specifically is happening (action scenes only) |

### Prompt Assembly Logic (Server-Side)

```
FINAL_PROMPT = TEMPLATE_PREFIX
             + leader_description
             + TEMPLATE_MIDDLE (injected from archetype + culture + time_of_day + mood)
             + action_description (if action scene)
             + TEMPLATE_SUFFIX (style tail, always identical)
```

The client never sees the full prompt. They provide the differentiating human detail; the server provides the structural framing that makes it work in Flux.

---

## 2. API Specification

### Single Endpoint

```
POST /generate
```

### Request Schema

```json
{
  "asset_type": "splash",
  "leader_name": "Amonheru the Eternal",
  "leader_description": "an aged Nubian pharaoh with dark skin, a grey-streaked beard, broad shoulders, wearing the double crown of unified Egypt, a white linen shendyt kilt with gold belt, broad collar of carnelian and turquoise, holding a long gold staff, a old battle scar across his left cheek, calm weathered wisdom in his eyes",
  "culture": "ancient_egyptian",
  "archetype": "philosopher_king",
  "time_of_day": "golden_hour",
  "mood": "wise_serene",
  "reference_leader_id": "leader_pharaoh_001",
  "action_category": null,
  "action_description": null
}
```

```json
{
  "asset_type": "action",
  "leader_name": "Amonheru the Eternal",
  "leader_description": "an aged Nubian pharaoh with dark skin, a grey-streaked beard, broad shoulders, wearing the double crown of unified Egypt",
  "culture": "ancient_egyptian",
  "archetype": "philosopher_king",
  "time_of_day": "golden_hour",
  "mood": "triumphant",
  "reference_leader_id": "leader_pharaoh_001",
  "action_category": "construction",
  "action_description": "standing before a newly completed grand library, scholars unrolling scrolls at his feet, laborers cheering from the scaffolding, a massive stone sundial being unveiled in the courtyard"
}
```

### Response Schema

```json
{
  "status": "completed",
  "asset_type": "splash",
  "leader_name": "Amonheru the Eternal",
  "image_url": "/output/splash_amonheru_the_eternal_20260114_143022.png",
  "seed": 84729104512,
  "generation_time_ms": 7200,
  "resolution": "1920x1088",
  "prompt_used": "epic cinematic wide composition of an aged Nubian pharaoh...",
  "leader_id": "leader_pharaoh_001"
}
```

---

## 3. Server-Side Enum Catalog

These are the structured values your API accepts. Each injects specific prompt fragments.

### `archetype` → injected framing

| Value | Injects |
|-------|---------|
| `warrior_queen` | `standing proudly, martial bearing, armor and weapons prominent` |
| `warrior_king` | `commanding presence, battle-scarred dignity, weapon in hand` |
| `philosopher_king` | `seated or standing in contemplation, scrolls or scientific instruments nearby` |
| `merchant_prince` | `calculating gaze, surrounded by symbols of wealth and trade` |
| `spiritual_leader` | `mystical aura, religious or natural symbols, ceremonial pose` |
| `diplomat` | `open posture, negotiating table or formal court setting` |
| `tyrant` | `imposing, shadows, iron grip on throne or weapon, intimidation` |
| `visionary` | `gazing toward horizon, plans or blueprints, forward-looking` |

### `culture` → injects architecture + material palette

| Value | Injects |
|-------|---------|
| `ancient_egyptian` | `sandstone, hieroglyphs, gold and lapis lazuli, palm columns, desert` |
| `classical_greek` | `marble, corinthian columns, olive groves, Aegean blue, white stone` |
| `roman_imperial` | `travertine, domes, eagles, crimson and gold, paved forums` |
| `medieval_european` | `stone castles, tapestries, oak, iron, stained glass, heraldry` |
| `east_asian_imperial` | `jade, red lacquer, cherry blossoms, silk, curved roofs, misty mountains` |
| `mesopotamian` | `mud brick ziggurats, lapis lazuli, bronze, reed marshes, river plains` |
| `mesoamerican` | `step pyramids, obsidian, jade, quetzal feathers, jungle, stone stelae` |
| `nordic_viking` | `timber longhouses, furs, iron, runestones, fjords, northern lights` |
| `persian` | `blue tile, gardens, cypress trees, gold, silk, mountain passes` |
| `sub_saharan_african` | `mud-brick mosques, gold, ivory, baobabs, savanna, woven textiles` |
| `south_asian` | `sandstone temples, silk saris, gold jewelry, lotus ponds, monsoon skies` |
| `islamic_golden_age` | `geometric tile, arabesques, domes, brass, parchment, desert observatories` |

### `time_of_day` → injects lighting

| Value | Injects |
|-------|---------|
| `dawn` | `first light of dawn, cool blue shadows giving way to warm gold, mist rising` |
| `golden_hour` | `low golden sunlight, long dramatic shadows, warm amber glow, dust motes` |
| `midday` | `harsh clear sunlight, strong contrast, bright blue sky, sharp shadows` |
| `twilight` | `purple and orange sky, torches being lit, transition between day and night` |
| `night` | `moonlight and firelight, deep shadows, stars visible through windows, warm torch glow` |
| `storm` | `dark brooding clouds, lightning illuminating the scene, wind-tossed elements` |

### `mood` → injects emotional tone

| Value | Injects |
|-------|---------|
| `triumphant` | `expression of hard-won victory, proud, celebratory atmosphere` |
| `wise_serene` | `expression of profound calm wisdom, peaceful dignified atmosphere` |
| `grim_determined` | `expression of steely resolve, tense charged atmosphere` |
| `mystical` | `expression of spiritual transcendence, ethereal otherworldly atmosphere` |
| `melancholic` | `expression of bittersweet reflection, quiet somber atmosphere` |
| `menacing` | `expression of cold calculated power, oppressive intimidating atmosphere` |
| `hopeful` | `expression of optimistic vision, bright aspirational atmosphere` |
| `contemplative` | `expression of deep thought, quiet introspective atmosphere` |

### `action_category` → injects scene framing

| Value | Injects |
|-------|---------|
| `military` | `dynamic composition, weapons drawn, battlefield context, smoke and banners` |
| `diplomatic` | `formal setting, treaty documents, handshake or exchange, multiple parties` |
| `construction` | `monument or building in progress, workers, scaffolding, sense of scale` |
| `scientific` | `instruments, scrolls, observatory or laboratory, discovery moment` |
| `cultural` | `ceremony, festival, artistic performance, ritual, audience watching` |
| `exploration` | `newly discovered land, map unfurled, scouts behind, vista of unknown territory` |
| `crisis` | `imminent threat, leader responding, tense faces, urgent body language` |

---

## 4. Server-Side Prompt Templates

These live in your API server, never sent to the client.

### Splash Template

```
epic cinematic wide composition of {leader_description}, {archetype_inject},
in a {culture_inject} setting, {time_of_day_inject}, {mood_inject},
civilization leader splash screen art, rich painterly oil style,
masterpiece composition, dramatic lighting, by Craig Mullins and Greg
Rutkowski, 8K, 16:9 cinematic aspect ratio, highly detailed
```

### Profile Template

```
professional close-up portrait of {leader_description}, face filling
the frame, {profile_headpiece_hint}, {mood_inject} expression,
civilization leader profile picture, sharp focus on eyes, Rembrandt
lighting, portrait lens 85mm f/1.4, very shallow depth of field, bokeh
background, highly detailed skin texture and pores, 8K, square format
```

### Action Template

```
epic cinematic scene depicting {leader_description} {action_description},
in a {culture_inject} setting, {time_of_day_inject}, {mood_inject},
{action_category_inject}, civilization game event art, rich painterly oil
style, dramatic composition, consistent character design, 8K, 16:9
cinematic aspect ratio, highly detailed
```

---

## 5. Server Architecture

```
┌──────────┐     POST /generate      ┌────────────────┐     /prompt     ┌────────────┐
│  Client  │ ────────────────────────▶│  FastAPI Server │ ──────────────▶│  ComfyUI   │
│  (Game)  │◀─────────────────────────│  (Port 8000)    │◀──────────────│  (Port 8188)│
└──────────┘     image URL / JSON     └────────────────┘   /history/{id} └────────────┘
                                              │
                                              │ On startup:
                                              │ 1. Load workflow JSONs
                                              │ 2. Build enum mappings
                                              │ 3. Queue LoRA registry
                                              │ 4. Connect to ComfyUI
                                              │
                                              ▼
                                      ┌────────────────┐
                                      │  Job Queue      │
                                      │  Async tasks    │
                                      │  Poll /history  │
                                      └────────────────┘
```

The FastAPI server is thin: it assembles the prompt, injects it into the pre-built workflow JSON, submits to ComfyUI's native `/prompt` endpoint, polls `/history/{prompt_id}`, and returns the result. ComfyUI's REST API is well-documented and production-capable [3][5].

The server runs on the **same machine** as the GPUs. ComfyUI starts with `--listen` to expose its API. The FastAPI wrapper runs alongside it — no network latency, no object storage needed for raw throughput.

---

## 6. Client Prompt Guide

This is what you give to the API consumer (game team, content team). They only need to understand two things: how to write `leader_description` and how to write `action_description`.

---

### Field: `leader_description`

**What it does:** This is the raw material. Describe the leader exactly as you envision them. The API wraps it in art direction that makes it work.

**Rules:**
1. **Physical description first, then clothing, then bearing.** The model weights physical words more heavily.
2. **Be specific about materials.** "gold filigree armor" beats "fancy armor."
3. **Include one distinctive, memorable feature.** A scar, an unusual eye color, a specific piece of jewelry, a unique hairstyle. This anchors the AI's attention and aids consistency across assets.
4. **No camera directions, no style words.** Don't say "cinematic lighting" or "8K" — the server adds those. Your words compete for attention in the prompt; spend them on what makes this leader unique.
5. **500 characters maximum.** If you need more, you're over-describing.

**Bad:**
```
a cool warrior queen with awesome armor and a sword, epic fantasy vibes, digital art
```

**Good:**
```
a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, wearing engraved bronze scale armor over a crimson linen tunic, a lion-pelt cape fastened at her left shoulder, holding a curved khopesh sword point-down, a healed slash scar across her right cheekbone, expression of calm authority earned through decades of battle
```

---

### Field: `action_description`

**What it does:** For action scenes only. Describes what is happening right now.

**Rules:**
1. **One action, one moment.** The AI paints a single frame. "Overseeing the completion of the great library" — not "first they planned the library, then built it over years."
2. **Include secondary characters if they tell the story.** "Laborers cheering from scaffolding" contextualizes the action.
3. **Hint at the emotional register.** Not "she is happy" — show it: "a restrained smile of satisfaction."
4. **No need to re-describe the leader.** The `leader_description` field already handles that. Mention only what's different for this scene (e.g., "now wearing battle armor").
5. **500 characters maximum.**

**Bad:**
```
the queen fights a huge battle against many enemies and wins gloriously, very epic, lots of action
```

**Good:**
```
standing on horseback at the crest of a hill, her cavalry behind her silhouetted against sunset, watching enemy banners being lowered in surrender on the plain below, her bloodied sword resting across her saddle, expression of grim relief rather than celebration, smoke rising from the distant battlefield
```

---

### Full Example: One Leader, Three API Calls

**Splash:**
```json
{
  "asset_type": "splash",
  "leader_name": "Ishtar of Akkad",
  "leader_description": "a regal Mesopotamian queen in her forties with olive skin, long black hair elaborately braided with lapis lazuli beads, kohl-lined dark eyes with an intense piercing gaze, wearing a fringed woolen shawl dyed in royal purple and gold over a pleated linen dress, a heavy gold headdress with bull-horn motifs, layered necklaces of carnelian and lapis, holding a cylinder seal in one hand and resting the other on a bronze sword hilt, expression of absolute unshakeable authority",
  "culture": "mesopotamian",
  "archetype": "warrior_queen",
  "time_of_day": "golden_hour",
  "mood": "triumphant",
  "reference_leader_id": null
}
```

**Profile:**
```json
{
  "asset_type": "profile",
  "leader_name": "Ishtar of Akkad",
  "leader_description": "a regal Mesopotamian queen in her forties with olive skin, long black hair elaborately braided with lapis lazuli beads, kohl-lined dark eyes with an intense piercing gaze, gold headdress with bull-horn motifs, layered necklaces of carnelian and lapis",
  "culture": "mesopotamian",
  "archetype": "warrior_queen",
  "time_of_day": "night",
  "mood": "grim_determined",
  "reference_leader_id": "leader_ishtar_001"
}
```

**Action:**
```json
{
  "asset_type": "action",
  "leader_name": "Ishtar of Akkad",
  "leader_description": "a regal Mesopotamian queen in her forties with olive skin, long black hair braided with lapis lazuli beads, kohl-lined dark eyes, wearing a bronze scale armor cuirass over her royal garments, gold headdress with bull-horn motifs",
  "culture": "mesopotamian",
  "archetype": "warrior_queen",
  "time_of_day": "twilight",
  "mood": "grim_determined",
  "reference_leader_id": "leader_ishtar_001",
  "action_category": "military",
  "action_description": "standing atop a mud-brick city wall at twilight, pointing her sword toward an approaching army on the plain below, archers lined along the battlements drawing their bows, torchlight flickering on her armor, expression of steely resolve as she commands the defense"
}
```

---

## 7. What the API Server Handles That the Client Never Touches

| Responsibility | Where |
|----------------|-------|
| Workflow JSON construction | Server builds the node graph per `asset_type` |
| Prompt assembly from template + params | Server concatenates, never exposed |
| Style tail appended to every prompt | `"...by Craig Mullins and Greg Rutkowski, 8K, 16:9"` |
| Negative prompt | Always the full block shown earlier |
| LoRA loading decision | If `reference_leader_id` has a trained LoRA, auto-load at 0.8 |
| IPAdapter fallback | If no LoRA exists, auto-chain FaceID + Style IPAdapter from stored reference crop |
| Seed generation | `random.randint(10**14, 10**15 - 1)`, logged in response |
| File naming | `{asset_type}_{leader_name_slug}_{timestamp}.png` |
| Reference face storage | Crop from first splash art, store by `leader_id` |

---

## 8. Prompt Guide Summary (Client-Facing Documentation)

You hand the client team a one-page document:

> ## Leader Art API — Prompt Writing Guide
>
> ### You provide two things:
>
> **1. `leader_description`** — Who is this person?
>
> Describe them as if to a portrait painter who has never met them:
> - Age, build, skin tone, hair, eyes, face
> - One distinctive feature (scar, tattoo, unusual jewelry)
> - What they wear — be specific about materials and colors
> - Their expression and bearing
>
> Do not include: camera directions, style words ("epic," "cinematic"), image quality words ("8K," "masterpiece"). We add those.
>
> **2. `action_description`** (action scenes only) — What is happening right now?
>
> Single moment, single action. Include:
> - What the leader is physically doing
> - Who or what is around them
> - How they feel about it (shown through expression/body language, not stated)
>
> D o not re-describe the leader unless something has changed for this scene.
>
> ### You pick from lists:
>
> `archetype`, `culture`, `time_of_day`, `mood`, `action_category`
>
> These are dropdowns. Pick the closest match. We inject the right art direction for each.
>
> ### Example result:
>
> *[Show the Ishtar splash/profile/action trio above as the canonical example]*

---

## 9. Why This Design

The split between structured params and natural language is deliberate:

**Structured params (`culture`, `time_of_day`, `mood`, `archetype`, `action_category`)** are concepts where:
- The exact wording matters for AI quality
- There's a fixed set of valid options
- Getting it "wrong" (e.g., contradictory lighting words) ruins the image
- The server can inject the optimal phrasing consistently

**Natural language (`leader_description`, `action_description`)** are concepts where:
- Creative specificity is the whole point
- Enum values could never capture the nuance
- The client's domain expertise (game design, character concept) exceeds any pre-built list

The boundary: **parameterize what has a discoverable correct answer; natural-language what requires creative judgment.**

The ComfyUI integration is straightforward — submit to `/prompt`, poll `/history/{id}`, return image [3][5]. The FastAPI server is a thin prompt-injection layer, not a heavy orchestration system. Most of the complexity lives in the prompt templates and enum mappings, which are plain dictionaries in the server code.