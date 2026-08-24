# Beyond Style UAE AI Jewellery Designer V2 — Master Product Specification

> Detailed reference. Claude should read only the section needed for the active task. Root `CLAUDE.md` contains always-on rules.

## Mission
Build a production-grade Arabic/English personalized jewellery platform converting customer text, names, prompts, sketches, photos, WhatsApp/Instagram references and existing designs into editable, manufacturable products.

System roles:
- AI Jewellery Designer
- Reference-Based Custom Design Engine
- Customer Service & Sales Engine
- Designer Copilot
- Workshop Manufacturing OS
- Market/Trend Intelligence
- Continuous Jewellery Intelligence System

Core loop:
`Intent/Reference → Brief → Knowledge Retrieval → ≥30 2D Candidates → QA → Auto Repair → Diverse Top 10 → Select/Edit → Final 2D → Approval/Lock → 3D → Price/Order → Workshop → QC → Delivery → Actual Results → Evaluation/Learning`

## Architecture
Next.js/React/TypeScript/Tailwind; FastAPI/Python; PostgreSQL+pgvector; Redis; S3-compatible storage; HarfBuzz + OpenType/FreeType; SVG/vector geometry; Three.js/WebGL; CadQuery/OpenCascade; Docker/CI-CD.

Use feature-based/Common Closure architecture, versioned schemas/contracts and migrations.

## Canonical Design Schema
Use one versioned `JewelleryDesignSchema`.
Design Graph:
`SourceText → Characters → Glyphs → Dots/Harakat → Connectors → Composition → Components → Vector Geometry → Manufacturing Geometry → CAD → ProductionVersion`
Assembly Graph:
`Components → Connectors/Joints → AttachmentPoints → Materials → ManufacturingMethod → AssemblyOrder`
Never use raster/flattened SVG as sole truth. Keep immutable source text separate from editable geometry.

## Arabic/Text Engine
Deterministic P0 truth:
Unicode normalization, BiDi, HarfBuzz/OpenType shaping, ligatures, contextual forms, mark positioning.
Support Arabic, English, mixed text, numbers, Harakat, long text, multi-name.
AI cannot silently change spelling/order/dots/Hamza/Taa Marbuta/Alif Maqsura/Harakat.
Verification failure blocks production.
Transliteration requires explicit confirmation.
Sacred/religious text: enhanced verification; no rewriting/paraphrasing; explicit approval.

## Font/Glyph/Lettering Intelligence
Plugin font manager: TTF/OTF/WOFF/WOFF2/variable fonts.
Track source, license, commercial rights, script, coverage, Harakat, ligatures, axes, readability, manufacturability.
Rights: VERIFIED_OPEN_SOURCE / COMMERCIAL_LICENSED / CUSTOMER_OWNED / INTERNAL_ONLY / UNKNOWN_RIGHTS.
Unknown rights cannot enter commercial production.
Support classical + modern Arabic and Latin script/cursive/signature families.
Build Font Wall + Glyph Variant Library for positions, ligatures, tails, swashes, dots and validated designer edits.

## Design Intelligence Library
Build ≥150 structured, expandable archetypes, not copied artwork.
Cover classical calligraphy, Kufi variants, circular/geometric frames, mirror/Muthanna/radial, Tughra-inspired, calligrams/Arabesque, modern/minimal/abstract, openwork/negative-space/wire/solid/hollow/two-layer/two-tone, stones/enamel/pearl, men/women/kids, family/couple, long-text engraving, photo jewellery and experimental forms.
Use hybrid metadata + pgvector retrieval.
Store Design DNA, rights and historical performance.

## Product Construction Library
Reusable archetypes: two-loop name necklace, single-bail pendant, round/oval plate, photo pendant, name+photo disc, Y/lariat necklace, mesh bracelet nameplate, ring top/open ring, ear stud/drop, cufflink, tasbih accessory, bookmark/tassel, car hanger, keychain, watch accessory, gift set, family/couple multi-part pieces.
Store components/connectors/dimensions/material/process/assembly/rules/workshop outcomes.

## Customer / Reference / WhatsApp Intake
Inputs: text/name, request, reference image/screenshot, sketch, logo, jewellery photo, multiple refs, WhatsApp screenshot.
Classify reference jobs:
exact-text-replacement / same-structure-new-text / style-inspired-redesign / product-conversion / material-conversion / needs-clarification.
Vision/OCR is never source-text truth; require explicit confirmed text.
Store reference structure/material/style/components/attachment points, Design DNA and IP risk.
Flag brand/copyright risk and produce inspired alternatives where direct copying is unsafe.
Convert chats/screenshots into structured brief: customer, product, confirmed text, refs, material, quantity, budget, deadline, delivery, missing inputs, next action.
Generate natural Arabic/English reply drafts.
Maintain unified customer timeline.

