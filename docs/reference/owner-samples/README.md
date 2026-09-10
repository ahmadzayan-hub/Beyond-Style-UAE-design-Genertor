# Owner samples — Beyond Style reference images (2026-09-10)

112 images were supplied by the owner in seven batches ("real samples to
LLM to learn"). They are ingested into the **Golden Production Memory**
(`backend/app/data/golden_production_cases.py`, cases BS-GPC-0003 … BS-GPC-0040)
as *structured construction lessons*, not as pictures to copy:

- **No text is read off any photo.** Every owner case seeds with
  `customer_source_text = None` and stays in the
  `GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION` tier until a customer confirms
  exact text on the platform. Names or dates visible on a sample are never data.
- **Personal photos are never persisted.** Anything showing a customer, a child,
  a face, an arm/neck, or a customer's engraved name/date is registered by
  sha256 only (`EXCLUDED_PERSONAL_DATA`) and is *not* in this folder.
- **Third-party photos are never copied.** Market references from other brands
  or of unknown origin are `EXCLUDED_THIRD_PARTY_RIGHTS` (hash only,
  `rights_provenance` THIRD_PARTY_NO_COPY / UNKNOWN_RIGHTS) and never influence
  generation or training export. They are *not* in this folder either.
- What **is** here: Beyond Style's own creatives, catalogue pages, workshop
  outlines and product photos without people — downscaled (≤1400 px, JPEG).
  Originals are hash-registered in the case file (`PENDING_OBJECT_STORE_UPLOAD`
  until the private object store receives them).

## Evidence tiers introduced for these samples

| Tier | Weight | Meaning |
|---|---|---|
| `MANUFACTURED_OWNER_SAMPLE` | 0.9 | a piece Beyond Style actually made (product photo / workshop outline); construction proven, text unverified |
| `MARKETING_RENDER_UNMANUFACTURED` | 0.3 | brand creatives / catalogue pages; merchandising memory, never construction or dimension truth |
| `EXTERNAL_INSPIRATION` | 0.2 | third-party market references; designer-advisory only |

## Index

| File | Case | Tier |
|---|---|---|
| 01 bar-name pendant layout proof (AI render, labelled) · 02 workshop outline | BS-GPC-0003 | MANUFACTURED_OWNER_SAMPLE |
| 05–08 layered charm / calligraphy necklace ads | BS-GPC-0008 | MARKETING_RENDER |
| 09 layered Latin name set ad | BS-GPC-0009 | MARKETING_RENDER |
| 10 cat + baby-feet charm bracelet ad · 19 workshop outline · 20 render | BS-GPC-0010 | MARKETING_RENDER |
| 12 bracelet size guide | `app/data/wearability.json` (OWNER_PUBLISHED) | — |
| 13 DecoType Thuluth III reference | `docs/CALLIGRAPHY_SOURCES.md` (locked commercial font — never imitated) | — |
| 14 · 51 · 52 Latin script name bracelet · 15 open name ring with heart · 16 enamel calligraphy cufflinks | BS-GPC-0005 / 0006 / 0007 | MANUFACTURED_OWNER_SAMPLE |
| 17 engraved Thuluth phrase disc keychain | BS-GPC-0011 | MANUFACTURED_OWNER_SAMPLE |
| 18 lariat with separated Latin letters ad | BS-GPC-0013 | MARKETING_RENDER |
| 21 enamel orchid brooch vector · 22 product thumbnail | BS-GPC-0014 | MANUFACTURED_OWNER_SAMPLE |
| 23 Arabic name necklace with stone dot ad | BS-GPC-0016 | MARKETING_RENDER |
| 24 Arabic name bar-pin brooch with hanging disc | BS-GPC-0015 | MANUFACTURED_OWNER_SAMPLE |
| 25–29 men's 925 chain ads with length/weight tables | BS-GPC-0017 + `wearability.json#chain_catalogue` | MARKETING_RENDER (OWNER_CATALOGUE_STATED) |
| 30 car mirror hanger ad · 50 hanger with a car-brand medallion (recorded as a BRAND-RISK example) | BS-GPC-0020 | MARKETING_RENDER |
| 31 block name curb bracelet · 34 script name bracelet with birthstone | BS-GPC-0021 | MARKETING_RENDER |
| 32 Arabic name with pearl stations · 33 monoline name with heart-stone drop | BS-GPC-0022 | MARKETING_RENDER |
| 35 intertwined calligraphy name pendant ad | BS-GPC-0024 | MARKETING_RENDER |
| 36 phrase plate on mesh bracelet ad · 46 finished gold + silver pieces · 47 studio photo · 54 name plates on mesh bands | BS-GPC-0025 | MANUFACTURED_OWNER_SAMPLE |
| 49 relief calligraphy disc cufflinks ad | BS-GPC-0033 | MARKETING_RENDER |
| 53 letter-station necklace with turquoise beads | BS-GPC-0034 | MANUFACTURED_OWNER_SAMPLE |
| 48 packaging materials & finishes board | BS-GPC-0032 → `product_catalogue.json#packaging` | MARKETING_RENDER |
| 37–45 catalogue pages (rings p.19–21, brooches p.27, necklaces p.4/5/7/8/9) | BS-GPC-0023 → `app/data/product_catalogue.json` (75 items, AED starting prices, OWNER_CATALOGUE_STATED) | MARKETING_RENDER |

Hash-only (not in this folder): pavé name necklace on a person (0004), engraved
name+date keychain and pierced name disc with date (0011/0012), kids' name
jewellery market photos (0018), men's cufflink market photos (0019), pearl-strand
and ID-bar references (0026), necklace length-guide graphics (0028 → the
industry-standard chart in `wearability.json`), Meta ad screenshot (0009), retail-display survey of stock name necklaces / engraved bars / cord bracelets photographed in a shop (0029–0031: design rights unknown, several held in hand), a branded framed-calligraphy pendant on a person (0036), third-party font tables / font comparison sheets (0037: unidentified commercial fonts, nothing traced), calligraphy phrase-library screenshots incl. a Qur'anic verse (0038: sacred-text path, third-party vectors), a WhatsApp lariat reference on a person (under 0013), the Top Style retail stock survey (0039: third-party carded stock incl. a pavé sacred word → sacred-text path), supplier renders of a leather-strap phrase plate, rope cuff with pavé name and pavé halo frame (0040: unknown rights), the brand mood board with AI-composited faces (under 0032).

How the memory is used: `golden_case_influence(product)` in
`backend/app/fonts/curation.py` returns construction principles + lessons per
platform product (necklace, pendant, multi_name, bracelet, ring, cufflink,
keychain, brooch, hanger, earrings) from owned cases only, ordered by
`EVIDENCE_PRIORITY`; geometry is never copied. The catalogue and size guide are
served by `GET /api/products/catalogue` and `GET /api/products/size-guide`.
