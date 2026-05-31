# Frontend Test Recommendations

**Status:** Recommendation for Future Work  
**Date:** 2026-05-31  
**Priority:** High (for production deployment)

---

## Executive Summary

The StrategAI frontend currently has **zero test coverage**. While the application functions correctly and TypeScript strict mode catches type errors at build time, the lack of runtime tests creates significant risk for production deployment. This document outlines a comprehensive testing strategy that should be implemented before the project moves beyond the academic deliverable phase.

---

## Current State

### What Exists
- **TypeScript strict mode** (`tsconfig.json` with `"strict": true`) — catches type errors at compile time
- **Manual testing** — developers run the game and verify functionality
- **No automated tests** — no Jest, Vitest, React Testing Library, Playwright, or Cypress

### What's Missing
- Unit tests for utility functions (hex math, API client, asset resolution)
- Component tests for React components (map rendering, diplomacy panel, AI intent log)
- Integration tests for API interactions (game creation, turn resolution, asset fetching)
- End-to-end tests for user workflows (game setup, turn advancement, diplomacy)
- Visual regression tests for UI changes
- Accessibility tests (keyboard navigation, screen reader compatibility)

---

## Recommended Test Strategy

### 1. Unit Tests (Priority: High)

**Framework:** Vitest + React Testing Library  
**Target Coverage:** 70-80% of utility functions

#### Test Categories

**A. Hex Math Utilities (`lib/hex.ts`)**
- `hexToPixel()` — coordinate conversion accuracy
- `pixelToHex()` — inverse conversion
- `hexDistance()` — distance calculation
- `hexNeighbors()` — neighbor enumeration
- `hexRing()` — ring generation
- Edge cases: negative coordinates, large grids, boundary conditions

**B. API Client (`lib/api.ts`)**
- `createGame()` — request formatting, response parsing
- `advanceTurn()` — error handling (404, 500, network failures)
- `submitAction()` — all action types (move, attack, found, research, build)
- `getAILog()` — graceful degradation when endpoint unavailable
- Mock fetch responses, verify request shapes

**C. Asset Resolution (`lib/assetManifest.ts`, `lib/assetApi.ts`)**
- `loadManifest()` — manifest parsing, fallback behavior
- `resolveAsset()` — asset lookup, missing asset handling
- `generateAsset()` — POST request formatting, error recovery
- Test with incomplete manifests, missing asset types, network failures

**D. Turn Event Processing (`lib/turnEvents.ts`)**
- `diffGameStates()` — event detection (combat, founding, research, diplomacy)
- Event formatting and summarization
- Edge cases: multiple events per turn, no events, malformed state

**E. Audio System (`lib/useAudio.ts`)**
- Music crossfade logic
- TTS narration triggering
- Volume control and muting

#### Example Test Structure

```typescript
// tests/lib/hex.test.ts
import { describe, it, expect } from 'vitest';
import { hexToPixel, pixelToHex, hexDistance } from '@/lib/hex';

describe('hex utilities', () => {
  describe('hexToPixel', () => {
    it('converts origin hex to pixel coordinates', () => {
      const { x, y } = hexToPixel(0, 0, 32);
      expect(x).toBe(0);
      expect(y).toBe(0);
    });

    it('converts positive hex coordinates', () => {
      const { x, y } = hexToPixel(2, 3, 32);
      expect(x).toBeCloseTo(110.85, 2);
      expect(y).toBeCloseTo(96, 2);
    });

    it('handles negative coordinates', () => {
      const { x, y } = hexToPixel(-1, -1, 32);
      expect(x).toBeCloseTo(-55.42, 2);
      expect(y).toBeCloseTo(-48, 2);
    });
  });

  describe('hexDistance', () => {
    it('calculates distance between adjacent hexes', () => {
      expect(hexDistance(0, 0, 1, 0)).toBe(1);
      expect(hexDistance(0, 0, 0, 1)).toBe(1);
    });

    it('calculates distance to self as zero', () => {
      expect(hexDistance(5, 5, 5, 5)).toBe(0);
    });

    it('calculates distance across multiple hexes', () => {
      expect(hexDistance(0, 0, 3, 3)).toBe(3);
    });
  });
});
```

### 2. Component Tests (Priority: Medium)

**Framework:** React Testing Library  
**Target Coverage:** Critical UI components

#### Test Categories

**A. Map Rendering (`components/SquareMap.tsx`)**
- Renders correct number of hex tiles for given map size
- Applies terrain colors correctly (grassland, forest, mountain, water)
- Displays unit glyphs and structure icons
- Handles fog of war (hidden vs visible tiles)
- Camera panning and zooming (user interactions)

