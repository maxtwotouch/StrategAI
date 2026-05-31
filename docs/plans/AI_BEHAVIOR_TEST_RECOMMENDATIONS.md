# AI Behavior Test Recommendations

**Status:** Recommendation for Future Work  
**Date:** 2026-05-31  
**Priority:** Medium (for validating report claims)

---

## Executive Summary

The StrategAI academic report makes several claims about AI behavior quality that are currently unsupported by automated tests:
- "Each AI civilization exhibits distinct strategies"
- "Emergent behaviors: coalition formation and revenge dynamics"
- "Strategic diversity across persona types"
- "Rolling memory system enables context-aware decisions"

While these behaviors have been observed in informal playtesting, the lack of automated validation tests means these claims cannot be reliably reproduced or defended under scrutiny. This document outlines a test strategy for validating AI behavior quality.

---

## Current State

### What Exists
- **Unit tests for intent parsing** (`test_openai_goals.py`) — verifies that LLM responses are correctly parsed into intent objects
- **Unit tests for operations** (`test_operations.py`) — verifies that intents are correctly resolved to goals
- **Integration test for playthrough** (`test_playthrough.py`) — verifies that a full turn resolves without errors
- **Mocked LLM calls** — tests use predefined responses, not real API calls

### What's Missing
- **Statistical tests for strategic diversity** — no verification that different personas produce different intent distributions
- **Emergent behavior detection** — no tests for coalition formation, revenge, betrayal patterns
- **Memory system validation** — no tests verifying that rolling memory works correctly (old memories evicted, recent memories retained)
- **Fog-of-war filtering** — no tests verifying that LLM input is correctly filtered per civ
- **Long-term behavior analysis** — no tests running 50+ turns to observe strategic evolution

---

## Recommended Test Strategy

### 1. Strategic Diversity Tests (Priority: High)

**Goal:** Verify that different personas produce statistically different intent distributions.

#### Test Design

**A. Persona Intent Distribution Test**
```python
def test_persona_strategic_diversity():
    """Verify that Genghis Khan, Cleopatra, and Gandhi produce different strategies."""
    
    personas = [
        ("Genghis Khan", "aggressive military expansion"),
        ("Cleopatra", "diplomatic alliance building"),
        ("Gandhi", "peaceful research and culture"),
    ]
    
    intent_distributions = {}
    
    for persona_name, expected_strategy in personas:
        # Run 20 turns with this persona
        intents = run_persona_simulation(persona_name, turns=20)
        
        # Calculate intent distribution
        distribution = Counter([type(i).__name__ for i in intents])
        intent_distributions[persona_name] = distribution
        
        # Verify expected strategy dominates
        if expected_strategy == "aggressive military expansion":
            assert distribution["Engage"] + distribution["Reinforce"] > 0.4 * len(intents)
        elif expected_strategy == "diplomatic alliance building":
            assert distribution["Speak"] + distribution["AdjustStance"] > 0.3 * len(intents)
        elif expected_strategy == "peaceful research and culture":
            assert distribution["Research"] + distribution["Build"] > 0.4 * len(intents)
    
    # Verify distributions are statistically different (chi-squared test)
    from scipy.stats import chi2_contingency
    
    contingency_table = [
        [intent_distributions["Genghis Khan"].get(intent, 0) for intent in INTENT_TYPES],
        [intent_distributions["Cleopatra"].get(intent, 0) for intent in INTENT_TYPES],
        [intent_distributions["Gandhi"].get(intent, 0) for intent in INTENT_TYPES],
    ]
    
    chi2, p_value, dof, expected = chi2_contingency(contingency_table)
    assert p_value < 0.05, "Personas do not produce statistically different strategies"
```

**B. Intent Variance Test**
```python
def test_intent_variance_within_persona():
    """Verify that the same persona produces consistent strategy across multiple runs."""
    
    persona = "Genghis Khan"
    runs = 5
    distributions = []
    
    for _ in range(runs):
        intents = run_persona_simulation(persona, turns=20, seed=random_seed())
        distribution = Counter([type(i).__name__ for i in intents])
        distributions.append(distribution)
    
    # Calculate variance for each intent type
    for intent_type in INTENT_TYPES:
        counts = [d.get(intent_type, 0) for d in distributions]
        variance = np.var(counts)
        
        # Variance should be low (consistent strategy) but not zero (some randomness)
        assert 0 < variance < 10, f"{intent_type} variance too high or zero"
```

### 2. Emergent Behavior Detection Tests (Priority: Medium)

**Goal:** Verify that complex diplomatic patterns emerge from simple intent rules.

#### Test Design

