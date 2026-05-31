# Benchmark Claim Origins

This document traces the origin of specific performance claims in the StrategAI codebase to determine whether they are substantiated by evidence or appear only in documentation.

**Methodology:**
- Searched entire codebase for each claim using grep
- Categorized occurrences by file type (source code vs documentation vs planning)
- Identified first canonical occurrence (excluding `docs/plans/` directory)
- Searched for supporting evidence (benchmark scripts, measurement code, test results)

---

## Claim 1: "~80% cache hit rate"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:693` — "Cache hit rate: ~80% for typical gameplay (repeated terrain/unit types)"
- `docs/IEEE_REPORT_COMPLETE.tex:417` — "Cache hit rate averages approximately 80% for typical gameplay with repeated terrain and unit types"

**File type:** Technical report (IEEE format)

**Supporting evidence:** 
- ❌ **None found**
- The assetserver implements an LRU cache in `assetserver/src/storage.py:43-44` with configurable `cache_max_entries` and `cache_max_mb`
- However, there is **no code that measures, logs, or reports cache hit rates**
- No benchmark scripts exist that calculate hit rates
- No test results or logs document this metric

**Other occurrences:**
- `docs/SEPARATION_OF_CONCERNS.md:382` — repeats the claim
- `docs/DEPLOYMENT.md:429` — repeats the claim
- `docs/PRESENTATION_OUTLINE.md:210` — repeats the claim
- `docs/plans/QUESTIONS_FOR_TEAM.md:16-17` — questions the claim

**Verdict:** ❌ **Unsubstantiated**
- The claim appears to be an estimate or assumption
- No measurement infrastructure exists to validate it
- First appears in technical reports without citation to source data

---

## Claim 2: "2.5-6 seconds generation time"

**First canonical occurrence:**
- `assetserver/docs/project-report.md:201` — "At 2.5–6 seconds per generation on a Blackwell RTX 6000 (3.5–7 seconds on an RTX 3090)"
- `docs/IEEE_REPORT.md:691` — "Generation time: 2.5-6 seconds per image (Blackwell RTX 6000, 14-16 GB VRAM with FP8)"

**File type:** Technical report (assetserver project report + IEEE report)

**Supporting evidence:**
- ✅ **Measurement infrastructure exists**
- `assetserver/src/unit/engine.py:114,176,250` — tracks `generation_time_ms` via `elapsed = int((time.time() - start) * 1000)`
- `assetserver/src/leader/engine.py:122,213,314,437,589,646` — same pattern
- `assetserver/src/tile/engine.py` — same pattern
- `assetserver/src/comfyui_client.py:311-314` — logs "Generation completed: prompt_id=%s filename=%s elapsed=%.1fs"
- `assetserver/scripts/validate_api.py:775,974` — measures `r.elapsed_ms` for API calls
- `assetserver/docs/project-report.md:980-986` — provides detailed latency breakdown

**However:**
- ❌ No aggregated benchmark results are stored in the repository
- ❌ No CSV/JSON files with timing data
- ❌ No benchmark scripts that run multiple generations and report statistics

**Other occurrences:**
- `docs/IEEE_REPORT_COMPLETE.tex:417,470` — repeats with GPU specifications
- `docs/IEEE_REPORT.tex:380` — earlier version claimed "1.2-4 seconds on RTX 5090" (inconsistent)
- `docs/PRESENTATION_OUTLINE.md:209` — repeats the claim

**Verdict:** ⚠️ **Partially substantiated**
- Measurement infrastructure exists and is actively used
- Individual generation times are logged but never aggregated
- The 2.5-6s range appears to be based on manual observation, not systematic benchmarking
- No published benchmark results to verify the specific range

---

## Claim 3: "<100ms API response"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:685` — "API response time: <50ms for state queries, <100ms for actions" (backend)
- `docs/IEEE_REPORT.md:692` — "API response time: <100ms for cached assets, 2-5 seconds for generation" (asset server)

**File type:** Technical report

**Supporting evidence:**
- ❌ **None found**
- No API latency benchmark scripts in `backend/` or `assetserver/`
- No response time logging middleware or aggregation
- No performance test results stored in repository
- `scripts/asset_api_smoke.py:70-84` measures individual request times but doesn't aggregate or report statistics

**Other occurrences:**
- `docs/IEEE_REPORT_COMPLETE.tex:415,417` — repeats both backend and asset server claims
- `docs/PRESENTATION_OUTLINE.md:209` — repeats asset server claim
- `.github/agents/oral-presentation.agent.md:64` — repeats claim
- `docs/plans/QUESTIONS_FOR_TEAM.md:23` — questions the claim

**Verdict:** ❌ **Unsubstantiated**
- No measurement infrastructure for API latency
- Claim appears to be an estimate or manual observation
- No benchmark results or logs to verify

---

