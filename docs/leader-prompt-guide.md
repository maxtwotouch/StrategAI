# Leader Generation API — Client Prompt Guide

═══════════════════════════════════════════════════════════════════
  LEADER GENERATION API — PROMPT WRITING GUIDE
═══════════════════════════════════════════════════════════════════

A three-stage pipeline (splash → profile → action) with img2img
character consistency via reference images. Multi-leader action
scenes are also supported via a txt2img composite prompt path.

  POST /leader   → splash, profile, single-leader action, or multi-leader action


───────────────────────────────────────────────────────────────────
HOW IT WORKS
───────────────────────────────────────────────────────────────────

You pick enum values for archetype, culture, time_of_day, mood, and
(for action scenes) action_category.  The server maps each enum to
rich, hand-crafted prose and assembles a complete prompt behind the
scenes.  You never write raw prompts.

All style directives — cinematic quality tags, composition framing,
shot-type guidance (close-up portrait, wide composition, dynamic
action), and format constraints — live exclusively in the server's
``config/prompt_templates.json``.  The Python layer only assembles
enum prose + your free-form description between the template prefix
and suffix.  No prompt prose is hardcoded in Python.

You also provide free-form `leader_description` and (for action)
`action_description` fields for specifics the enums can't capture.

The splash establishes the canonical visual identity. Profile and
single-leader action use the splash as an img2img reference image to
preserve character consistency across all three stages.

For multi-leader action scenes, provide a `leader_ids` list instead
of a single `leader_id`. The server runs as txt2img with a composite
prompt weaving together all leaders' descriptions — no reference
image is used because multiple distinct faces must be depicted.

See [`architecture.md`](./architecture.md) for the full system architecture and
[`workflow-design-justification.md`](./workflow-design-justification.md) for Flux2 Klein design rationale.


═══════════════════════════════════════════════════════════════════
  ORDER OF OPERATIONS PER LEADER
═══════════════════════════════════════════════════════════════════

  1. SPLASH   (generates the canonical reference)
  2. PROFILE  (uses splash as img2img init — same face, close crop)
  3. ACTION   (uses splash as img2img init — new scene, same person)

Profile and Action calls require the leader_id from the Splash response.


═══════════════════════════════════════════════════════════════════
  LEADER DESCRIPTION (leader_description)
═══════════════════════════════════════════════════════════════════

Describe the person. Be specific about materials, not generic.

  INCLUDE:
    • Age, build, skin tone, hair style and color, eye color
    • One distinctive feature (scar, unusual jewelry, tattoo, unique weapon)
    • What they wear — exact materials and colors
    • Expression and bearing

  DO NOT INCLUDE:
    • Camera directions ("close-up", "wide shot")
    • Style words ("epic", "cinematic", "beautiful", "masterpiece")
    • Image quality words ("8K", "highly detailed", "sharp")
    • Setting or background description
    • Atmosphere or lighting words

  BAD (60 chars):
    "a cool warrior queen with awesome armor and epic fantasy vibes"

  GOOD (480 chars):
    "a tall warrior queen with bronze skin and sharp amber eyes, long
     black hair in tight braids bound with gold rings, wearing engraved
     bronze scale armor over a crimson linen tunic, a lion-pelt cape
     fastened at her left shoulder, holding a curved khopesh sword
     point-down, a healed slash scar across her right cheekbone,
     expression of calm authority earned through decades of battle"

  For profile and action calls, you can SHORTEN the description —
  retain the key identifying features (scar, braids, armor material).
  The face reference comes from the splash art via img2img.


═══════════════════════════════════════════════════════════════════
  ACTION DESCRIPTION (action_description)
═══════════════════════════════════════════════════════════════════

One moment. One action. Describe what the leader is doing right now.

  INCLUDE:
    • What the leader is physically doing
    • Who or what is around them
    • The emotional register — shown through expression or body language

  DO NOT INCLUDE:
    • Multi-step narratives ("first they planned, then built...")
    • Abstract descriptions ("they are strong and victorious")
    • Re-describing the leader's appearance (already in leader_description)

  BAD:
    "the queen fights a huge battle against many enemies and wins"

  GOOD:
    "standing on horseback at the crest of a hill, cavalry behind her
     silhouetted against sunset, watching enemy banners lowered in
     surrender, her bloodied sword resting across her saddle, expression
     of grim relief rather than celebration, smoke rising from the
     distant battlefield"


═══════════════════════════════════════════════════════════════════
  MULTI-LEADER ACTION SCENES
═══════════════════════════════════════════════════════════════════

To generate a scene with multiple leaders together, provide a
`leader_ids` list instead of a single `leader_id`:

```json
{
  "asset_type": "action",
  "leader_name": "Multi-Scene",
  "leader_description": "placeholder — ignored when leader_ids is provided",
  "leader_ids": ["LEADER_ID_1", "LEADER_ID_2"],
  "archetype": "diplomat",
  "culture": "medieval_european",
  "time_of_day": "midday",
  "mood": "contemplative",
  "action_category": "diplomatic",
  "action_description": "two leaders seated at opposite sides of a long oak table..."
}
```

The response includes all leader IDs and names:

```json
{
  "leader_ids": ["leader_cleopatra_vii_a1b2c3", "leader_ramesses_ii_d4e5f6"],
  "leader_names": ["Cleopatra VII", "Ramesses II"]
}
```

The engine weaves all leader descriptions from their splash records
into a single composite prompt. This runs as txt2img — no reference
image is used because ComfyUI can only accept one for img2img, but
multiple distinct faces must be depicted.


═══════════════════════════════════════════════════════════════════
  ENUM VALUES — PICK ONE FROM EACH CATEGORY
═══════════════════════════════════════════════════════════════════

ARCHETYPE          CULTURE                   TIME OF DAY
warrior_queen      ancient_egyptian          dawn
warrior_king       classical_greek           golden_hour
philosopher_king   roman_imperial            midday
merchant_prince    medieval_european         twilight
spiritual_leader   east_asian_imperial       night
diplomat           mesopotamian              storm
tyrant             mesoamerican
visionary          nordic_viking
                   persian
                   sub_saharan_african
                   south_asian
                   islamic_golden_age

MOOD               ACTION CATEGORY
triumphant         military
wise_serene        diplomatic
grim_determined    construction
mystical           scientific
melancholic        cultural
menacing           exploration
hopeful            crisis
contemplative


═══════════════════════════════════════════════════════════════════
  ERROR REFERENCE
═══════════════════════════════════════════════════════════════════

| Scenario | HTTP Code | Message |
|---|---|---|
| `leader_id` missing for profile | 400 | `"leader_id is required for profile assets"` |
| `leader_id` or `leader_ids` missing for action | 400 | `"leader_id or leader_ids is required when asset_type='action'"` |
| `leader_id` not found | 400 | `"Leader 'X' not found. Generate a splash first."` |
| `leader_ids` empty for multi-leader action | 400 | `"leader_ids must contain at least one leader_id for multi-leader action scenes."` |
| Any leader in `leader_ids` not found | 400 | `"Leader 'X' not found. Generate a splash first."` |
| `action_category` missing for action | 400 | `"action_category is required for action assets."` |
| `action_description` missing for action | 400 | `"action_description is required for action assets."` |
| `leader_description` < 50 chars | 422 | Pydantic validation |
| `leader_description` > 800 chars | 422 | Pydantic validation |
| `action_description` > 800 chars | 422 | Pydantic validation |