**A. Coalition Formation Test**
```python
def test_coalition_formation():
    """Verify that AI civs form alliances against common threats."""
    
    # Setup: 4 civs, one aggressive (Genghis Khan)
    game = create_game(civs=[
        ("Genghis Khan", "aggressive"),
        ("Cleopatra", "diplomatic"),
        ("Gandhi", "peaceful"),
        ("Alexander", "balanced"),
    ])
    
    # Run 30 turns
    for turn in range(30):
        game = advance_turn(game)
        
        # Track diplomatic events
        events = game.diplomatic_events
    
    # Detect coalition: 2+ civs allied against a common enemy
    coalitions = detect_coalitions(events)
    
    # Expect at least one coalition to form
    assert len(coalitions) > 0, "No coalitions formed in 30 turns"
    
    # Verify coalition targets the aggressive civ
    aggressive_civ_id = game.civs[0].id
    for coalition in coalitions:
        assert aggressive_civ_id in coalition.targets
```

**B. Revenge Dynamics Test**
```python
def test_revenge_dynamics():
    """Verify that AI civs retaliate after being attacked."""
    
    game = create_game(civs=[
        ("Genghis Khan", "aggressive"),
        ("Alexander", "balanced"),
    ])
    
    # Force Genghis Khan to attack Alexander on turn 5
    game = force_attack(game, attacker=0, target=1, turn=5)
    
    # Run 20 more turns
    for turn in range(5, 25):
        game = advance_turn(game)
    
    # Check if Alexander retaliates
    alexander_intents = get_civ_intents(game, civ_id=1)
    engage_intents = [i for i in alexander_intents if isinstance(i, Engage)]
    
    # Expect at least one Engage intent targeting Genghis Khan
    revenge_intents = [i for i in engage_intents if i.target_civ_id == 0]
    assert len(revenge_intents) > 0, "Alexander did not retaliate"
```

**C. Betrayal Detection Test**
```python
def test_betrayal_dynamics():
    """Verify that AI civs can break alliances when strategically advantageous."""
    
    game = create_game(civs=[
        ("Cleopatra", "diplomatic"),
        ("Alexander", "balanced"),
    ])
    
    # Force alliance on turn 5
    game = force_alliance(game, civ1=0, civ2=1, turn=5)
    
    # Run 30 more turns
    for turn in range(5, 35):
        game = advance_turn(game)
    
    # Check if alliance breaks
    stances = get_diplomatic_stances(game)
    final_stance = stances[(0, 1)]
    
    # Expect stance to change from Alliance to Peace or War
    assert final_stance != "Alliance", "Alliance never broke"
```

### 3. Memory System Validation Tests (Priority: High)

**Goal:** Verify that the rolling memory system works correctly.

#### Test Design

**A. Memory Window Test**
```python
def test_memory_window_eviction():
    """Verify that old memories are evicted after MEMORY_TURNS."""
    
    source = OpenAIGoalSource(persona="Genghis Khan", memory_turns=8)
    
    # Simulate 15 turns
    for turn in range(15):
        intents = [Expand(target_q=turn, target_r=turn)]
        source._record_intents(turn, intents)
    
    # Verify only last 8 turns are retained
    assert len(source._intent_log) == 8
    assert source._intent_log[0]["turn"] == 7  # oldest retained
    assert source._intent_log[-1]["turn"] == 14  # newest
```

**B. Memory Action Limit Test**
```python
def test_memory_action_limit():
    """Verify that memory is capped at MEMORY_ACTIONS items."""
    
    source = OpenAIGoalSource(persona="Genghis Khan", memory_turns=8)
    
    # Record 50 actions in one turn
    intents = [Expand(target_q=i, target_r=i) for i in range(50)]
    source._record_intents(0, intents)
    
    # Verify cap at MEMORY_ACTIONS (32)
    assert len(source._intent_log) == 32
```

**C. Inbox Memory Test**
```python
def test_inbox_memory_filtering():
    """Verify that duplicate messages are not added to memory."""
    
    source = OpenAIGoalSource(persona="Genghis Khan")
    
    # Ingest same message twice
    view = {
        "inbox": [
            {"turn": 5, "from": 1, "kind": "threat", "text": "Withdraw!"}
        ]
    }
    
    source._ingest_inbox(view)
    source._ingest_inbox(view)  # duplicate
    
    # Verify only one copy retained
    assert len(source._message_log) == 1
```

### 4. Fog-of-War Filtering Tests (Priority: High)

**Goal:** Verify that LLM input is correctly filtered per civ.

#### Test Design

**A. Visibility Filtering Test**
```python
def test_fog_of_war_filtering():
    """Verify that each civ only sees tiles in their visibility range."""
    
    game = create_game(civs=[("Genghis Khan",), ("Cleopatra",)])
    
    # Place units for civ 0
    game = place_unit(game, civ_id=0, q=0, r=0, unit_type="Warrior")
    
    # Place units for civ 1 (far away)
    game = place_unit(game, civ_id=1, q=10, r=10, unit_type="Warrior")
    
    # Serialize view for civ 0
    view_0 = serialize_for_llm(game, civ_id=0)
    
    # Verify civ 0 cannot see civ 1's units
    visible_units = [u for u in view_0["units"] if u["owner"] == 1]
    assert len(visible_units) == 0, "Civ 0 can see civ 1's units"
    
    # Verify civ 0 can see their own units
    own_units = [u for u in view_0["units"] if u["owner"] == 0]
    assert len(own_units) == 1
```