## Parametric Generator / Ranking
AI proposes structured parameters; deterministic engine makes geometry.
Generate ≥30 internal candidates → Arabic QA → Geometry QA → Manufacturing QA → diversity → rank → show exactly 10.
Default weights: Arabic 30%, Manufacturing 25%, Visual 20%, Wearability 10%, Originality 10%, Customer Fit 5%.
Top 10 must be meaningfully different.

## 2D Proof + Designer Copilot
2D is first approval artifact.
Request → 10 options → select → refine → verify → final proof.
Proof shows option ID, exact source text, artwork, style, dimensions where available, manufacturing score.
Human designer may edit glyph, position, scale, stroke, tail, swash, connectors, bridges, dots, composition, dimensions and attachment points.
Version all edits.

## Constraint Solver / Auto Repair
Optimize beauty + Arabic integrity + wearability + manufacturability.
Validate minimum stroke/gap/bridge, connectivity, stone clearance, attachment points, sharp edges, balance, center of gravity, fit and process constraints.
Repair: bridge, artistic bridge, thicken, reposition, engrave, cutout, gemstone, manual.
Show Before/After; never silently change text.

## Long Text / Photo / Multi-Part
Support quotes, poetry, dedications, approved religious text, bookmarks, tassels, plates, keychains, gift tags, corporate gifts.
Optimize script, lines, font size, Kashida, Harakat density, margins, orientation, engraving stroke and safe zones.
Never delete/distort text to fit.
Support photo engraving with original + processed + approved asset.
Support 2–20+ names and paired/multi-part assemblies.

## Wearability / Process
Validate ring/wrist/necklace size, earring/pendant weight, chain load, comfort, snag/sharp-edge risk.
Process router: laser/casting/CNC/engraving/wax-3D print/enamel/stone/plating.
Apply kerf, shrinkage, tolerance, polishing/plating allowance and stone clearance.
Tolerance stack: Nominal / Min / Max / Workshop Capability.

## Customer Approval / 3D
Approval creates immutable DesignVersion/hash/timestamp/approver; changes invalidate approval.
3D only after 2D QA. Three.js/WebGL for visualization; CadQuery/OpenCascade for manufacturing CAD.
Support 360°, dimensions, thickness, chain/bail, stones, finish, estimated weight, materials, hanging/fit checks.

## Pricing / Workshop OS
Pricing = verified metal rate × estimated weight + workshop + stones + chain + plating + engraving + polishing + packaging + payment + delivery + operating/marketing allocation + margin + VAT.
Never invent live prices.
Workshop state:
New → Design Review → Technical Check → Approved → Manufacturing → QC → Rework? → Ready → Delivered.
Production Pack includes approved hash, exact text, product/material/dimensions/thickness/weight/process/loops/stones/stroke-gap/tolerances/BOM/routing/warnings/score/SVG/DXF/PDF/CAD.
Capture actual material/lot/weight/wastage/time/cost/defects/rework/QC.
Delivery completion requires Receiver Name, Staff Number, Actual Received Date.

## Workshop/Supplier / Capacity / QC / After-Sales
Score capability, quality, price, lead time, defects/rework, capacity and process compatibility.
Route jobs appropriately.
QC exact text, dimensions, thickness, weight, edges, finish, stones, engraving, assembly, photo evidence.
PASS/REWORK/REJECT.
After-sales: repair/remake/warranty/return/refund-credit/root cause/cost ownership.

## Product Master / Segments / B2B
SKU/variant engine: product, size, material, thickness, chain, stone, finish, BOM, process, weight, price, workshop route.
Support B2B/bulk corporate gifts, events, weddings, CSV/Excel names, batch approval/pricing/production.
Segments: Women/Men/Kids/Teens/Couples/Family/Corporate-Gifts.
Kids require independent safety gate.

## Trend Intelligence
One shared research gateway; agents for Global, UAE/GCC, Women, Men, Kids/Teens, Gifts, Accessories, Materials/Manufacturing, Competition, Evidence/IP, Merchandising.
Source hierarchy: official/industry/trade → respected design/fashion → brands/retail → social weak signals.
Loop:
Discover → Verify → Rights → Score → MFG Check → UAE Fit → Commercial Eval → Human Approval → Prototype → Customer Test → Sales/Workshop Results → Trend Memory.
Never copy proprietary designs.