## Claim 4: "60 FPS map rendering"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:698` — "Map rendering: 60 FPS for 1000-hex maps with SVG optimization"
- `docs/IEEE_REPORT_COMPLETE.tex:419` — "Map rendering maintains 60 FPS for 1000-hex maps with SVG optimization"

**File type:** Technical report

**Supporting evidence:**
- ❌ **None found**
- `frontend/components/SquareMap.tsx:370` uses `requestAnimationFrame` for panning
- `frontend/lib/useAudio.ts:46,56,61` uses `performance.now()` and `requestAnimationFrame` for audio visualization
- However, **no FPS measurement, profiling, or benchmarking code exists**
- No performance test results for map rendering
- No documentation of "SVG optimization" techniques

**Other occurrences:**
- `docs/IEEE_REPORT.tex:382` — repeats the claim
- `docs/plans/QUESTIONS_FOR_TEAM.md:35` — questions the claim
- `docs/plans/DOCUMENTATION_PERFECTION_PLAN.md:72` — notes "60 FPS rendering → cite profiling data or remove"

**Verdict:** ❌ **Unsubstantiated**
- No FPS measurement or profiling code
- No benchmark results for map rendering
- Claim appears to be an assumption or target, not a measurement

---

## Claim 5: "2-4s LLM decision time"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:686` — "LLM decision time: 2-4 seconds per AI civilization per turn"
- `docs/IEEE_REPORT_COMPLETE.tex:415` — "LLM decision time ranges from 2--4 seconds per AI civilization per turn, depending on the complexity of the game state and the number of visible entities"

**File type:** Technical report

**Supporting evidence:**
- ❌ **None found**
- `backend/app/engine/openai_goals.py` — implements LLM integration but **does not measure or log decision time**
- No timing instrumentation around OpenAI API calls
- No benchmark scripts for LLM latency
- No logs or results documenting decision times

**Other occurrences:**
- `docs/IEEE_REPORT.tex:378` — repeats the claim
- `docs/PRESENTATION_OUTLINE.md:68` — mentions "LLM decisions" but not timing
- `docs/plans/QUESTIONS_FOR_TEAM.md:28-29` — questions the claim

**Verdict:** ❌ **Unsubstantiated**
- No measurement infrastructure for LLM latency
- No timing code in the LLM integration layer
- Claim appears to be an estimate based on manual observation

---

## Claim 6: "$0.03 per AI turn"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:850` — "LLM cost: GPT-4 API calls incur per-token costs (~$0.03 per AI turn at current prompt sizes)"
- `docs/IEEE_REPORT_COMPLETE.tex:521` — "LLM cost is a consideration, with GPT-4 API calls incurring per-token costs of approximately $0.03 per AI turn at current prompt sizes"

**File type:** Technical report

**Supporting evidence:**
- ❌ **None found**
- No cost tracking code in `backend/`
- No token counting or API usage logging
- No billing data or cost calculations stored
- `docs/IEEE_REPORT.md:800` mentions "600,000–1,500,000 tokens processed" over 100 turns but provides no source

**Other occurrences:**
- `docs/IEEE_REPORT.tex:433` — repeats the claim
- `docs/PRESENTATION_OUTLINE.md:332` — repeats with "$9 per 100-turn game" calculation
- `.github/agents/oral-presentation.agent.md:104` — repeats the claim
- `docs/plans/QUESTIONS_FOR_TEAM.md:44-45` — questions the claim
- `docs/plans/DOCUMENTATION_PERFECTION_PLAN.md:71` — notes "$0.03/turn cost → cite API usage data or remove"

**Verdict:** ❌ **Unsubstantiated**
- No cost tracking or token counting infrastructure
- No API usage logs or billing data
- Claim appears to be a back-of-envelope calculation based on OpenAI pricing

---

## Claim 7: "886 tests"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:729` — "Total: 886 tests with ~80% aggregate coverage"
- `docs/IEEE_REPORT_COMPLETE.tex:431` — "Total test count across all components is 886 tests"

**File type:** Technical report

**Supporting evidence:**
- ⚠️ **Partially verified**
- `assetserver/docs/project-report.md:941` — "**Total tests**: 547 (verified via `pytest --collect-only -q`)"
- This is the **only claim that cites a verification methodology**
- The 886 number appears to be derived: 339 (backend) + 547 (assetserver) + 35 (dataset-gen-train) = 921, not 886
- `docs/plans/QUESTIONS_FOR_TEAM.md:105-113` notes discrepancies: different docs report 886, 932, and other numbers
- No automated test count verification script exists

**Other occurrences:**
- `docs/IEEE_REPORT_COMPLETE.tex:552` — repeats "886 tests, ~80% coverage"
- `docs/IEEE_REPORT.tex:394,464` — repeats the claim
- `docs/PRESENTATION_OUTLINE.md:211,230` — repeats with breakdown
- `docs/FIGURE_DESCRIPTIONS.md:309,317` — repeats
- `docs/PROJECT_COMPLETION_GUIDE.md:269,365` — repeats
- `.github/agents/oral-presentation.agent.md:65` — repeats

