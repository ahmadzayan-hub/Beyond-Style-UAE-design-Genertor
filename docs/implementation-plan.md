# P0 Golden Path — Audit & Implementation Plan

Audit date: 2026-08-24 · Branch: `claude/p0-golden-path-audit-jtyduw`

## Audit result

**Existing:** Nothing. Remote repo had zero commits/branches. No frontend, backend, DB, CI, fonts, tests, or docs. This commit seeds `CLAUDE.md` + spec docs only.

**Reusable:** Only the governance docs (CLAUDE.md, master spec, low-token guide). No code to preserve; no conflicts with spec — greenfield.

**Gaps (all of P0):**
- Arabic Engine (normalization/BiDi/HarfBuzz shaping/identity verification)
- Canonical `JewelleryDesignSchema` / Design Graph
- Font manager + legally verified Arabic fonts (none acquired yet)
- Design Intelligence archetypes (0 of 150+)
- Parametric generator, constraint solver, auto-repair, diversity ranking
- SVG/DXF mm export, approval/version-lock, workshop handoff
- Customer UI (mobile-first, RTL), anonymous sessions
- Infra: Postgres+pgvector, Redis, S3, Docker, CI, test harness

**Risks:**
1. Font licensing is the first hard gate — no shaping without verified OFL/licensed Arabic fonts (candidates: Amiri, Reem Kufi, Aref Ruqaa, Cairo — verify OFL before commit). UNKNOWN_RIGHTS blocks commercial use.
2. Glyph-outline → jewellery vector geometry (Booleans, connectivity, stroke/gap analysis) is the highest-complexity core; must be deterministic, not AI.
3. Achieving genuinely diverse 30→10 candidates deterministically (AI optional/flagged) needs a real archetype library early.
4. uharfbuzz/FreeType native deps must be pinned in Docker from day one.
5. Repo name typo "Genertor" — cosmetic; do not rename without owner.
6. DXF validity for workshops needs `ezdxf` + real-unit (mm) verification tests, not visual inspection.

## First vertical slice — max 12 files

Smallest complete loop: text → confirm → ≥30 candidates → QA → 10 proofs → select → approve/lock → SVG/DXF.

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/main.py` | FastAPI app, routers, CORS, health |
| 2 | `backend/app/schemas/jewellery_design.py` | Versioned JewelleryDesignSchema; immutableSourceText ≠ editableVisualGeometry; Design Graph nodes |
| 3 | `backend/app/engines/arabic_engine.py` | NFC normalization, BiDi, uharfbuzz shaping, deterministic identity verify → BLOCK_PRODUCTION_EXPORT |
| 4 | `backend/app/engines/geometry_engine.py` | Glyph outlines → vector paths (mm); stroke/gap/connectivity constraint checks; basic auto-repair (bridge/thicken) |
| 5 | `backend/app/engines/candidate_generator.py` | Parametric composition from archetypes; ≥30 internal; QA pipeline; diversity rank → top 10 |
| 6 | `backend/app/api/designs.py` | Endpoints: brief, confirm-text, generate, select, refine, approve (hash lock), export SVG/DXF |
| 7 | `backend/app/data/archetypes_seed.json` | First ~20 structured archetypes + rights metadata (grow to 150+) |
| 8 | `backend/tests/test_golden_path.py` | Golden fixtures (ميثة, hamza, taa marbuta, alif maqsura, lam-alif, mixed AR/EN); identity, diversity, export validity |
| 9 | `frontend/app/design/page.tsx` | Mobile-first customer flow: text → style intent → 10 proofs → select → spelling confirm → approve → download |
| 10 | `frontend/lib/api.ts` | Typed API client mirroring schema |
| 11 | `frontend/components/ProofCard.tsx` | RTL-correct proof card: SVG preview, style, score, actions |
| 12 | `docker-compose.yml` | postgres+pgvector, redis, backend, frontend |

Notes: persistence models start inside file 2 (SQLAlchemy + Pydantic co-located) to hold the 12-file cap; fonts vendored under `backend/assets/fonts/` (binary, outside cap) only after license verification; `docs/production-readiness.md` updated with evidence per slice.

## Next action
Implement slice files 1–8 (backend loop + tests) before any UI, per priority "text correctness first".