**B. Diplomacy Panel**
- Renders message history in correct order
- Displays relationship scores with color coding
- Shows stance pills (Peace/War/Alliance)
- Handles message submission (input validation, API call)
- AI-generated message badges render correctly

**C. AI Intent Log Panel**
- Fetches AI log on mount
- Displays last 10 decisions with correct formatting
- Color-codes intents by type (military, diplomatic, economic)
- Shows "new decisions" badge when updates arrive
- Handles empty state gracefully (no decisions yet)
- Handles API failure gracefully (endpoint unavailable)

**D. Game Setup Screen**
- Renders civilization selection
- Validates player name input
- Handles game creation (API call, loading state, error handling)
- Transitions to game view on success

**E. Turn Controls**
- "End Turn" button triggers turn advancement
- Shows loading state during turn resolution
- Displays turn chronicle (banner events)
- Handles turn resolution errors

#### Example Test Structure

```typescript
// tests/components/AIIntentLog.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AIIntentLog from '@/components/AIIntentLog';
import { getAILog } from '@/lib/api';

vi.mock('@/lib/api');

describe('AIIntentLog', () => {
  it('renders loading state initially', () => {
    vi.mocked(getAILog).mockResolvedValue({ decisions: [] });
    render(<AIIntentLog gameId="1" />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays AI decisions when loaded', async () => {
    vi.mocked(getAILog).mockResolvedValue({
      decisions: [
        {
          civ_id: 1,
          civ_name: 'Mongol Empire',
          turn: 5,
          intent: 'engage',
          args: { target_civ_id: 3 },
          timestamp: '2026-05-31T10:23:45Z',
          reasoning: null,
        },
      ],
    });

    render(<AIIntentLog gameId="1" />);

    await waitFor(() => {
      expect(screen.getByText('Mongol Empire')).toBeInTheDocument();
      expect(screen.getByText(/engage/i)).toBeInTheDocument();
    });
  });

  it('handles API failure gracefully', async () => {
    vi.mocked(getAILog).mockRejectedValue(new Error('Network error'));
    render(<AIIntentLog gameId="1" />);

    await waitFor(() => {
      expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
    });
  });
});
```

### 3. Integration Tests (Priority: Medium)

**Framework:** Vitest + MSW (Mock Service Worker)  
**Target Coverage:** Critical user workflows

#### Test Scenarios

**A. Game Creation Flow**
1. User fills out setup form
2. Frontend sends POST to `/games`
3. Backend returns game state
4. Frontend transitions to game view
5. Asset manifest loads
6. Map renders with initial state

**B. Turn Advancement Flow**
1. User clicks "End Turn"
2. Frontend sends POST to `/games/{id}/turn/resolve`
3. Backend resolves AI turns, returns new state
4. Frontend updates map, displays turn chronicle
5. AI intent log refreshes with new decisions

**C. Unit Movement Flow**
1. User selects unit on map
2. User clicks destination hex
3. Frontend sends POST to `/games/{id}/actions/move`
4. Backend validates move, returns updated state
5. Frontend updates unit position on map

**D. Diplomacy Flow**
1. User opens diplomacy panel
2. User composes message
3. Frontend sends POST to `/games/{id}/diplomacy/messages`
4. Backend processes message, updates relationship
5. Frontend displays message in history, updates relationship score

#### Example Test Structure

```typescript
// tests/integration/game-creation.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import App from '@/app/page';

const server = setupServer(
  http.post('/games', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: 1,
      turn: 0,
      current_civ_id: 1,
      civs: [/* mock data */],
      map: {/* mock data */},
    });
  }),
);

beforeAll(() => server.listen());
afterAll(() => server.close());

describe('game creation flow', () => {
  it('creates a new game and transitions to game view', async () => {
    render(<App />);

    // Fill out setup form
    fireEvent.change(screen.getByLabelText(/player name/i), {
      target: { value: 'Test Player' },
    });
    fireEvent.click(screen.getByText(/start game/i));

    // Wait for game view
    await waitFor(() => {
      expect(screen.getByText(/turn 0/i)).toBeInTheDocument();
    });

    // Verify map rendered
    expect(screen.getByRole('img', { name: /game map/i })).toBeInTheDocument();
  });
});
```

### 4. End-to-End Tests (Priority: Low)

**Framework:** Playwright  
**Target Coverage:** Critical user journeys

#### Test Scenarios