**Verdict:** ⚠️ **Partially substantiated**
- Assetserver count (547) is verified via `pytest --collect-only`
- Backend count (339+) is mentioned but not verified in documentation
- Total (886) appears to be arithmetic but doesn't match component sum
- No automated verification of total count

---

## Claim 8: "85% coverage"

**First canonical occurrence:**
- `docs/IEEE_REPORT.md:710` — "Coverage: ~85% of engine code" (backend)
- `docs/IEEE_REPORT_COMPLETE.tex:423` — "Coverage is approximately 85% of engine code"

**File type:** Technical report

**Supporting evidence:**
- ⚠️ **Tooling exists, but no published results**
- `backend/pyproject.toml:18` — includes `pytest-cov>=5.0` dependency
- `backend/pyproject.toml:31-35` — configures `[tool.coverage.run]` and `[tool.coverage.report]`
- `assetserver/pyproject.toml:27` — includes `pytest-cov>=4.0,<8.0`
- `assetserver/docs/project-report.md:943` — claims "~82%" coverage for assetserver
- However, **no coverage reports (HTML, XML, or text) are stored in the repository**
- No CI/CD pipeline results are documented
- No `.coverage` files or `htmlcov/` directories are committed

**Other occurrences:**
- `docs/IEEE_REPORT_COMPLETE.tex:425,427,429` — claims 82% (assetserver), 70% (frontend), 90% (training)
- `docs/IEEE_REPORT.tex:386,388,390,392` — repeats all coverage claims
- `docs/PRESENTATION_OUTLINE.md:211-212` — repeats "Backend: 315 tests, 85% coverage"
- `docs/PROJECT_COMPLETION_GUIDE.md:265` — repeats "Backend tests: 315 tests, 85% coverage"

**Verdict:** ⚠️ **Partially substantiated**
- Coverage measurement tools are configured and available
- No published coverage reports to verify specific percentages
- Claims appear to be based on local test runs that were not documented
- Assetserver claim (82%) is more specific but still unverified

---

## Summary

### Claims with canonical sources: **8/8**
All claims first appear in technical reports (`docs/IEEE_REPORT.md`, `docs/IEEE_REPORT_COMPLETE.tex`, or `assetserver/docs/project-report.md`).

### Claims only in planning docs: **0/8**
No claims appear *only* in `docs/plans/` — they all have canonical sources.

### Claims with supporting evidence: **2/8**
- ✅ **Generation time (2.5-6s)**: Measurement infrastructure exists and is actively used
- ⚠️ **Test count (886)**: Assetserver count (547) verified via `pytest --collect-only`

### Claims with NO supporting evidence: **6/8**
- ❌ Cache hit rate (~80%)
- ❌ API response time (<100ms)
- ❌ Map rendering (60 FPS)
- ❌ LLM decision time (2-4s)
- ❌ Cost per turn ($0.03)
- ❌ Coverage percentages (85%, 82%, 70%, 90%)

---

## Key Findings

1. **All claims originate in technical reports**, not in source code comments or docstrings. This suggests they were added during documentation writing, not during development.

2. **No benchmark scripts exist** in the repository. There are no scripts that systematically measure performance and generate reports.

3. **No performance test results are stored**. No CSV, JSON, or log files contain aggregated performance data.

4. **Measurement infrastructure is incomplete**:
   - Generation time is tracked per-request but never aggregated
   - Test counts can be verified via pytest but total is inconsistent
   - Coverage tools are configured but reports are not published
   - All other metrics have no measurement code at all

5. **The `docs/plans/QUESTIONS_FOR_TEAM.md` file questions 6 of 8 claims**, indicating the team recognized these were unsubstantiated.

6. **Inconsistencies exist between report versions**:
   - `IEEE_REPORT.tex` (earlier version) claimed "1.2-4 seconds on RTX 5090"
   - `IEEE_REPORT_COMPLETE.tex` (later version) claims "2.5-6 seconds on Blackwell RTX 6000"
   - Test counts vary: 886, 932, and component sums don't match

7. **Claims appear to be estimates or manual observations** that were never formally measured, documented, or verified.

---

## Recommendations

To substantiate these claims, the following evidence should be created:

1. **Benchmark scripts** that measure each metric systematically
2. **Performance test results** stored as CSV/JSON in `docs/benchmarks/`
3. **Coverage reports** generated and committed (or linked to CI/CD)
4. **Measurement logging** added to production code (cache hits, API latency, LLM timing)
5. **Verification methodology** documented for each claim
6. **Consistent numbers** across all documents (resolve 886 vs 932 discrepancy)

Without this evidence, all performance claims should be marked as "estimated" or "target" rather than stated as measurements.