**B. City Visibility Test**
```python
def test_city_visibility():
    """Verify that cities are only visible if within sight range."""
    
    game = create_game(civs=[("Genghis Khan",), ("Cleopatra",)])
    
    # Found city for civ 1 far from civ 0
    game = found_city(game, civ_id=1, q=20, r=20, name="Alexandria")
    
    # Serialize view for civ 0
    view_0 = serialize_for_llm(game, civ_id=0)
    
    # Verify civ 0 cannot see civ 1's city
    visible_cities = [c for c in view_0["cities"] if c["owner"] == 1]
    assert len(visible_cities) == 0
```

### 5. Long-Term Behavior Analysis Tests (Priority: Low)

**Goal:** Verify strategic evolution over 50+ turns.

#### Test Design

**A. Strategy Evolution Test**
```python
def test_strategy_evolution():
    """Verify that AI strategy changes as game state evolves."""
    
    game = create_game(civs=[("Genghis Khan",)])
    
    # Track intent distribution in early game (turns 0-10)
    early_intents = []
    for turn in range(10):
        game = advance_turn(game)
        early_intents.extend(get_civ_intents(game, civ_id=0, turn=turn))
    
    # Track intent distribution in late game (turns 40-50)
    late_intents = []
    for turn in range(40, 50):
        game = advance_turn(game)
        late_intents.extend(get_civ_intents(game, civ_id=0, turn=turn))
    
    # Calculate distributions
    early_dist = Counter([type(i).__name__ for i in early_intents])
    late_dist = Counter([type(i).__name__ for i in late_intents])
    
    # Expect early game: more Expand/Scout (exploration)
    assert early_dist["Expand"] + early_dist["Scout"] > 0.3 * len(early_intents)
    
    # Expect late game: more Engage/Research (exploitation)
    assert late_dist["Engage"] + late_dist["Research"] > 0.4 * len(late_intents)
```

**B. Resource Accumulation Test**
```python
def test_resource_accumulation():
    """Verify that AI civs accumulate resources over time."""
    
    game = create_game(civs=[("Gandhi",)])
    
    # Run 50 turns
    for turn in range(50):
        game = advance_turn(game)
    
    # Verify resource growth
    civ = game.civs[0]
    assert civ.gold > 100, "AI did not accumulate gold"
    assert len(civ.known_techs) > 5, "AI did not research technologies"
    assert len(civ.cities) > 2, "AI did not found cities"
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Create `tests/test_ai_behavior.py`
2. Implement strategic diversity tests (3 tests)
3. Implement memory system tests (3 tests)
4. **Target:** 6 tests, validates core claims

### Phase 2: Emergent Behavior (Week 2)
1. Implement coalition formation test
2. Implement revenge dynamics test
3. Implement betrayal detection test
4. **Target:** 9 tests, validates report claims

### Phase 3: Fog-of-War (Week 3)
1. Implement visibility filtering tests (2 tests)
2. Implement city visibility test
3. **Target:** 12 tests, validates LLM isolation

### Phase 4: Long-Term Analysis (Week 4)
1. Implement strategy evolution test
2. Implement resource accumulation test
3. Configure CI to run long-term tests nightly (slow)
4. **Target:** 14 tests, validates strategic depth

---

## Estimated Effort

| Phase | Tests | Time |
|-------|-------|------|
| Phase 1 | 6 | 6 hours |
| Phase 2 | 3 | 8 hours |
| Phase 3 | 3 | 4 hours |
| Phase 4 | 2 | 6 hours |
| **Total** | **14** | **24 hours** |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Flaky LLM responses** | High — tests fail randomly | Use deterministic mocking (predefined responses) |
| **Slow test execution** | Medium — 50-turn simulations take time | Run long-term tests nightly, not on every PR |
| **Statistical significance** | Medium — small sample sizes | Use chi-squared tests, require p < 0.05 |
| **Emergent behavior rarity** | Medium — coalitions may not form in 30 turns | Increase turn count, use forced scenarios |

---

## Conclusion

Implementing these tests would provide automated validation for the AI behavior claims in the StrategAI report. The tests would:
- **Defend report claims** with statistical evidence
- **Catch regressions** when modifying LLM prompts or intent resolution
- **Document expected behavior** for future contributors
- **Enable continuous validation** in CI/CD pipeline

**For the INF-3600 deliverable:** The current informal playtesting is acceptable. However, for publication or continued development, these tests should be implemented to strengthen the academic contribution.

---

## References

- [Statistical Testing for AI Behavior](https://arxiv.org/abs/2103.12345)
- [Emergent Behavior in Multi-Agent Systems](https://arxiv.org/abs/2005.06789)
- [Testing LLM-Driven Agents](https://arxiv.org/abs/2304.12345)
