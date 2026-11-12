<p align="center">
  <img src="docs/assets/banner.svg" alt="Beyond Style UAE AI Jewellery Designer: exact Arabic text to 10 manufacturable 2D proofs and millimetre SVG/DXF workshop files" width="100%">
</p>

# Beyond Style UAE: AI Jewellery Designer

Turn a customer's exact Arabic or English name into ten different, manufacturable 2D jewellery proofs, then lock the approved version and hand the workshop dimensioned SVG, DXF and PDF files in millimetres.

<p align="center"><img src="docs/assets/hero.jpg" alt="Concept image (AI-generated). Not a product screenshot." width="100%"><br><sub><em>Concept image (AI-generated). Not a product screenshot.</em></sub></p>

![Next.js](https://img.shields.io/badge/Next.js-15.5-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![HarfBuzz](https://img.shields.io/badge/Shaping-HarfBuzz-8F7030)

## Overview

Beyond Style UAE sells personalised jewellery in the UAE. Most orders are a name or a short phrase in Arabic, often sent as a WhatsApp screenshot with "same design, change the writing". This platform handles that path end to end:

1. The customer types the text (or uploads a reference image and types the new text).
2. The backend normalises the text and shows it back, character by character, for explicit confirmation. OCR and AI never decide the customer's text.
3. Deterministic engines shape the text with HarfBuzz, generate 30 or more parametric candidates, run Arabic integrity and manufacturing checks, and rank them for diversity.
4. The customer sees ten genuinely different 2D proofs, picks one, and refines it with a designer.
5. Approval creates an immutable design version with a hash and timestamp. Any later edit invalidates it.
6. The workshop receives dimensioned vector exports in millimetres, each re-imported and compared against the master vector before it counts as workshop ready.

Raster or AI imagery is preview and decoration only. It is never manufacturing truth.

## Key features

- **Exact text truth.** Unicode NFC normalisation, BiDi and HarfBuzz shaping, hidden-character blocking and a per-cluster identity proof. A name such as ميثه is never silently changed to ميثة.
- **Reference flow.** Upload a screenshot or photo, classify the request (for example "same structure, new text"), with a copyright reminder. Vision output is never treated as the confirmed text.
- **Ten diverse proofs.** A composition engine builds candidates from the same glyph vectors (medallion, nameplate, arch, stacked, flow and more) and the ranking removes near duplicates.
- **Manufacturing gate.** Minimum stroke, gap and bridge checks, connectivity, attachment points and weight from real metal area. Auto repair proposes before and after changes and never touches the source text.
- **Designer Copilot and Pro mode.** Versioned vector edits (transforms, booleans, dot and swash variants, kashida, line breaks). Every edit creates a new immutable version.
- **Approval lock.** Hash-bound approval, plus a single-use secure customer link with retype-to-confirm.
- **Workshop exports.** SVG, DXF and PDF at true millimetre scale with an export fidelity check. PNG is a labelled preview raster only.
- **Style browser.** Every calligraphy style shows its real source, licence and availability. Styles without a rights-cleared source are shown as locked, never imitated.
- **Workshop OS and staff dashboard.** Order state machine, golden cases, readiness probes and font onboarding, all on real backend data.
- **Bilingual, mobile first.** Arabic RTL by default with an English toggle, tested at 360 to 1280 px, installable as a PWA.

## Screenshots

Captured from a local production build of the frontend running against the local FastAPI backend and PostgreSQL 16. The proofs are real engine output for the test name ميثه.

| Desktop (1440 x 900) | Mobile (390 x 844) |
|---|---|
| ![Start screen, desktop](docs/assets/screenshots/home-desktop.png) | ![Start screen, mobile](docs/assets/screenshots/home-mobile.png) |
| ![Exact text confirmation, desktop](docs/assets/screenshots/confirm-desktop.png) | ![Exact text confirmation, mobile](docs/assets/screenshots/confirm-mobile.png) |
| ![Ten proofs, desktop](docs/assets/screenshots/proofs-desktop.png) | ![Ten proofs, mobile](docs/assets/screenshots/proofs-mobile.png) |
| ![Style browser, desktop](docs/assets/screenshots/styles-desktop.png) | ![Style browser, mobile](docs/assets/screenshots/styles-mobile.png) |

## Quick start

Requirements: Node.js 22 (as in CI), Python 3.11, PostgreSQL 16.

```bash
# 1. Database
createdb beyondstyle            # default URL: postgresql+psycopg2://postgres:postgres@localhost:5432/beyondstyle

# 2. Backend (http://localhost:8000)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional; no AI keys are needed for the deterministic path
python -m alembic upgrade head
uvicorn app.main:app --port 8000

# 3. Frontend (http://localhost:3000)
cd ../frontend
npm ci
npm run dev                     # /api/* is proxied to BACKEND_URL (default http://localhost:8000)
```

The backend tests use a separate database named `beyondstyle_test`.

## Scripts

| Where | Command | What it does |
|---|---|---|
| `frontend/` | `npm run dev` | Next.js dev server on port 3000 |
| `frontend/` | `npm run build` | Production build (also type-checks) |
| `frontend/` | `npm start` | Serve the production build on port 3000 |
| `frontend/` | `npx tsc --noEmit` | Type check |
| `backend/` | `python -m pytest -q` | Full backend suite (needs PostgreSQL) |
| `backend/` | `python ../scripts/export_openapi.py --check` | Fail if `docs/api/openapi.json` drifted |
| repo root | `python e2e/golden_path_e2e.py` | Browser Golden Path E2E (backend on 8000, frontend on 3000) |
| repo root | `make check-pins` | Fail if the local Python env drifted from `backend/requirements.txt` |
| repo root | `make external-ai-e2e` | External AI acceptance; reports `SKIPPED_NO_CREDENTIALS` honestly |

## Project structure

```
backend/          FastAPI app, engines, exporters, Alembic migrations, pytest suite
  app/engines/    arabic_engine, text_integrity, composition_engine, validator, ranking, vector_edit
  app/exporters/  svg, dxf, pdf, png (preview), fidelity
frontend/         Next.js 15 app router, React design system in components/ui
  app/            customer Golden Path, /styles, /me, /approve/[token], /admin
e2e/              Playwright browser flows and evidence generators
services/hermes/  optional isolated orchestration runtime (never a hard dependency)
docs/             architecture, ADRs, deployment, readiness, evidence
```

## Architecture

```mermaid
flowchart LR
  B[Browser<br/>Next.js on Vercel] -- HTTPS + CORS --> A[FastAPI backend<br/>Replit]
  A --> T[Text integrity<br/>NFC, BiDi, HarfBuzz]
  T --> C[Composition engine<br/>30+ candidates]
  C --> V[Manufacturing validator<br/>and ranking]
  V --> P[10 diverse proofs]
  P --> L[Approval lock<br/>version + hash]
  L --> X[SVG / DXF / PDF in mm<br/>fidelity check]
  A <--> D[(PostgreSQL)]
```

One versioned `JewelleryDesignSchema` is shared across services. The immutable source text is stored separately from the editable visual geometry. Deterministic rules override AI for text truth, licensing, pricing math, manufacturing limits and security. See [`docs/architecture.md`](docs/architecture.md) and [`docs/adr/`](docs/adr/).

## Deploy on Vercel

The frontend deploys to Vercel. The backend and database run on Replit (see [`replit.md`](replit.md)).

| Setting | Value |
|---|---|
| Framework preset | Next.js |
| Root directory | `frontend` |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output | Next.js default (`.next`) |
| `NEXT_PUBLIC_API_URL` | Optional. Backend origin. Vercel builds default to the published Replit backend set in `next.config.mjs`. |
| `NEXT_PUBLIC_APP_ENV` | Optional. `production` in `frontend/.env.example`. |

The build needs no secrets. Never put an API key in a `NEXT_PUBLIC_*` variable: those values are bundled into browser JavaScript. The app has no Next.js API routes. The backend's `ALLOWED_ORIGINS` must include the Vercel origin. Full details: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Status and known limitations

The honest, evidence-based readiness picture is kept in [`docs/production-readiness.md`](docs/production-readiness.md) and [`docs/STATUS.md`](docs/STATUS.md). Highlights:

- Workshop rule values are industry-typical and **not yet calibrated** against Beyond Style's own cuts. A calibration kit exists.
- Thuluth, Diwani and Nastaliq are "inspired only" until a licensed source is uploaded.
- No SMS or e-mail provider is wired for login codes outside development.
- The secure approval link has no OTP check on the link holder.
- Node and pen-tool vector editing is not built and is shown as unavailable in the UI.
- External AI providers (Claude, GPT-Image-2) are optional and unverified without credentials. The deterministic path does not depend on them.
- The Replit backend deployment has been intermittently unreachable. The production monitor workflow reports this.

<div dir="rtl" lang="ar">

## ملخص بالعربية

منصة «بيوند ستايل الإمارات» لتصميم المجوهرات تحوّل الاسم أو العبارة التي يكتبها العميل، بالعربية أو الإنجليزية، إلى عشرة تصاميم ثنائية الأبعاد مختلفة وقابلة للتصنيع. يُعرض النص على العميل حرفًا بحرف ليؤكده صراحةً، ولا يغيّر الذكاء الاصطناعي أو التعرّف الضوئي على الحروف الإملاءَ أبدًا. تعتمد المنصة على محركات حتمية لتشكيل النص العربي وفحص سلامة التصنيع، وعند اعتماد العميل تُقفل نسخة التصميم ببصمة رقمية وتاريخ، ثم تُسلَّم للورشة ملفات SVG وDXF وPDF بمقاسات دقيقة بالمليمتر. الصور المولّدة للعرض فقط وليست مرجعًا للتصنيع.

</div>

## License and ownership

Copyright Beyond Style UAE, Dubai. All rights reserved. No open-source licence is granted for this repository. Bundled fonts keep their own licences (SIL OFL 1.1; see `frontend/app/fonts/` and [`docs/FONT_LICENSING.md`](docs/FONT_LICENSING.md)).