**A. Complete Game Session**
1. Launch application
2. Create new game with custom settings
3. Play 5 turns (move units, found city, research tech)
4. Engage in diplomacy with AI civ
5. Verify game state persistence (refresh page, state restored)

**B. Asset Generation**
1. Start game with asset server enabled
2. Verify leader portraits load
3. Verify structure art generates on city founding
4. Verify graceful degradation when asset server unavailable

**C. AI Behavior Observation**
1. Create game with 4 AI civs
2. Advance 10 turns
3. Verify AI intent log shows diverse strategies
4. Verify diplomatic messages appear
5. Verify relationship scores change over time

#### Example Test Structure

```typescript
// tests/e2e/game-session.spec.ts
import { test, expect } from '@playwright/test';

test('complete game session', async ({ page }) => {
  await page.goto('http://localhost:3000');

  // Create game
  await page.fill('[data-testid="player-name"]', 'Test Player');
  await page.click('[data-testid="start-game"]');

  // Wait for game view
  await expect(page.locator('[data-testid="turn-indicator"]')).toContainText('Turn 0');

  // Play 5 turns
  for (let i = 0; i < 5; i++) {
    await page.click('[data-testid="end-turn"]');
    await expect(page.locator('[data-testid="turn-indicator"]')).toContainText(`Turn ${i + 1}`);
  }

  // Verify AI intent log has entries
  const logEntries = page.locator('[data-testid="ai-log-entry"]');
  await expect(logEntries).toHaveCount(await logEntries.count());
  expect(await logEntries.count()).toBeGreaterThan(0);
});
```

### 5. Visual Regression Tests (Priority: Low)

**Framework:** Playwright + Percy or Chromatic  
**Target Coverage:** Critical UI states

#### Test Scenarios

- Game setup screen (initial state)
- Map view with different terrain types
- Diplomacy panel with message history
- AI intent log with various decision types
- City drawer with production queue
- Sovereign overlay with leader portrait

### 6. Accessibility Tests (Priority: Medium)

**Framework:** jest-axe or Playwright accessibility checks  
**Target Coverage:** All interactive components

#### Test Categories

- Keyboard navigation (Tab, Enter, Escape)
- Screen reader compatibility (ARIA labels, roles)
- Color contrast (WCAG AA compliance)
- Focus management (modals, drawers)
- Form validation (error messages, required fields)

---

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Install Vitest, React Testing Library, MSW
2. Configure test environment (jsdom, setup files)
3. Write unit tests for `lib/hex.ts` (10 tests)
4. Write unit tests for `lib/api.ts` (15 tests)
5. **Target:** 25 tests, 30% coverage

### Phase 2: Component Tests (Week 2)
1. Write component tests for `SquareMap` (10 tests)
2. Write component tests for diplomacy panel (10 tests)
3. Write component tests for AI intent log (8 tests)
4. **Target:** 53 tests, 50% coverage

### Phase 3: Integration Tests (Week 3)
1. Write integration tests for game creation (3 tests)
2. Write integration tests for turn advancement (3 tests)
3. Write integration tests for unit movement (3 tests)
4. **Target:** 62 tests, 60% coverage

### Phase 4: Polish (Week 4)
1. Write accessibility tests for all interactive components
2. Add visual regression tests for critical UI states
3. Configure CI/CD to run tests on every PR
4. **Target:** 80+ tests, 70% coverage

---

## Estimated Effort

| Phase | Tests | Coverage | Time |
|-------|-------|----------|------|
| Phase 1 | 25 | 30% | 8 hours |
| Phase 2 | 28 | 50% | 12 hours |
| Phase 3 | 9 | 60% | 6 hours |
| Phase 4 | 18+ | 70% | 10 hours |
| **Total** | **80+** | **70%** | **36 hours** |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Flaky tests** | High — undermines confidence | Use deterministic mocks, avoid timing-dependent assertions |
| **Slow test suite** | Medium — slows development | Run unit tests on every save, integration tests on PR |
| **Maintenance burden** | Medium — tests break on refactor | Write tests against behavior, not implementation details |
| **False confidence** | Medium — tests pass but bugs exist | Combine automated tests with manual smoke testing |

---

## Conclusion

Implementing this test strategy would significantly improve the reliability and maintainability of the StrategAI frontend. The phased approach allows incremental adoption, starting with high-value unit tests and expanding to integration and e2e tests as the project matures.

**For the INF-3600 deliverable:** The current state (TypeScript strict mode + manual testing) is acceptable for an academic project. However, for production deployment or continued development, this test strategy should be implemented as a priority.

---

## References

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Mock Service Worker](https://mswjs.io/)
- [Playwright](https://playwright.dev/)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