## Memory / Control Plane / Events / Learning
PostgreSQL source of truth; pgvector retrieval; Redis session/cache; object storage media/CAD; immutable audit/events.
Memory: Session, Customer Preference(opt-in), Design Knowledge, Manufacturing, Episodic/Audit, Evaluation, Trend, Historical Beyond Style.
Import Beyond Style-owned proofs, vector/CAD, designer artwork, final products, fonts/glyphs, materials, dimensions, workshop/process, customer feedback/QC into structured memory. OCR is not authoritative text.
Control Plane versions Agents/Models/Prompts/Tools/Memory Policies/Design KB/Arabic Engine/Manufacturing Rules/Evaluations; supports routing, permissions, budgets, feature flags and rollback.
Events include RequestReceived, CandidatesGenerated, ArabicValidated, ManufacturingValidated, DesignSelected, CustomerApproved, QuoteCreated, OrderPaid, WorkshopAssigned, ManufacturingStarted, QCFailed, ReworkCompleted, Manufactured, Delivered, ActualResultsRecorded, EvaluationUpdated.
Implement idempotency/retries/DLQ/replay/audit.
No direct self-modification:
Observe → Learning Candidate → Offline Eval → Golden Dataset → Safety/MFG Tests → Comparison → Approval → Versioned Promotion → Monitor → Rollback.
Use Shadow Mode first.

## UX / Customer Service
Premium 2026 jewellery-tech, luxury/simple/fast/mobile-first.
Customer:
Idea/Reference → Style → 10 Proofs → Select/Edit → Final 2D → 3D → Approve → Price → Order.
Desktop: Tools | Canvas | Inspector | Variations/History.
True RTL/LTR. WCAG AA.
Anonymous basic design, later claim designs.
Customer Service Agent asks only missing fields and guides approval/order.
Primary CTA: MAKE IT FOR ME.

## Rights / Privacy / Security / Resilience
Track font/reference/template source, license, transformations, AI involvement, similarity/provenance.
Similarity check before commercial approval.
Private by default; no shared-model training without opt-in.
Security: RBAC, MFA-ready admin, CSP, rate limits, signed URLs, safe uploads, malware scan, SVG sanitization, font sandbox, MIME verification, secrets, audit, backups/restores, RPO/RTO, provider fallback, timeouts, circuit breakers, AI budgets.
Graceful deterministic fallback if external AI fails:
Text → shaping → approved font/glyph → parametric template → vector proof → manufacturing validation.
Feature flags: OFF/INTERNAL/SHADOW/BETA/PRODUCTION.

## Admin / BI
No-code admin: fonts/rights/archetypes/products/materials/workshops/manufacturing limits/pricing/margins/shipping/agent weights/trend thresholds/feature flags.
Funnel:
Visit → Generate → Select → 3D → Approve → Quote → Pay → Manufacture → QC → Deliver → Repeat.
Track revenue, margin, conversion, AI cost, top products/archetypes/fonts, abandoned designs, workshop quality, defects, lead time, repeat sales.

## Phases
P0: Arabic Engine, Design Graph, Font/Glyph, Design Intelligence, Product Construction, Reference/WhatsApp intake, Parametric Generator, Top-10 2D Proofs, Designer Copilot, Constraint/Auto Repair, long-text/photo/multi-part basics, score, approval/lock, SVG/DXF, workshop handoff, mobile, historical import.
P1: 3D, CAD, process router, workshop profiles, pricing, cart/orders, Customer Service AI, Production Packs, CRM/payment/integrations, QC/after-sales.
P2: Trend automation, community/collections, marketplace, workshop network, AR, advanced personalization/BI.
Do not implement P1/P2 until P0 acceptance passes.

## P0 Acceptance / Required Docs
Prove:
text or WhatsApp/reference → structured brief → exact text confirmation → knowledge retrieval → ≥30 candidates → Arabic+MFG QA → diversity → 10 proofs → selection → edit → repair → final approval/lock → valid mm SVG/DXF.
Mobile + desktop.
No fake buttons/data.
Maintain:
`docs/architecture.md`
`docs/implementation-plan.md`
`docs/production-readiness.md`
`docs/adr/`
Tests: lint, typecheck, unit, integration, E2E, Arabic shaping/RTL, fonts, SVG/DXF, geometry, manufacturing, security, performance/build.
Never claim 100% from compilation.
