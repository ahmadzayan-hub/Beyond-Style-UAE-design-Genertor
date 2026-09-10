"""Real Beyond Style production cases kept as top-tier design memory.

Every record here is a genuine order that was designed, manufactured,
delivered and positively received — NOT a synthetic fixture. The two
disciplines that govern this file:

TEXT TRUTH — `customer_source_text` is only ever populated from an order
record or an explicit customer/owner confirmation. It is never read off a
photo. Where no such authority exists the field stays None with
`source_text_status="PENDING_CUSTOMER_VERIFICATION"`, and the service
layer refuses to promote the case to the GOLDEN_PRODUCTION tier.

PRIVACY — WhatsApp conversation screenshots are NOT persisted. Their
evidence descriptors are recorded as EXCLUDED_PERSONAL_DATA and only a
normalized, de-identified feedback sentence is stored. Retaining the
original conversation image would require explicit customer consent that
does not exist for these cases.
"""
from __future__ import annotations

from ..ai.design_dna import DesignDNA

#: Ordered evidence roles a case may carry, in lifecycle order.
EVIDENCE_ROLES = [
    # What the customer picked out of the existing Beyond Style catalogue.
    "customer_selection",
    # Beyond Style's hand markup ON that selection, capturing construction intent.
    "shop_annotation",
    "style_reference",
    "reference_image",
    "concept_sketch",
    "concept_selection",
    "workshop_outline",
    # One of the writing styles put in front of the customer to choose between.
    "writing_variant_proposal",
    "layout_proof",
    "final_product",
    "final_product_video",
    "customer_conversation",
]

#: Evidence that is registered by content hash but deliberately not kept.
EXCLUDED_PERSONAL_DATA = "EXCLUDED_PERSONAL_DATA"
#: Evidence that is retainable but whose binary has not been uploaded to
#: the private object store yet (honest: the record exists, the file does
#: not — no admin view pretends otherwise).
PENDING_OBJECT_STORE = "PENDING_OBJECT_STORE_UPLOAD"
#: Third-party market photos: registered by hash for de-duplication and
#: audit only; the binary is never stored and the artwork is never copied.
EXCLUDED_THIRD_PARTY = "EXCLUDED_THIRD_PARTY_RIGHTS"


#: Uploads that were PNG (marketing composites/vector exports); all other evidence is JPEG.
_PNG_EVIDENCE = {
    "00f9d9ea968fa69ecf9731f9e526534c7b4360720fd5dd262211b4ab58130e43",
    "0dccb7265098a4331208a09ab4b6733c9df28d850fe68bd8cf1cec72baa676ba",
    "13d26340d2546f99de77e6392643174af59081e5103293079cf7c8b91bbc6653",
    "229686664496398adda52136f56083d5095fef6679438713d2906bceac3b0f4f",
    "3311ec9e2e68b2acefaf8a9020b752fad13315256ae82ffef40326c17066a232",
    "41fbe4a10d7ddefcfafd5076cbc3cf18c032e73ca95d1632d8c3ff3cca919367",
    "5420c81751ab1ec8a3f24efb0c55aa3d66d07942d04c2439705c11988d326706",
    "55839d236338691e287bc46a78e7d16c89d4b875d98eb657ee33f68539b544a3",
    "5e698d391e41dff049ccb0f441e08a0e6aa05639a7a2024468661e4b4fb97110",
    "656978e0783d52f5316e563d0589993b95e3395dc65ff43916b4a1448d9feec5",
    "74b88b5d7ea3bc03bfcca168a65fad992e04b5436f229f318a674deae8cdcd02",
    "753ab6e1ff0a4c371327e4ed6bab28f5690b5185de17526ab70730a4f8d4e2de",
    "7d6e86da0b17ba55f7433e16f95facd59113711048fc48f55243bc29214981a7",
    "7fe41b6fc83618b99af57edec5e4fdd4e04c818ee490e8dcff7214b23dfb3319",
    "851179b796644fb880ba1449684132ede481613b124a2b685df4730c72f11078",
    "8613fb79e94569970af550b9bdc3ff3833a4b59cdcb3114edf14cc4de32a6943",
    "ae86e75f7b09a03e47cbb29978c4d455caf9bd12ec38621100d6e4ce5e705ebc",
    "b0c1604ab5338f769a177bacaae59e5d58c67de032aef2c589617447647b2a25",
    "b5a9070a1c5f7568c8f0887067438449d61c9ba555cdc43c6cf220894564fc2d",
    "ba02db3fc7e0e0a9ce9e0ff98cfd502ddaed7459a212e236123a076c2046ff6e",
    "bb1f82373a68ea340a53465619c195eaf2646d5c5da247a7a43036edbb39b212",
    "dde7a9c6b0711a543adde607caa464487d0c9b3ad24e4d59f3271561c65d89b2",
    "e3a2b49ae6201e0a44ae218cebce242a0d60cfb698e29f29cdfdb1dd6c266d2a",
    "e8ca9b1a5f0c208344b3e1ffb3104167eb7b07efb4dd07acd463176fdbd59f48",
    "ec07f9d9e150e5ad23f9e564297b6376c8051afd77c02bec830ba00ab5b41467",
    "f4eaea54558e89964a3e423fa17cf2dc1f1ef09ee35cf0cc7b52e423b70845cb",
    "fa848ab421630bfd49e56837f969dad357939aaba710e024aa0eb13729da7f38",
}


def _ev(role, sha256, width, height, size_bytes, storage_status, note, media_type=None):
    if media_type is None:
        media_type = "image/png" if sha256 in _PNG_EVIDENCE else "image/jpeg"
    return {
        "role": role,
        "sha256": sha256,
        "media_type": media_type,
        "width": width,
        "height": height,
        "size_bytes": size_bytes,
        "storage_key": None,
        "storage_status": storage_status,
        "note": note,
    }


# ---------------------------------------------------------------------------
# CASE 1 — Arabic letter drop earrings with hanging pearl
# ---------------------------------------------------------------------------

ARABIC_LETTER_PEARL_EARRINGS = {
    "case_id": "BS-GPC-0001-arabic-letter-pearl-earrings",
    # The letters are legible in the workshop drawing, but reading them off
    # an image is exactly what CLAUDE.md forbids: identity must come from
    # the order record or an explicit confirmation. Until then this case
    # contributes STYLE and CONSTRUCTION memory only.
    "customer_source_text": None,
    "source_text_status": "PENDING_CUSTOMER_VERIFICATION",
    "source_text_authority": "NOT_ESTABLISHED",
    "source_text_sha256": None,
    "primary_names": None,
    "language": "AR",
    "product_type": "ARABIC_LETTER_EARRINGS",
    "layout_style": "ELONGATED_VERTICAL_LETTER_PAIR",
    "composition_type": "ASYMMETRIC_LETTER_PAIR",
    "construction": ["LETTER_BODY", "LOWER_ATTACHMENT_LOOP", "HANGING_PEARL"],
    "construction_topology": "LETTER_BODY+LOWER_ATTACHMENT_LOOP+HANGING_PEARL",
    "attachment_topology": "EAR_WIRE_TOP + INTEGRATED_LOWER_CIRCULAR_LOOP",
    "attachment_points": [
        {"position": "letter_top", "kind": "ear_wire_hook", "load": "primary_suspension"},
        {"position": "letter_bottom", "kind": "integrated_circular_loop", "load": "pearl_drop"},
    ],
    "chain_topology": None,
    "design_version_id": None,
    "canonical_geometry_hash": None,
    "lineage_status": "PRE_PLATFORM_CASE_NO_DESIGN_VERSION",
    "material": "silver_tone_metal",
    "finish": "polished",
    "dimensions": None,  # not measured — never guessed from photographs
    "stone_or_pearl_details": {
        "type": "pearl",
        "shape": "teardrop",
        "colour": "white",
        "count_per_earring": 1,
        "attachment": "suspended_from_lower_loop",
    },
    "workshop_changes": [
        {
            "change": "letter outlines cleaned into a single closed contour per piece",
            "stage": "concept_to_workshop_outline",
            "effect": "cuttable, connected geometry",
        },
        {
            "change": "lower circular loop drawn as part of the letter body, not soldered on",
            "stage": "workshop_outline",
            "effect": "removed a solder joint and its failure mode",
        },
    ],
    "manufacturing_result": "SUCCESS",
    "production_success": True,
    "customer_feedback": "Customer strongly liked the finished product and approved it.",
    "customer_sentiment": "HIGHLY_POSITIVE",
    "customer_approved": True,
    "memory_tier": "GOLDEN_PRODUCTION",
    "evidence_tier": "MANUFACTURED_CUSTOMER_APPROVED",
    "ranking_weight": "HIGH",
    "rights_provenance": "BEYOND_STYLE_OWNED",
    "privacy_status": "PRIVATE",
    "retrieval_keywords": [
        "arabic letter earrings", "minimal arabic earrings", "pearl arabic earrings",
        "single letter jewellery", "hanging letter earrings", "arabic initial earrings",
        "drop earrings", "letter drop earring", "حلق حرف", "حلق عربي",
    ],
    "dna": DesignDNA(
        source="human_curated_production_case",
        analyzer_model="none",
        product_type="drop_earring",
        audience="women",
        material="silver",
        metal_color="silver",
        script_family="modern_arabic",
        calligraphy_style="minimal_modern",
        composition="vertical",
        shape_envelope="elongated_vertical",
        construction="plate",
        stroke_character="clean_even_weight",
        kashida="absent",
        swashes="present",
        tails="curved_terminal",
        symmetry="asymmetric_pair",
        negative_space="open",
        frame="none",
        bail_loops="integrated_lower_circular_loop",
        chain_attachment="ear_wire_hook",
        stones="none",
        pearls="hanging_teardrop",
        enamel="none",
        ornament="minimal",
        geometry_density="low",
        luxury_score=0.75,
        minimal_score=0.85,
        heritage_score=0.35,
        modern_score=0.8,
        manufacturing_complexity="low",
        reference_confidence=0.9,
        orientation="vertical",
    ),
    "stage_comparison": {
        "stages": ["concept_selection", "workshop_outline", "manufactured_product"],
        "measurement_method": "VISUAL_REVIEW_NO_VECTOR_GEOMETRY",
        "dimensions": {
            "silhouette_fidelity": {"score": 0.9, "note": "manufactured pieces follow the workshop outline closely"},
            "proportions": {"score": 0.9, "note": "elongated vertical proportion preserved through all three stages"},
            "letter_identity": {
                "score": None,
                "status": "NOT_ASSESSED",
                "note": "identity cannot be verified without the authoritative source text",
            },
            "loop_position": {"score": 0.95, "note": "lower loop sits where the outline places it on both pieces"},
            "attachment_geometry": {"score": 0.9, "note": "ear wire at the top, pearl at the lower loop, as drawn"},
            "pearl_placement": {"score": 0.9, "note": "single teardrop pearl hangs centred below each letter"},
            "visual_balance": {"score": 0.85, "note": "asymmetric pair reads as a balanced set when worn"},
        },
    },
    "design_process": [
        {"step": 1, "actor": "customer", "action": "requested Arabic letter earrings"},
        {"step": 2, "actor": "beyond_style", "action": "proposed letter concepts on a single sheet"},
        {"step": 3, "actor": "customer", "action": "selected the pair, marked by hand on the concept sheet"},
        {"step": 4, "actor": "beyond_style", "action": "redrew the selection as a clean workshop outline"},
        {"step": 5, "actor": "workshop", "action": "manufactured the letter bodies with integrated lower loops"},
        {"step": 6, "actor": "workshop", "action": "attached one teardrop pearl per piece"},
        {"step": 7, "actor": "beyond_style", "action": "sent final photos/video to the customer"},
        {"step": 8, "actor": "customer", "action": "received the piece and approved it"},
    ],
    "variant_selection": {
        "stage": "letter_concept",
        "options_presented": 4,
        "selection_method": "HAND_MARKED_ON_CONCEPT_SHEET",
        "selected_variant": "the hand-circled pair",
        "selection_status": "RECORDED_FROM_CASE_EVIDENCE",
        "note": "the concept sheet carries four letter shapes in two near-duplicate pairs; "
                "the circled pair is what went to the workshop",
    },
    "lessons_learned": [
        "An integrated lower loop drawn into the letter body removes a solder joint and survived manufacture intact.",
        "A low-ornament, single-weight Arabic letter silhouette manufactures cleanly at earring scale.",
        "One hanging teardrop pearl per piece adds perceived value without adding a manufacturing constraint.",
        "An asymmetric letter pair is accepted by customers as a set — the two pieces need not mirror.",
        "Letter identity must come from the order record: the photographic record alone cannot certify it.",
    ],
    "evidence": [
        _ev("style_reference", "c04507ed960fec00ab5d9558b22ae53ab6c2db4f3f0bb69fa30187779ba9c02a",
            1122, 1402, 141194, PENDING_OBJECT_STORE,
            "Beyond Style branded product graphic — same construction family, turquoise stone variant"),
        _ev("style_reference", "d0146e5eec52af6d4b797d653795df662ce16cfef1857f96d5f6ff381d3f7232",
            1122, 1402, 131234, PENDING_OBJECT_STORE,
            "closer crop of the same branded graphic"),
        _ev("reference_image", "d54568ba1c178e6f38438e0057b5eff62a9dae579c0627cdd571046a42797b31",
            333, 501, 10906, PENDING_OBJECT_STORE, "worn-on-ear reference showing the hook and drop stone"),
        _ev("concept_selection", "321aa18bad34fca4670426875790bc01b4491bcbadd1f298290283437c5ccdff",
            1220, 627, 28239, PENDING_OBJECT_STORE, "letter concept sheet with the selected pair hand-circled"),
        _ev("workshop_outline", "eb619adbfd50f91c55ad4174c81d78bc0d4cc53ae5b4f62a7d56fdbf68603d9f",
            1600, 900, 24537, PENDING_OBJECT_STORE, "clean vector outline handed to the workshop"),
        _ev("final_product", "f5ec3a5aaad1022ff630fe4cb7d677082380b41f42c9ad2ff86e42fe4b6eb10d",
            720, 1280, 68672, PENDING_OBJECT_STORE, "manufactured pair with hanging pearls"),
        _ev("customer_conversation", "1c4ccd3c4f715335fc2f9078065387db9e0f2a38e4bee43bc4c68f3745eaa07e",
            1080, 2316, 393977, EXCLUDED_PERSONAL_DATA,
            "WhatsApp screenshot — contains contact name, avatar and timestamps; not stored, "
            "only the normalized feedback sentence is kept"),
    ],
}


# ---------------------------------------------------------------------------
# CASE 2 — Layered English name necklace (ADAM / OMAR)
# ---------------------------------------------------------------------------

LAYERED_NAME_NECKLACE_ADAM_OMAR = {
    "case_id": "BS-GPC-0002-layered-name-necklace-adam-omar",
    # No order record exists in this system (pre-platform order), so the
    # names come from the owner's explicit written instruction, recorded
    # here verbatim and in that exact order.
    "customer_source_text": "ADAM\nOMAR",
    "source_text_status": "CONFIRMED",
    "source_text_authority": "OWNER_CONFIRMED_CASE_EVIDENCE",
    "source_text_sha256": None,  # computed at seed time from the text itself
    "primary_names": ["ADAM", "OMAR"],
    "language": "EN",
    "product_type": "LAYERED_NAME_NECKLACE",
    "layout_style": "VERTICAL_STACKED_NAMES",
    "composition_type": "TWO_NAME_LAYERED_COMPOSITION",
    "construction": ["OUTER_CHAIN", "INNER_CENTER_DROP", "VERTICAL_NAME_ELEMENTS"],
    "construction_topology": "OUTER_CHAIN+INNER_CENTER_DROP+VERTICAL_NAME_ELEMENTS",
    "attachment_topology": "PER_LETTER_JUMP_RINGS ON TWO INDEPENDENT CHAIN RUNS",
    "attachment_points": [
        {"position": "upper_chain_center", "kind": "bezel_accent_then_letter_run", "load": "upper_name"},
        {"position": "letter_to_letter", "kind": "jump_ring", "load": "vertical_letter_chain"},
        {"position": "lower_drop_terminal", "kind": "bezel_accent", "load": "drop_terminal"},
    ],
    "chain_topology": "TWO_LAYER: shorter outer chain framing the neckline + longer inner chain carrying the drop",
    "design_version_id": None,
    "canonical_geometry_hash": None,
    "lineage_status": "PRE_PLATFORM_CASE_NO_DESIGN_VERSION",
    "material": None,  # alloy not recorded; appearance only is described in `finish`
    "finish": "polished_silver_tone",
    "dimensions": None,
    "stone_or_pearl_details": {
        "type": "bezel_accent",
        "count": 2,
        "placement": ["above_upper_name", "below_lower_name"],
        "note": "small round accents terminating each vertical name run",
    },
    "workshop_changes": [
        {
            "change": "names split into individual letter elements joined by jump rings",
            "stage": "layout_proof_to_manufacture",
            "effect": "the run flexes and lies flat on the body instead of reading as a rigid bar",
        },
        {
            "change": "upper name carried by the shorter chain, lower name by the longer drop",
            "stage": "concept_to_manufacture",
            "effect": "two names stay independently readable instead of colliding",
        },
    ],
    "manufacturing_result": "SUCCESS",
    "production_success": True,
    "customer_feedback": "Customer strongly approved the final necklace.",
    "customer_sentiment": "HIGHLY_POSITIVE",
    "customer_approved": True,
    "memory_tier": "GOLDEN_PRODUCTION",
    "evidence_tier": "MANUFACTURED_CUSTOMER_APPROVED",
    "ranking_weight": "HIGH",
    "rights_provenance": "BEYOND_STYLE_OWNED",
    "privacy_status": "PRIVATE",
    "retrieval_keywords": [
        "english name necklace", "layered necklace", "vertical necklace",
        "two name necklace", "stacked letters necklace", "layered name necklace",
        "double chain name necklace", "vertical name drop", "name necklace",
    ],
    "dna": DesignDNA(
        source="human_curated_production_case",
        analyzer_model="none",
        product_type="necklace",
        audience="unisex",
        material="unknown",
        metal_color="silver",
        script_family="latin_script",
        calligraphy_style="bold_serif",
        composition="stacked",
        shape_envelope="vertical_linear_drop",
        construction="plate",
        stroke_character="bold_serif_slab",
        kashida="absent",
        swashes="absent",
        tails="absent",
        symmetry="center_aligned",
        negative_space="even_letter_spacing",
        frame="none",
        bail_loops="per_letter_jump_rings",
        chain_attachment="two_chain_layered",
        stones="two_small_bezel_accents",
        pearls="none",
        enamel="none",
        ornament="minimal",
        geometry_density="low",
        luxury_score=0.7,
        minimal_score=0.8,
        heritage_score=0.2,
        modern_score=0.85,
        manufacturing_complexity="medium",
        reference_confidence=0.9,
        orientation="vertical",
    ),
    "stage_comparison": {
        "stages": [
            "customer_selection", "shop_annotation", "concept_sketch",
            "selected_writing_variant", "manufactured_product",
        ],
        "measurement_method": "VISUAL_REVIEW_NO_VECTOR_GEOMETRY",
        "dimensions": {
            "silhouette_fidelity": {"score": 0.9, "note": "sketch's two-loop + centre-drop topology is what was built"},
            "letter_order_accuracy": {"score": 1.0, "note": "A-D-A-M and O-M-A-R read top-to-bottom in the finished piece"},
            "name_readability": {"score": 0.9, "note": "bold serif letters stay legible at worn scale"},
            "vertical_spacing": {"score": 0.85, "note": "jump-ring spacing is even; slightly wider than the proof"},
            "center_alignment": {"score": 0.9, "note": "both runs hang centred on their chains"},
            "drop_proportion": {"score": 0.9, "note": "long-drop proportion of the reference style is preserved"},
            "chain_balance": {"score": 0.85, "note": "the two chain lengths separate cleanly without tangling"},
            "wearability": {"score": 0.9, "note": "flexible letter runs lie flat against the body"},
            "visual_balance": {"score": 0.9, "note": "upper/lower name hierarchy reads as intended"},
            "manufacturing_faithfulness": {"score": 0.9, "note": "delivered piece matches the approved layout proof"},
        },
    },
    "design_process": [
        {"step": 1, "actor": "customer",
         "action": "chose an existing published Beyond Style design as the starting point"},
        {"step": 2, "actor": "beyond_style",
         "action": "drew by hand over the customer's chosen design to fix the construction intent"},
        {"step": 3, "actor": "customer", "action": "gave the two names to be made"},
        {"step": 4, "actor": "beyond_style", "action": "proposed two writing styles for those names"},
        {"step": 5, "actor": "customer", "action": "selected one of the two writing styles"},
        {"step": 6, "actor": "beyond_style",
         "action": "produced the final design to the customer's selected style and requirements"},
        {"step": 7, "actor": "workshop", "action": "manufactured the layered two-chain necklace"},
        {"step": 8, "actor": "customer", "action": "received the piece and approved it"},
    ],
    "variant_selection": {
        "stage": "writing_style",
        "options_presented": 2,
        "selection_method": "CUSTOMER_CHOSE_FROM_TWO_PROPOSALS",
        "options": [
            {
                "variant": "ROTATED_LETTERS",
                "description": "letters rotated 90°, reading along the vertical run",
            },
            {
                "variant": "UPRIGHT_STACKED_LETTERS",
                "description": "each letter upright, stacked top to bottom",
            },
        ],
        "selected_variant": "UPRIGHT_STACKED_LETTERS",
        # The owner confirmed that two styles were proposed and one chosen,
        # but did not state WHICH. This reading comes from the finished
        # piece and is flagged as such rather than asserted as a record.
        "selection_status": "OBSERVED_FROM_FINAL_PRODUCT_NOT_OWNER_CONFIRMED",
    },
    "lessons_learned": [
        "A customer choosing from our own published catalogue removes third-party IP risk entirely — "
        "the starting point is already ours to reproduce.",
        "Drawing by hand over the customer's chosen design is what fixed the construction intent; "
        "the sketch and the layout proof both descend from that markup.",
        "Offering exactly two writing styles — not one, not ten — got a decision in a single round.",
        "Splitting a name into per-letter elements on jump rings gives a vertical run that lies flat and reads cleanly.",
        "A two-chain layered arrangement keeps two names independently readable; one chain would force them to compete.",
        "Bold serif letterforms survive the size reduction to necklace scale better than thin or script forms.",
        "Small bezel accents terminating each run add a finished look with no extra manufacturing constraint.",
        "A vertical stacked layout proof shown before manufacture is what the customer approves against — keep it.",
    ],
    "evidence": [
        _ev("customer_selection", "46a3d8faf363b6cf9ce77ad039a0f0de07b6c96848dea3a85e8d7599f73185d3",
            1054, 1600, 93976, PENDING_OBJECT_STORE,
            "the published Beyond Style design the CUSTOMER chose as the starting point — "
            "selected from our own catalogue, so there is no third-party IP to clear"),
        _ev("shop_annotation", "aec82d6954c5e2df18365078265c7f4627ed38632fea9bc10d5be2be43a3bb7d",
            1054, 1600, 101197, PENDING_OBJECT_STORE,
            "Beyond Style hand markup over the customer's selection, marking the two chain "
            "runs and the centre drop that had to be reproduced"),
        _ev("concept_sketch", "a40b2247166c455b086df12f65c79ab177f9ce711509634916d8da4d731d73a3",
            936, 1280, 56963, PENDING_OBJECT_STORE,
            "construction sketch abstracted from the annotation: outer chain, inner chain, "
            "two vertical name drops"),
        _ev("writing_variant_proposal", "7903ba43a6121b6704c0c22819e09887162beb3904bce22a201b9da5c7c64106",
            1167, 666, 33115, PENDING_OBJECT_STORE,
            "the two writing styles offered to the customer side by side: rotated letters "
            "(left) and upright stacked letters (right), both names in each"),
        _ev("writing_variant_proposal", "e5814d6a99f310c29121797b76656d988a84f94ff18d62a9569a47f3c770b92a",
            1180, 1280, 26034, PENDING_OBJECT_STORE,
            "the rotated-letter writing style shown on its own at working size"),
        _ev("customer_conversation", "3e8e0b947bdecd6271c749ec939542a6400d47396f8ac4cc66039068b657e76f",
            1080, 2316, 434153, EXCLUDED_PERSONAL_DATA,
            "WhatsApp screenshot carrying the final-product video — contains contact name, avatar and "
            "timestamps; not stored, only the normalized feedback sentence is kept"),
    ],
}


# ---------------------------------------------------------------------------
# OWNER SAMPLES (2026-09-10) — Beyond Style's own manufactured pieces and
# product-line creatives supplied by the owner as learning material.
#
# Evidence tiers are honest about what each image proves:
#   MANUFACTURED_OWNER_SAMPLE       photo of a real piece from Beyond Style's
#                                   workshop (customer approval not on file)
#   MARKETING_RENDER_UNMANUFACTURED AI-composited product-line creative —
#                                   merchandising memory, never construction
#                                   truth
# Text is never read off a photograph (source_text_status stays PENDING),
# dimensions are never guessed, and photographs showing a customer's body
# or chat UI are registered by hash only (EXCLUDED_PERSONAL_DATA).
# ---------------------------------------------------------------------------

_OWNER_STAGE = {
    "stages": ["owner_sample"],
    "measurement_method": "VISUAL_REVIEW_NO_VECTOR_GEOMETRY",
    "dimensions": {
        "letter_identity": {"score": None, "status": "NOT_ASSESSED",
                            "note": "identity cannot be verified without the authoritative source text"},
    },
}


def _owner_case(case_id, *, product_type, language, layout_style, composition_type, construction, topology,
                attachment_topology, attachment_points, chain_topology, material, finish, stones, dna,
                keywords, lessons, evidence, evidence_tier="MANUFACTURED_OWNER_SAMPLE", manufactured=True,
                workshop_changes=None, feedback=None, rights_provenance="BEYOND_STYLE_OWNED",
                supplied_as="owner learning sample", dimensions=None):
    """One owner-supplied sample (2026-09-10 batches). Rights default to
    BEYOND_STYLE_OWNED; third-party market references must pass
    rights_provenance="THIRD_PARTY_NO_COPY" or "UNKNOWN_RIGHTS" so they can
    never reach production export or generation influence."""
    return {
        "case_id": case_id,
        "customer_source_text": None,
        "source_text_status": "PENDING_CUSTOMER_VERIFICATION",
        "source_text_authority": "NOT_ESTABLISHED",
        "source_text_sha256": None,
        "primary_names": None,
        "language": language,
        "product_type": product_type,
        "layout_style": layout_style,
        "composition_type": composition_type,
        "construction": construction,
        "construction_topology": topology,
        "attachment_topology": attachment_topology,
        "attachment_points": attachment_points,
        "chain_topology": chain_topology,
        "design_version_id": None,
        "canonical_geometry_hash": None,
        "lineage_status": "PRE_PLATFORM_CASE_NO_DESIGN_VERSION",
        "material": material,
        "finish": finish,
        "dimensions": dimensions,
        "stone_or_pearl_details": stones,
        "workshop_changes": workshop_changes or [],
        "manufacturing_result": "SUCCESS" if manufactured else "NOT_MANUFACTURED",
        "production_success": manufactured,
        "customer_feedback": feedback,
        "customer_sentiment": "UNKNOWN",
        "customer_approved": False,
        "memory_tier": "GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION",
        "evidence_tier": evidence_tier,
        "ranking_weight": "HIGH" if manufactured else "MEDIUM",
        "rights_provenance": rights_provenance,
        "privacy_status": "PRIVATE",
        "retrieval_keywords": keywords,
        "dna": dna,
        "stage_comparison": _OWNER_STAGE,
        "design_process": [{"step": 1, "actor": "beyond_style", "action": f"supplied as {supplied_as} (2026-09-10)"}],
        "variant_selection": {"stage": "not_recorded", "options_presented": None, "selection_method": "NOT_RECORDED",
                              "selected_variant": None, "selection_status": "NOT_RECORDED", "note": ""},
        "lessons_learned": lessons,
        "evidence": evidence,
    }


def _dna(**kw):
    base = dict(source="human_curated_production_case", analyzer_model="none", audience="women",
                material="gold", metal_color="yellow_gold", kashida="absent", harakat_style="none",
                dot_style="round", pearls="none", enamel="none", reference_confidence=0.85)
    base.update(kw)
    return DesignDNA(**base)


NAME_ON_BASELINE_BAR_PENDANT = _owner_case(
    "BS-GPC-0003-name-on-baseline-bar-pendant",
    product_type="ARABIC_NAME_BAR_PENDANT", language="AR",
    layout_style="SINGLE_NAME_ON_HORIZONTAL_BAR", composition_type="NAME_OVER_BASELINE_BAR",
    construction=["NAME_BODY", "BASELINE_BAR", "END_RINGS_ON_BAR", "DESCENDER_BELOW_BAR", "STONE_AS_DOT"],
    topology="NAME_BODY+BASELINE_BAR+END_RINGS_ON_BAR",
    attachment_topology="CHAIN_RINGS_AT_BOTH_BAR_ENDS",
    attachment_points=[{"position": "bar_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "bar_right_end", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="SINGLE_CHAIN_THROUGH_BAR_END_RINGS",
    material="gold_tone_metal", finish="polished",
    stones={"type": "small_round_stone", "count": 1, "placement": "replaces_a_dot_on_the_bar_end", "setting": "prong"},
    dna=_dna(product_type="pendant", script_family="diwani", calligraphy_style="flowing_diwani_influenced",
             composition="horizontal", shape_envelope="wide_horizontal", construction="openwork",
             stroke_character="modulated_calligraphic", swashes="present", tails="descender_below_bar",
             symmetry="asymmetric", negative_space="open", frame="baseline_bar",
             bail_loops="integrated_rings_at_bar_ends", chain_attachment="bar_end_rings", stones="single_accent",
             ornament="minimal", geometry_density="medium", luxury_score=0.7, minimal_score=0.7,
             heritage_score=0.6, modern_score=0.6, manufacturing_complexity="medium", orientation="horizontal"),
    keywords=["name on bar", "bar necklace", "baseline bar pendant", "diwani name necklace", "arabic name bar",
              "stone dot", "end rings", "قلادة اسم", "اسم على بار", "ديواني"],
    lessons=[
        "A horizontal bar under the name is the chain attachment: integrated rings at both bar ends carry the chain, so no ring is soldered to a letter.",
        "Descenders are allowed to drop below the bar — the bar reads as a baseline, not a boundary.",
        "One small prong-set stone can stand in for a letter dot or terminate the bar; the stone seat must be planned in the outline (≈1.5 mm seat), never added after cutting.",
        "The AI render (labelled) and the vector outline agree on structure; the outline is what the workshop cut.",
    ],
    evidence=[
        _ev("layout_proof", "123e30b2ed78a1829201079548fe62e11f55427d16a4ba0ea37b652e1fa943b8",
            4624, 2352, 475732, PENDING_OBJECT_STORE,
            "AI-labelled layout render of the bar pendant with a stone-dot — presentation only, never manufacturing truth"),
        _ev("workshop_outline", "ce9f2db5d7fe98ef5ac90bbfd786ccf4f3ca6c9445ed238e62a0c197714f1c6e",
            1156, 589, 19543, PENDING_OBJECT_STORE,
            "vector outline: name on baseline bar, rings at both bar ends, descender below the bar"),
        _ev("final_product", "825eaabc4730240db9e682cda88f24750c2d6298ee2ac61763a246d31fe811a8",
            1080, 2316, 575058, EXCLUDED_PERSONAL_DATA,
            "workshop photo of the finished gold piece worn by a customer, delivered over chat — body and chat UI visible; not stored"),
    ],
)

PAVE_NAME_NECKLACE_ON_BAR = _owner_case(
    "BS-GPC-0004-pave-thin-stroke-name-necklace",
    product_type="ARABIC_NAME_PAVE_NECKLACE", language="AR",
    layout_style="SINGLE_NAME_STONE_SET", composition_type="NAME_CROSSED_BY_THIN_BAR",
    construction=["NAME_BODY", "PAVE_SET_STROKES", "THIN_CROSSING_BAR", "RINGS_AT_NAME_ENDS"],
    topology="NAME_BODY(PAVE)+THIN_CROSSING_BAR+RINGS_AT_NAME_ENDS",
    attachment_topology="CHAIN_RINGS_AT_FIRST_AND_LAST_LETTER",
    attachment_points=[{"position": "first_letter", "kind": "ring", "load": "chain"},
                       {"position": "last_letter", "kind": "ring", "load": "chain"}],
    chain_topology="SINGLE_FINE_CHAIN", material="white_gold_tone_metal", finish="polished",
    stones={"type": "pave_round_stones", "count": "many", "placement": "along every stroke", "setting": "micro_pave"},
    dna=_dna(product_type="pendant", material="white_gold", metal_color="white_gold", script_family="ruqaa",
             calligraphy_style="thin_calligraphic", composition="horizontal", shape_envelope="wide_horizontal",
             construction="openwork", stroke_character="thin_even_weight", swashes="present", tails="curved_terminal",
             symmetry="asymmetric", negative_space="open", frame="thin_crossing_bar", bail_loops="rings_at_name_ends",
             chain_attachment="name_end_rings", stones="pave_along_strokes", ornament="stones_only",
             geometry_density="low", luxury_score=0.9, minimal_score=0.6, heritage_score=0.4, modern_score=0.8,
             manufacturing_complexity="high", orientation="horizontal"),
    keywords=["pave name necklace", "diamond name necklace", "stone set arabic name", "thin name necklace",
              "white gold arabic name", "قلادة اسم الماس", "اسم مرصع"],
    lessons=[
        "Pavé setting needs strokes wide enough for a stone seat plus two walls (≈1.4 mm and up): thin-stroke calligraphy must be thickened for the stone version, not the plain version.",
        "The chain attaches at the first and last letter; a thin crossing bar stiffens the name without becoming the attachment.",
        "Stone-set names read best in white metal with an even stroke; ornament comes from the stones, not swashes.",
    ],
    evidence=[
        _ev("final_product", "a822fc15ecf2730ff151bda322da5466f2e2863fd00030f4ccc117af2823c467",
            1080, 2316, 449630, EXCLUDED_PERSONAL_DATA,
            "photo of the pavé name necklace worn on a person — not stored"),
    ],
)

LATIN_SCRIPT_NAME_BRACELET = _owner_case(
    "BS-GPC-0005-latin-script-name-bracelet",
    product_type="LATIN_SCRIPT_NAME_BRACELET", language="EN",
    layout_style="CONNECTED_CURSIVE_NAME", composition_type="BARE_CURSIVE_NAME",
    construction=["NAME_BODY_CONNECTED_CURSIVE", "RINGS_AT_NAME_ENDS", "LOBSTER_CLASP"],
    topology="NAME_BODY+RINGS_AT_NAME_ENDS", attachment_topology="CHAIN_RINGS_AT_FIRST_AND_LAST_LETTER",
    attachment_points=[{"position": "first_letter", "kind": "ring", "load": "chain"},
                       {"position": "last_letter", "kind": "ring", "load": "chain"}],
    chain_topology="BRACELET_CHAIN_WITH_LOBSTER_CLASP", material="gold_tone_metal", finish="polished", stones=None,
    dna=_dna(product_type="bracelet", script_family="latin_script", calligraphy_style="connected_cursive",
             composition="horizontal", shape_envelope="wide_horizontal", construction="openwork",
             stroke_character="clean_even_weight", swashes="present", tails="curved_terminal", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="rings_at_name_ends", chain_attachment="name_end_rings",
             stones="none", ornament="minimal", geometry_density="low", luxury_score=0.6, minimal_score=0.85,
             heritage_score=0.1, modern_score=0.8, manufacturing_complexity="low", orientation="horizontal"),
    keywords=["name bracelet", "cursive name bracelet", "script bracelet", "english name bracelet",
              "gold name bracelet", "سوار اسم", "اسوارة اسم"],
    lessons=[
        "A connected cursive name is one closed piece by construction — every letter joins the next — so it needs no bridges and lies flat on the wrist.",
        "The chain attaches through small rings at the first and last letter; the name itself is the bracelet's centre link.",
        "Bracelet length follows the wrist size guide (16–21 cm); the name width is subtracted from the chain length, not added.",
    ],
    evidence=[_ev("final_product", "0f9fb8e74a3ba229df11af6f706ef6dbf98f17f01043c2d40fa5971ee79519fc",
                  2268, 4032, 533528, PENDING_OBJECT_STORE,
                  "product photo on a black box — docs/reference/owner-samples/14-latin-script-name-bracelet-product.jpg"),
        _ev("final_product", "a830c3dfa9286a687954e78d04d05a9e8072f8b6083fdf4eb5f1e674fcd73d42", 2268, 4032, 497082,
            PENDING_OBJECT_STORE, "same script name bracelet in its gift box"),
        _ev("final_product", "1b9383513c633d7a7a295fd33e9e3fc261459d38a90b331b06246a4e97f83502", 2268, 4032, 886399,
            PENDING_OBJECT_STORE, "same script name bracelet laid on the box, clasp and end rings visible"),
    ],
)

OPEN_NAME_RING_WITH_HEART = _owner_case(
    "BS-GPC-0006-open-name-ring-heart-terminal",
    product_type="NAME_RING_OPEN_BAND", language="EN",
    layout_style="NAME_AS_RING_TOP", composition_type="OPEN_BAND_NAME_WITH_HEART",
    construction=["NAME_BODY_CONNECTED", "OPEN_BAND_CONTINUING_FROM_NAME", "HEART_TERMINAL"],
    topology="OPEN_BAND+NAME_BODY+HEART_TERMINAL", attachment_topology="NONE_RING",
    attachment_points=[], chain_topology=None, material="gold_tone_metal", finish="polished", stones=None,
    dna=_dna(product_type="ring", script_family="latin_script", calligraphy_style="bold_cursive",
             composition="horizontal", shape_envelope="curved_band", construction="openwork",
             stroke_character="bold_even_weight", swashes="present", tails="heart_terminal", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="none", chain_attachment="none", stones="none",
             ornament="heart", geometry_density="medium", luxury_score=0.5, minimal_score=0.6, heritage_score=0.1,
             modern_score=0.8, manufacturing_complexity="medium", orientation="horizontal"),
    keywords=["name ring", "open ring name", "cursive name ring", "heart name ring", "adjustable name ring",
              "خاتم اسم", "خاتم اسم مفتوح"],
    lessons=[
        "An open band lets the name sit on top and the two band ends overlap — the ring adjusts without a size cut and the name never has to close into a circle.",
        "A heart (or another small charm) terminates the band end and hides the free end of the wire.",
        "Bold connected letters are needed at ring scale; thin script would flex.",
    ],
    evidence=[_ev("final_product", "e4ac5892ecc70bcd46d2ab4dded76b640a943d0efae176b31b16fc1bf0e4179d",
                  2268, 4032, 410822, PENDING_OBJECT_STORE,
                  "product photo — docs/reference/owner-samples/15-open-name-ring-heart-product.jpg")],
)

ENAMEL_CALLIGRAPHY_CUFFLINKS = _owner_case(
    "BS-GPC-0007-enamel-calligraphy-cufflinks",
    product_type="CALLIGRAPHY_CUFFLINKS_ENAMEL", language="AR",
    layout_style="NAME_IN_ROUND_ENAMEL_FIELD", composition_type="ROUND_PLATE_ENAMEL_FIELD_RAISED_CALLIGRAPHY",
    construction=["ROUND_PLATE", "RAISED_POLISHED_CALLIGRAPHY", "BLACK_ENAMEL_FIELD", "RIM", "CUFFLINK_BACK"],
    topology="ROUND_PLATE+RIM+ENAMEL_FIELD+RAISED_CALLIGRAPHY+CUFFLINK_BACK", attachment_topology="CUFFLINK_TOGGLE_BACK",
    attachment_points=[{"position": "plate_back_centre", "kind": "cufflink_toggle", "load": "cuff"}],
    chain_topology=None, material="silver_tone_metal", finish="polished_with_black_enamel",
    stones=None,
    dna=_dna(product_type="cufflinks", audience="men", material="silver", metal_color="silver",
             script_family="diwani", calligraphy_style="compact_calligraphic", composition="medallion",
             shape_envelope="round", construction="relief", stroke_character="modulated_calligraphic",
             swashes="present", tails="curled", symmetry="paired", negative_space="filled_enamel", frame="rim",
             bail_loops="none", chain_attachment="none", stones="none", enamel="black_field", ornament="none",
             geometry_density="high", luxury_score=0.75, minimal_score=0.5, heritage_score=0.7, modern_score=0.5,
             manufacturing_complexity="high", orientation="round"),
    keywords=["cufflinks", "arabic cufflinks", "enamel cufflinks", "men calligraphy", "name cufflinks",
              "كبك", "كبك اسم", "كبك مينا"],
    lessons=[
        "Men's calligraphy works as a round plate: the name is raised and polished, the field is black enamel — the letters do not need to be self-supporting because the plate carries them.",
        "A rim protects the enamel edge; the cufflink back attaches to the plate, not to the letters.",
        "Compact, curled calligraphy fills a round field better than a horizontal name.",
    ],
    evidence=[_ev("final_product", "f9d3d8e10d9d2c5869fd8c1b9aa6501a2ad20642fbd80b4a3e91552748cf678e",
                  2268, 4032, 630003, PENDING_OBJECT_STORE,
                  "product photo of the pair — docs/reference/owner-samples/16-enamel-calligraphy-cufflinks-product.jpg")],
)

_MARKETING_NOTE = "AI-composited Beyond Style product-line creative — merchandising memory (what the brand sells and how it is layered), never construction or dimension truth"

LAYERED_CHARM_NECKLACE_LINE = _owner_case(
    "BS-GPC-0008-layered-charm-and-calligraphy-necklace-line",
    product_type="LAYERED_CHARM_CALLIGRAPHY_NECKLACE_SET", language="AR",
    layout_style="LAYERED_TWO_CHAINS_WITH_CHARMS", composition_type="CALLIGRAPHY_MEDALLION_OR_PLATE_PLUS_CHARMS",
    construction=["TWO_CHAIN_LAYERING", "CALLIGRAPHY_MEDALLION_OR_PHRASE_PLATE", "HANGING_CHARMS", "EVIL_EYE_ELEMENT",
                  "LARIAT_DROP", "BEADED_CHAIN_STATIONS"],
    topology="CHAIN_LAYERS+CENTRE_CALLIGRAPHY+HANGING_CHARMS", attachment_topology="UPPER_RINGS_PLUS_LOWER_CHARM_LOOPS",
    attachment_points=[{"position": "plate_top", "kind": "rings", "load": "chain"},
                       {"position": "plate_bottom", "kind": "loops", "load": "charms"}],
    chain_topology="TWO_LAYERED_CHAINS", material="gold_tone_metal", finish="polished",
    stones={"type": "evil_eye_glass_or_enamel", "placement": "charms_and_chain_stations"},
    dna=_dna(product_type="necklace", script_family="thuluth", calligraphy_style="dense_classical",
             composition="medallion", shape_envelope="round_or_plate", construction="openwork",
             stroke_character="modulated_calligraphic", swashes="present", tails="curled", symmetry="centred",
             negative_space="dense", frame="circle_or_plate", bail_loops="upper_rings_lower_charm_loops",
             chain_attachment="two_layered_chains", stones="evil_eye_accents", enamel="blue_evil_eye",
             ornament="charms", geometry_density="high", luxury_score=0.8, minimal_score=0.2, heritage_score=0.8,
             modern_score=0.5, manufacturing_complexity="high", orientation="round"),
    keywords=["layered necklace", "evil eye", "mashallah necklace", "medallion necklace", "lariat", "charms",
              "ما شاء الله", "عين زرقاء", "قلادة طبقات", "تعليقة"],
    lessons=[
        "The brand sells calligraphy as the centre of a layered set: a second chain with a small charm (moon, evil eye, dreamcatcher) frames the calligraphy piece.",
        "Phrase plates (ما شاء الله) carry charms on lower loops; a medallion keeps the calligraphy inside a rim.",
        "Evil-eye elements are glass/enamel components attached with rings — not cut from the sheet.",
    ],
    evidence=[
        _ev("style_reference", "ae86e75f7b09a03e47cbb29978c4d455caf9bd12ec38621100d6e4ce5e705ebc", 1122, 1402, 2242757, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — layered evil-eye lariat (05)"),
        _ev("style_reference", "00f9d9ea968fa69ecf9731f9e526534c7b4360720fd5dd262211b4ab58130e43", 1122, 1402, 2307132, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — moon charm + calligraphy medallion (06)"),
        _ev("style_reference", "5420c81751ab1ec8a3f24efb0c55aa3d66d07942d04c2439705c11988d326706", 1122, 1402, 2282955, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — dreamcatcher + phrase plate with hanging charms (07)"),
        _ev("style_reference", "3311ec9e2e68b2acefaf8a9020b752fad13315256ae82ffef40326c17066a232", 1122, 1402, 2249884, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — evil-eye station lariat with engraved oval (08)"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

LAYERED_NAME_SET_LINE = _owner_case(
    "BS-GPC-0009-layered-name-plate-set-line",
    product_type="LAYERED_NAME_PLATE_SET", language="EN",
    layout_style="THREE_CHAINS_THREE_NAMES", composition_type="NAME_PLATES_ON_SEPARATE_CHAINS",
    construction=["MULTI_CHAIN_LAYERING", "NAME_PLATE_PER_CHAIN", "ACCENT_CHAIN_WITH_STONES", "HEART_CHARM"],
    topology="THREE_CHAINS+ONE_NAME_PER_CHAIN", attachment_topology="RINGS_AT_NAME_ENDS_PER_CHAIN",
    attachment_points=[{"position": "name_ends", "kind": "rings", "load": "chain"}],
    chain_topology="THREE_LAYERED_CHAINS_MIXED_METALS", material="gold_tone_metal", finish="polished",
    stones={"type": "small_stones", "placement": "accent chain and heart charm"},
    dna=_dna(product_type="necklace", script_family="latin_block", calligraphy_style="bold_block_capitals",
             composition="horizontal", shape_envelope="wide_horizontal", construction="plate",
             stroke_character="bold_even_weight", swashes="absent", tails="none", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="rings_at_name_ends", chain_attachment="name_end_rings",
             stones="accent", ornament="heart", geometry_density="low", luxury_score=0.6, minimal_score=0.7,
             heritage_score=0.1, modern_score=0.9, manufacturing_complexity="low", orientation="horizontal"),
    keywords=["layered name necklace", "family names necklace", "three names", "name plate", "block letters",
              "سلاسل أسماء", "طقم أسماء", "أسماء العائلة"],
    lessons=[
        "A family set is one name per chain, each a self-contained plate with rings at its ends — the platform's single-name pendant repeated, not one multi-name piece.",
        "Mixed metal colours (yellow / white / rose) tell the names apart on the neck; the Meta ad version uses thin Arabic script per chain (مريم / نجلاء / عائشة as shown in the creative, unverified).",
    ],
    evidence=[
        _ev("style_reference", "229686664496398adda52136f56083d5095fef6679438713d2906bceac3b0f4f", 1122, 1402, 2105713, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — three block-capital name plates on three chains (09)"),
        _ev("style_reference", "ee0b7a64da9c82160c4cd7f032136ddecbe1c70d68ccd7d91dc8af3367615bfe", 1080, 2316, 470156, EXCLUDED_PERSONAL_DATA,
            "Meta 'Design ad' screenshot: three thin Arabic names on three coloured chains held by a model — ads-manager UI and face; not stored"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

CUSTOM_CHARM_BRACELET_LINE = _owner_case(
    "BS-GPC-0010-custom-charm-bracelet-line",
    product_type="CUSTOM_CHARM_BRACELET", language="EN",
    layout_style="TWO_ENGRAVED_CHARMS_ON_CHAIN", composition_type="SILHOUETTE_CHARMS_WITH_ENGRAVED_NAMES",
    construction=["SILHOUETTE_CHARM", "ENGRAVED_NAME_ON_CHARM", "RINGS_BETWEEN_CHARMS", "BRACELET_CHAIN"],
    topology="CHAIN+CHARM+RING+CHARM+CHAIN", attachment_topology="RINGS_AT_CHARM_ENDS",
    attachment_points=[{"position": "charm_ends", "kind": "rings", "load": "chain"}],
    chain_topology="BRACELET_CHAIN", material="gold_tone_metal", finish="polished", stones=None,
    dna=_dna(product_type="bracelet", script_family="latin_script", calligraphy_style="engraved_script",
             composition="horizontal", shape_envelope="charm_silhouettes", construction="engraving",
             stroke_character="engraved_line", swashes="present", tails="curved_terminal", symmetry="asymmetric",
             negative_space="open", frame="silhouette", bail_loops="rings_at_charm_ends", chain_attachment="charm_end_rings",
             stones="none", ornament="figurative_charms", geometry_density="low", luxury_score=0.5, minimal_score=0.6,
             heritage_score=0.1, modern_score=0.8, manufacturing_complexity="medium", orientation="horizontal"),
    keywords=["charm bracelet", "cat charm", "baby feet", "engraved name charm", "kids bracelet", "pet name",
              "سوار قطة", "أقدام أطفال", "سوار مخصص"],
    lessons=[
        "Names can be ENGRAVED on a silhouette charm (cat, baby feet) instead of cut as outlines — a second construction family the engraving profile already models.",
        "Charms join each other and the chain through rings at their ends; the silhouette must leave metal at those ends.",
    ],
    evidence=[_ev("style_reference", "fa848ab421630bfd49e56837f969dad357939aaba710e024aa0eb13729da7f38", 1122, 1402, 2220461, PENDING_OBJECT_STORE, _MARKETING_NOTE + " — cat + baby-feet engraved charm bracelet (10)")],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)


# ---------------------------------------------------------------------------
# Owner sample batch 2 (2026-09-10): keychains, cut-out disc, brooches, lariat
# letters, men's chain catalogue. Same rules: no text is read off any photo,
# names/dates engraved for a customer are personal data (hash only).
# ---------------------------------------------------------------------------

ENGRAVED_DISC_KEYCHAIN = _owner_case(
    "BS-GPC-0011-engraved-calligraphy-disc-keychain",
    product_type="ENGRAVED_DISC_KEYCHAIN", language="AR",
    layout_style="PHRASE_OR_NAME_ENGRAVED_ON_SOLID_DISC", composition_type="RELIEF_ON_SOLID_PLATE",
    construction=["SOLID_DISC", "RELIEF_OR_ENGRAVED_CALLIGRAPHY", "DARKENED_RECESS", "TOP_RING", "SPLIT_KEYRING"],
    topology="SOLID_DISC+TOP_RING+SPLIT_RING",
    attachment_topology="SINGLE_TOP_RING_TO_SPLIT_KEYRING",
    attachment_points=[{"position": "top_center", "kind": "integrated_ring", "load": "keyring"}],
    chain_topology="SPLIT_RING_ONLY",
    material="brass_or_925_silver_plated", finish="polished_face_darkened_recess", stones=None,
    dna=_dna(product_type="keychain", audience="unisex", material="silver", metal_color="silver",
             script_family="thuluth", calligraphy_style="classical_thuluth_relief", composition="stacked",
             shape_envelope="circle", construction="relief", stroke_character="modulated_calligraphic",
             swashes="present", tails="curled_inside_disc", symmetry="asymmetric", negative_space="dense",
             frame="circular_rim", bail_loops="top_ring", chain_attachment="split_ring", ornament="minimal",
             geometry_density="high", luxury_score=0.5, minimal_score=0.5, heritage_score=0.8, modern_score=0.3,
             manufacturing_complexity="low", orientation="square"),
    keywords=["keychain", "keyring", "engraved disc", "calligraphy keychain", "thuluth disc", "name keychain",
              "date engraving", "ميدالية", "ميدالية مفاتيح", "حفر"],
    lessons=[
        "On a solid engraved disc the plate carries the text, so connectivity, bridge and minimum-gap rules do not apply — only engraving line width and depth do; text can be far denser than any cut-out design.",
        "A darkened (oxidised/enamel-filled) recess is what makes dense Thuluth legible at 25–35 mm; the raised calligraphy is polished, the ground is dark.",
        "A name plus a date is a common engraving brief; the date is customer text too and must go through the same exact-text confirmation as the name.",
        "The only structural point is the top ring; it must be part of the outline (integrated), not soldered on after engraving.",
    ],
    evidence=[
        _ev("final_product", "1b84fa6b5d6098f83ebcc298185d8941c3f7aeba7392e3dcc80d0f74029f1c5c", 1200, 1600, 117374,
            PENDING_OBJECT_STORE, "engraved Thuluth phrase disc keychain on a dark field — phrase content not transcribed"),
        _ev("final_product", "f4eaea54558e89964a3e423fa17cf2dc1f1ef09ee35cf0cc7b52e423b70845cb", 1086, 1448, 1640001,
            EXCLUDED_PERSONAL_DATA, "engraved name + date disc keychain — customer name and date visible; hash only"),
    ],
)

CUTOUT_NAME_DISC_WITH_HEART_AND_DATE = _owner_case(
    "BS-GPC-0012-cutout-name-disc-heart-date",
    product_type="CUTOUT_NAME_DISC_PENDANT", language="AR",
    layout_style="NAME_PIERCED_IN_DISC_WITH_HEART_AND_DATE", composition_type="PIERCED_DISC_WITH_RIM",
    construction=["SOLID_RIM_DISC", "PIERCED_NAME_BODY", "HEART_CUTOUT", "ENGRAVED_DATE_LINE", "TOP_RING", "HALLMARK_925"],
    topology="RIM_DISC+PIERCED_NAME+HEART+ENGRAVED_DATE",
    attachment_topology="SINGLE_TOP_RING",
    attachment_points=[{"position": "top_center", "kind": "integrated_ring", "load": "chain_or_keyring"}],
    chain_topology="SINGLE_TOP_RING",
    material="925_silver", finish="polished", stones=None,
    dna=_dna(product_type="pendant", audience="women", material="silver", metal_color="silver",
             script_family="naskh", calligraphy_style="modern_naskh_pierced", composition="stacked",
             shape_envelope="circle", construction="openwork", stroke_character="uniform",
             swashes="absent", tails="short", symmetry="asymmetric", negative_space="open",
             frame="circular_rim", bail_loops="top_ring", chain_attachment="top_ring", ornament="heart",
             geometry_density="medium", luxury_score=0.5, minimal_score=0.6, heritage_score=0.4, modern_score=0.7,
             manufacturing_complexity="medium", orientation="square"),
    keywords=["cut out disc", "pierced name disc", "name disc pendant", "heart cutout", "date pendant",
              "925 silver name", "قرص اسم", "قلادة دائرية", "قلب"],
    lessons=[
        "Piercing a name inside a rim: every letter must connect to the rim or to a neighbour — counters that would fall out (closed loops of ه, م, و) need a bridge planned in the outline.",
        "A heart cut-out is a second pierced island; it must not weaken the rim below the minimum bridge width.",
        "A date can be engraved on the rim instead of pierced — mixing pierced name + engraved date keeps the disc strong.",
        "The hallmark (925) stamp needs a flat solid area reserved on the back.",
    ],
    evidence=[
        _ev("final_product", "e8ca9b1a5f0c208344b3e1ffb3104167eb7b07efb4dd07acd463176fdbd59f48", 1086, 1448, 1664717,
            EXCLUDED_PERSONAL_DATA, "pierced Arabic name disc with heart and engraved date — customer name/date visible; hash only"),
    ],
)

LARIAT_SEPARATED_LETTER_NECKLACE = _owner_case(
    "BS-GPC-0013-lariat-separated-letter-necklace",
    product_type="LARIAT_LETTER_NECKLACE", language="EN",
    layout_style="SEPARATE_LETTERS_AS_CHAIN_STATIONS_ON_LARIAT", composition_type="LETTER_STATIONS",
    construction=["INDIVIDUAL_LETTER_PLATES", "CHAIN_STATIONS", "LARIAT_DROP", "RING_PER_LETTER_END"],
    topology="LETTER_STATIONS+LARIAT_DROP",
    attachment_topology="EACH_LETTER_HAS_TWO_RINGS_INLINE_WITH_CHAIN",
    attachment_points=[{"position": "each_letter_left_and_right", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="LARIAT_WITH_LETTER_STATIONS",
    material="gold_tone_metal", finish="polished", stones=None,
    dna=_dna(product_type="necklace", script_family="latin", calligraphy_style="latin_serif_capitals",
             composition="horizontal", shape_envelope="linear_stations", construction="plate",
             stroke_character="uniform", swashes="absent", tails="none", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="two_rings_per_letter", chain_attachment="stations",
             ornament="minimal", geometry_density="low", luxury_score=0.6, minimal_score=0.8, heritage_score=0.2,
             modern_score=0.9, manufacturing_complexity="medium", orientation="portrait"),
    keywords=["lariat necklace", "letter stations", "separate letters", "initial necklace", "y necklace",
              "spaced letters", "قلادة حروف", "لاريات"],
    lessons=[
        "Letters can be separate plates strung as chain stations; each letter then needs two integrated rings and the chain carries the spacing — no connector metal between letters.",
        "Reading order on a lariat follows the chain, so the order of stations must be locked to the confirmed text order (LTR for Latin, RTL for Arabic when the piece is read facing the wearer).",
        "Station letters need a larger minimum stroke than a joined name because each one is a free-hanging part.",
    ],
    evidence=[
        _ev("style_reference", "2a8fca03bfa7070a5917ff9e0f22728c3cd22a85d0a430d7c399e828a3acf8cf", 1024, 1280, 88253,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — lariat with separate Latin letters as chain stations"),
        _ev("reference_image", "269ee801af8c56dee2aae5ecae50bb56ec0777460b5c8ec6738e61b1815c3b67", 716, 1600, 54536,
            EXCLUDED_PERSONAL_DATA, "WhatsApp screenshot of a third-party lariat: single Arabic letter station with pearl stations and a cord choker with letter + pearl, worn on a person — hash only, never copied"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

ENAMEL_ORCHID_BROOCH = _owner_case(
    "BS-GPC-0014-enamel-orchid-brooch",
    product_type="ENAMEL_FIGURATIVE_BROOCH", language="NONE",
    layout_style="FIGURATIVE_NO_TEXT", composition_type="FLAT_PLATE_WITH_ENAMEL_CELLS",
    construction=["FLAT_PLATE_SILHOUETTE", "ENAMEL_CELLS", "RAISED_CELL_WALLS", "PIN_BACK"],
    topology="PLATE+ENAMEL_CELLS+PIN_BACK",
    attachment_topology="PIN_BACK_ON_REVERSE",
    attachment_points=[{"position": "reverse_center", "kind": "soldered_pin_and_catch", "load": "pin"}],
    chain_topology="NONE",
    material="gold_tone_metal", finish="polished_with_purple_enamel", stones=None,
    dna=_dna(product_type="brooch", audience="women", script_family="none", calligraphy_style="none",
             composition="figurative", shape_envelope="organic", construction="plate", stroke_character="none",
             swashes="absent", tails="none", symmetry="asymmetric", negative_space="dense", frame="none",
             bail_loops="none", chain_attachment="pin_back", enamel="multi_cell_purple", ornament="floral",
             geometry_density="high", luxury_score=0.6, minimal_score=0.2, heritage_score=0.3, modern_score=0.6,
             manufacturing_complexity="medium", orientation="square"),
    keywords=["brooch", "enamel brooch", "orchid", "flower brooch", "pin", "بروش", "مينا", "زهرة"],
    lessons=[
        "Enamel needs closed cells: the vector must be drawn as walls (closed regions) — an open silhouette cannot hold enamel.",
        "The vector export used for cutting had the cell walls as the only cut geometry; colour is a finishing instruction, never geometry.",
        "A pin-back needs a solid area on the reverse; the front silhouette must leave that area unpierced.",
    ],
    evidence=[
        _ev("workshop_outline", "13d26340d2546f99de77e6392643174af59081e5103293079cf7c8b91bbc6653", 1122, 1402, 755955,
            PENDING_OBJECT_STORE, "vector export of the orchid brooch (cell walls only)"),
        _ev("final_product", "db3e5b604eb5017ffbe93ac926e46f12d1f920037344e1a809cf23bf8b783291", 182, 139, 7035,
            PENDING_OBJECT_STORE, "finished purple-enamel orchid brooch (thumbnail)"),
    ],
)

ARABIC_NAME_BAR_PIN_BROOCH = _owner_case(
    "BS-GPC-0015-arabic-name-bar-pin-brooch-hanging-disc",
    product_type="ARABIC_NAME_BAR_PIN_BROOCH", language="AR",
    layout_style="NAME_ON_PIN_BAR_WITH_HANGING_ENGRAVED_DISC", composition_type="BAR_PIN_WITH_DROP",
    construction=["NAME_BODY_ON_BAR", "PIN_BAR", "HANGING_ENGRAVED_DISC", "DROP_RING", "PIN_BACK"],
    topology="NAME_BAR+PIN_BACK+DROP_DISC",
    attachment_topology="PIN_BACK_PLUS_ONE_DROP_RING_UNDER_BAR",
    attachment_points=[{"position": "reverse_bar", "kind": "soldered_pin_and_catch", "load": "pin"},
                       {"position": "bar_bottom_center", "kind": "integrated_ring", "load": "drop_disc"}],
    chain_topology="SHORT_DROP_TO_DISC",
    material="gold_tone_metal", finish="polished", stones=None,
    dna=_dna(product_type="brooch", audience="women", script_family="diwani", calligraphy_style="flowing_diwani_influenced",
             composition="horizontal", shape_envelope="wide_horizontal", construction="openwork",
             stroke_character="modulated_calligraphic", swashes="present", tails="descender_below_bar",
             symmetry="asymmetric", negative_space="open", frame="baseline_bar", bail_loops="drop_ring",
             chain_attachment="pin_back", ornament="hanging_disc", geometry_density="medium", luxury_score=0.7,
             minimal_score=0.5, heritage_score=0.6, modern_score=0.6, manufacturing_complexity="medium",
             orientation="portrait"),
    keywords=["brooch", "name brooch", "hijab pin", "arabic name pin", "bar pin", "hanging disc", "بروش اسم",
              "دبوس", "دبوس حجاب"],
    lessons=[
        "A name can be carried on a pin bar (hijab/scarf pin): the bar is the structural member, the pin is on the reverse, and the name sits on top of the bar like the bar-pendant construction.",
        "A hanging engraved disc adds a second text surface (engraved, dense) under a pierced name (open, sparse) — two text processes in one piece, each with its own rule set.",
        "The drop ring must be at the bar's centre of gravity or the disc swings sideways.",
    ],
    evidence=[_ev("final_product", "db9db04c0dc8b7374bfdb16eefa2f91ab98259ea59361fa7728fd539ed201c18", 1980, 3520, 482326,
                  PENDING_OBJECT_STORE, "finished Arabic name bar-pin brooch with hanging engraved disc, photographed on a glove")],
)

ARABIC_NAME_NECKLACE_STONE_DOT_LINE = _owner_case(
    "BS-GPC-0016-arabic-name-necklace-stone-dot-line",
    product_type="ARABIC_NAME_NECKLACE", language="AR",
    layout_style="THIN_SCRIPT_NAME_WITH_STONE_DOT", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS", "STONE_AS_DOT"],
    topology="NAME_BODY+END_RINGS+STONE_DOT",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="SINGLE_CHAIN_THROUGH_END_RINGS",
    material="gold_tone_metal", finish="polished",
    stones={"type": "small_round_stone", "count": 1, "placement": "replaces_one_dot", "setting": "prong"},
    dna=_dna(product_type="necklace", script_family="naskh", calligraphy_style="thin_modern_naskh",
             composition="horizontal", shape_envelope="wide_horizontal", construction="openwork",
             stroke_character="thin_uniform", swashes="absent", tails="short", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="end_rings", chain_attachment="end_rings",
             stones="single_accent", ornament="minimal", geometry_density="low", luxury_score=0.6,
             minimal_score=0.9, heritage_score=0.4, modern_score=0.8, manufacturing_complexity="medium",
             orientation="portrait"),
    keywords=["arabic name necklace", "thin name necklace", "stone dot", "three names set", "minimal arabic name",
              "قلادة اسم عربي", "اسم رفيع", "نقطة حجر"],
    lessons=[
        "The brand's signature Arabic name look is a thin uniform stroke with one dot replaced by a prong-set stone; the stone seat must be planned as geometry (≈1.5 mm) and the surrounding stroke widened locally.",
        "The same ad shows a three-name layered set as a variant — one construction, three chain lengths.",
    ],
    evidence=[_ev("style_reference", "b5a9070a1c5f7568c8f0887067438449d61c9ba555cdc43c6cf220894564fc2d", 1122, 1402, 2117259,
                  PENDING_OBJECT_STORE, _MARKETING_NOTE + " — thin Arabic name with stone dot, insets of a three-name set")],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

_CHAIN_CATALOGUE_NOTE = "Beyond Style men's 925 silver chain catalogue creative — length/weight table as stated by the owner (OWNER_CATALOGUE_STATED, not measured on this platform)"

MENS_SILVER_CHAIN_CATALOGUE = _owner_case(
    "BS-GPC-0017-mens-925-silver-chain-catalogue",
    product_type="MENS_CHAIN_CATALOGUE", language="NONE",
    layout_style="NO_TEXT_PRODUCT", composition_type="CHAIN_ONLY",
    construction=["CURB_OR_ROPE_CHAIN", "LOBSTER_CLASP", "HALLMARK_925_TAG"],
    topology="CHAIN+CLASP",
    attachment_topology="CLASP_ONLY",
    attachment_points=[{"position": "ends", "kind": "lobster_clasp", "load": "closure"}],
    chain_topology="CONTINUOUS_CHAIN",
    material="925_silver", finish="polished", stones=None,
    dimensions={"source": "OWNER_CATALOGUE_STATED", "see": "app/data/wearability.json#chain_catalogue"},
    dna=_dna(product_type="chain", audience="men", material="silver", metal_color="silver", script_family="none",
             calligraphy_style="none", composition="none", shape_envelope="linear", construction="chain",
             stroke_character="none", swashes="absent", tails="none", symmetry="symmetric", negative_space="none",
             frame="none", bail_loops="none", chain_attachment="clasp", ornament="none", geometry_density="none",
             luxury_score=0.5, minimal_score=0.7, heritage_score=0.2, modern_score=0.7,
             manufacturing_complexity="low", orientation="portrait"),
    keywords=["men chain", "silver chain", "curb chain", "cuban chain", "chain weight", "chain length",
              "سلسلة رجالي", "سلسلة فضة", "وزن السلسلة"],
    lessons=[
        "Chain weight scales linearly with length within one profile (≈0.45–0.55 g/cm for the stated profiles); a name pendant's own weight must be added on top when quoting.",
        "Men's necklace lengths are sold at 55/60/65 cm and bracelets at 21 cm — these are the wearability defaults for the men's audience.",
    ],
    evidence=[
        _ev("style_reference", "753ab6e1ff0a4c371327e4ed6bab28f5690b5185de17526ab70730a4f8d4e2de", 1122, 1402, 2320140, PENDING_OBJECT_STORE, _CHAIN_CATALOGUE_NOTE + " — profile C160"),
        _ev("style_reference", "dde7a9c6b0711a543adde607caa464487d0c9b3ad24e4d59f3271561c65d89b2", 1122, 1402, 2190265, PENDING_OBJECT_STORE, _CHAIN_CATALOGUE_NOTE + " — profile GBD150"),
        _ev("style_reference", "656978e0783d52f5316e563d0589993b95e3395dc65ff43916b4a1448d9feec5", 1122, 1402, 2262632, PENDING_OBJECT_STORE, _CHAIN_CATALOGUE_NOTE + " — profile C200"),
        _ev("style_reference", "bb1f82373a68ea340a53465619c195eaf2646d5c5da247a7a43036edbb39b212", 1122, 1402, 2187061, PENDING_OBJECT_STORE, _CHAIN_CATALOGUE_NOTE + " — profile G150"),
        _ev("style_reference", "851179b796644fb880ba1449684132ede481613b124a2b685df4730c72f11078", 1122, 1402, 2243140, PENDING_OBJECT_STORE, _CHAIN_CATALOGUE_NOTE + " — profile C140"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

# ---------------------------------------------------------------------------
# Owner sample batch 3 (2026-09-10): five Beyond Style product-line creatives
# plus eleven third-party market photos (kids' name jewellery, men's
# calligraphy cufflinks). Third-party photos: rights are not ours, most show
# children or faces — hash only, construction lessons only, never copied.
# ---------------------------------------------------------------------------

CAR_MIRROR_HANGER_LINE = _owner_case(
    "BS-GPC-0020-car-mirror-hanger-line",
    product_type="CAR_MIRROR_HANGER", language="AR",
    layout_style="STACKED_PLATES_ON_HANGING_CHAIN", composition_type="VERTICAL_STACK_OF_LINKED_PLATES",
    construction=["FIGURATIVE_TOP_PLATE", "ARABIC_PHRASE_PLATE", "CALLIGRAPHY_NAME_PLATE", "NON_METAL_DROP",
                  "RING_BETWEEN_EACH_PLATE", "TOP_HANGING_CHAIN"],
    topology="CHAIN+PLATE+RING+PLATE+RING+PLATE+RING+DROP",
    attachment_topology="ONE_RING_TOP_AND_BOTTOM_OF_EVERY_PLATE",
    attachment_points=[{"position": "each_plate_top_center", "kind": "integrated_ring", "load": "plates_below"},
                       {"position": "each_plate_bottom_center", "kind": "integrated_ring", "load": "plates_below"}],
    chain_topology="SINGLE_HANGING_CHAIN_TO_LOOP",
    material="gold_tone_metal_with_wood_drop", finish="polished", stones=None,
    dna=_dna(product_type="hanger", audience="unisex", script_family="thuluth", calligraphy_style="thuluth_and_diwani_mixed",
             composition="stacked", shape_envelope="tall_vertical", construction="openwork",
             stroke_character="modulated_calligraphic", swashes="present", tails="stacked", symmetry="symmetric",
             negative_space="open", frame="none", bail_loops="ring_between_plates", chain_attachment="top_loop",
             ornament="figurative_hands_and_wood_drop", geometry_density="high", luxury_score=0.6, minimal_score=0.2,
             heritage_score=0.7, modern_score=0.5, manufacturing_complexity="high", orientation="portrait"),
    keywords=["car mirror hanger", "car hanging", "rear view mirror", "gift hanger", "phrase plate", "stacked plates",
              "تعليقة سيارة", "تعليقة مرايا", "هدية سيارة"],
    lessons=[
        "A hanger is a vertical stack: every plate needs an integrated ring at top-centre and bottom-centre, and the rings must sit on the vertical centre line or the stack twists.",
        "Load is cumulative — the top plate's bottom ring carries everything below it, so its bridge width must be sized for the whole stack, not one plate.",
        "Phrase plates are wide and short; calligraphic name plates are square-ish — the stack alternates widths deliberately to read as one composition.",
        "A non-metal drop (wood/stone) attaches with a ring through a drilled hole; it is not part of the cut geometry.",
        "A customer may ask for a car-brand logo as the bottom medallion — that is a third-party trademark: flag copyright/brand risk, never cut the logo without rights, and propose an inspired plain medallion or the customer's own initial instead.",
    ],
    evidence=[
        _ev("style_reference", "5e698d391e41dff049ccb0f441e08a0e6aa05639a7a2024468661e4b4fb97110", 1122, 1402, 2104035,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — car mirror hanger: hands-heart plate, phrase plate, name plate, wood drop"),
        _ev("style_reference", "04bc4d3d50701979e9c30569ac55d4b692600c8c92c9ee4f637ccaa786925654", 1254, 1254, 123881,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — car mirror hanger: calligraphy phrase plate with heart over a car-brand star medallion. BRAND RISK: the medallion reproduces a third-party automotive trademark; the platform flags logo requests as IP risk and offers a plain ring/medallion alternative"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

NAME_BRACELET_LINE = _owner_case(
    "BS-GPC-0021-name-bracelet-line",
    product_type="NAME_BRACELET", language="EN",
    layout_style="NAME_INLINE_WITH_HEART_OR_CHARM", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS", "HEART_TERMINAL_OR_CHARM_DROP", "CURB_OR_CABLE_CHAIN",
                  "LOBSTER_CLASP", "EXTENDER_TAG"],
    topology="CHAIN+RING+NAME+HEART/RING+CHAIN",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME_OPTIONAL_DROP_RING",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "chain_near_name", "kind": "jump_ring", "load": "birthstone_charm"}],
    chain_topology="SINGLE_CHAIN_THROUGH_END_RINGS_WITH_CLASP_AND_EXTENDER",
    material="gold_tone_metal", finish="polished",
    stones={"type": "birthstone_charm", "count": 1, "placement": "drop_from_chain_next_to_name", "setting": "bezel"},
    dna=_dna(product_type="bracelet", script_family="latin", calligraphy_style="block_capitals_or_brush_script",
             composition="horizontal", shape_envelope="wide_horizontal", construction="plate",
             stroke_character="uniform", swashes="present", tails="short", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="end_rings", chain_attachment="end_rings",
             stones="single_charm", ornament="heart", geometry_density="low", luxury_score=0.6, minimal_score=0.8,
             heritage_score=0.2, modern_score=0.9, manufacturing_complexity="low", orientation="portrait"),
    keywords=["name bracelet", "custom name bracelet", "block letter bracelet", "script bracelet", "birthstone bracelet",
              "heart bracelet", "curb chain bracelet", "سوار اسم", "سوار اسم مخصص", "حجر ميلاد"],
    lessons=[
        "Bracelet names are small (≈25–35 mm wide) so block capitals need ≥0.8 mm stroke and script needs a continuous baseline join — letters that touch only at hairlines fail on a bracelet.",
        "A heart can terminate the name and carry the right-hand ring, so the name itself keeps a clean end.",
        "A birthstone is a separate bezel charm on a jump ring next to the name — never set into the letters on a bracelet.",
        "Bracelets need a clasp plus extender tag; the tag is a stamped part, not cut geometry.",
    ],
    evidence=[
        _ev("style_reference", "74b88b5d7ea3bc03bfcca168a65fad992e04b5436f229f318a674deae8cdcd02", 1122, 1402, 2023511,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — block-capital name on curb chain with heart terminal"),
        _ev("style_reference", "55839d236338691e287bc46a78e7d16c89d4b875d98eb657ee33f68539b544a3", 1122, 1402, 1850896,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — brush-script name on cable chain with birthstone charm drop"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

NAME_NECKLACE_STATIONS_AND_DROPS_LINE = _owner_case(
    "BS-GPC-0022-name-necklace-pearl-stations-and-stone-drop-line",
    product_type="NAME_NECKLACE", language="AR",
    layout_style="NAME_OFFSET_PEARL_STATIONS_OR_STONE_DROP", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS", "PEARL_STATIONS_ON_CHAIN", "HEART_STONE_DROP", "CABLE_CHAIN"],
    topology="CHAIN(+PEARL_STATIONS)+RING+NAME+RING+CHAIN / NAME+HEART_LOOP+STONE_DROP",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME_OPTIONAL_DROP_UNDER_TERMINAL_HEART",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "terminal_heart_bottom", "kind": "integrated_ring", "load": "stone_drop"}],
    chain_topology="SINGLE_CHAIN_WITH_OPTIONAL_STATIONS",
    material="gold_tone_metal", finish="polished",
    stones={"type": "pearl_stations_or_heart_stone_drop", "count": "4 pearls or 1 heart stone", "placement": "on_chain_or_under_name", "setting": "bezel/prong"},
    dna=_dna(product_type="necklace", script_family="naskh", calligraphy_style="thin_naskh_or_monoline_latin_script",
             composition="horizontal", shape_envelope="wide_horizontal", construction="openwork",
             stroke_character="thin_uniform", swashes="present", tails="short", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="end_rings", chain_attachment="end_rings",
             stones="drop_or_stations", pearls="chain_stations", ornament="heart", geometry_density="low",
             luxury_score=0.7, minimal_score=0.8, heritage_score=0.3, modern_score=0.9,
             manufacturing_complexity="medium", orientation="portrait"),
    keywords=["arabic name necklace", "pearl station necklace", "name with pearls", "heart stone drop",
              "monoline name necklace", "offset name necklace", "عقد اسم عربي", "لؤلؤ", "قلب حجر"],
    lessons=[
        "The name can sit off-centre with pearl stations balancing the other side of the chain — stations are chain parts, not cut geometry, and the name still has two end rings.",
        "A monoline script name can end in a small heart loop whose bottom ring carries a prong-set heart stone — the heart loop must be a closed ring in the outline.",
        "Thin Arabic names on a necklace are at the minimum-stroke limit of the workshop profile; any thinner and the piece needs the pavé/bar construction instead.",
    ],
    evidence=[
        _ev("style_reference", "7d6e86da0b17ba55f7433e16f95facd59113711048fc48f55243bc29214981a7", 1122, 1402, 1917766,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — thin Arabic name offset on chain with four pearl stations"),
        _ev("style_reference", "ec07f9d9e150e5ad23f9e564297b6376c8051afd77c02bec830ba00ab5b41467", 1122, 1402, 2010104,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — monoline script name ending in a heart loop with a green heart-stone drop"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

_THIRD_PARTY_NOTE = "third-party market photo supplied by the owner as a style reference — rights not ours, artwork never copied, hash only"

KIDS_NAME_JEWELLERY_MARKET_REFERENCES = _owner_case(
    "BS-GPC-0018-kids-name-jewellery-market-references",
    product_type="KIDS_NAME_JEWELLERY", language="MIXED",
    layout_style="SHORT_NAME_WITH_CROWN_HEART_OR_ENAMEL_CHARM", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS", "CROWN_OR_HEART_ACCENT", "ENAMEL_CHARM_STATIONS", "FINE_CABLE_CHAIN"],
    topology="CHAIN+RING+NAME(+ACCENT)+RING+CHAIN",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="SINGLE_FINE_CHAIN_SHORT_LENGTH",
    material="gold_or_silver_market_samples", finish="polished", stones=None,
    dna=_dna(product_type="necklace", audience="kids", script_family="latin_or_naskh",
             calligraphy_style="rounded_script_or_bold_naskh", composition="horizontal",
             shape_envelope="wide_horizontal", construction="plate", stroke_character="bold_uniform",
             swashes="present", tails="short", symmetry="asymmetric", negative_space="open", frame="none",
             bail_loops="end_rings", chain_attachment="end_rings", enamel="charm_accents", ornament="crown_heart_enamel",
             geometry_density="low", luxury_score=0.4, minimal_score=0.6, heritage_score=0.2, modern_score=0.8,
             manufacturing_complexity="low", orientation="square", reference_confidence=0.6,
             copy_risk_indicators=["third_party_brand_watermark", "licensed_character_style_lettering"]),
    keywords=["kids name necklace", "baby bracelet", "children jewellery", "crown name", "enamel hearts",
              "kids arabic name", "matching necklace bracelet", "قلادة اسم اطفال", "سوار اطفال", "تاج"],
    lessons=[
        "Kids' pieces use short names in bold rounded lettering: stroke ≥1.0 mm and fully joined baselines so a small piece survives play; hairline scripts are rejected for the kids audience.",
        "Accents are a crown above the first letter, a heart after the last letter, or enamel charms as chain stations — always attached at the name ends, never hung from the middle of a letter.",
        "Necklace and bracelet are sold as a matching set from one outline scaled to two sizes; the bracelet scale must be re-checked against minimum stroke, not just shrunk.",
        "Lettering that imitates a licensed character/entertainment font is a copy risk — offer an inspired rounded script from the licensed library instead.",
    ],
    evidence=[
        _ev("style_reference", "0ac297f98c7b13f7db1ed50050172796544700e43ba606096119a3fd91fb8614", 736, 736, 41608, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — cursive name with enamel animal charm"),
        _ev("style_reference", "7edb8053ee62a4e0afaf894bd938384ab78bf8b323eecc629680d0951143ad44", 736, 1104, 47329, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — script name with crown and three enamel heart stations"),
        _ev("style_reference", "bf3cb0c47da59312acc651af47fec63d777809e77a0042e44626a49e175fe799", 736, 736, 142992, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — branded steel script name with crown and heart"),
        _ev("style_reference", "0340e63caf74a9a1cbed62ad9483d49b09265351262893a8fb68b78b3c888b8c", 736, 981, 84584, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — script name with pavé crown worn on a person; hash only"),
        _ev("style_reference", "e322eb939e577e7829ce74f140a824238ce87db935896073d7ccba3f8e634441", 736, 736, 45028, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — infant wrist with block name bracelet; hash only"),
        _ev("style_reference", "395b8cd632c5ca8e8d7e6ba8ed9c4b5815890523c7902733bf549000ffd6cb2e", 600, 600, 68562, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — toddler wearing a script name necklace; hash only"),
        _ev("style_reference", "ae04340ec8cb211505e65039a2c0e331b71ae165adf228f1591360b959488bc1", 736, 736, 48023, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — branded kids' Arabic name necklace + bracelet set on a child; hash only"),
        _ev("style_reference", "2ab8b01edbd71a4b991a88bd8fbd8476b162275763ca0ab6971ef623b4eb7cd0", 736, 919, 77573, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — child wearing a script name necklace with crown; hash only"),
        _ev("style_reference", "9590e1fc3298f9b87b91b5ce8aa0f964e6060a8b23011f1d4ec89a4013f21f70", 736, 1108, 40063, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — script name on curb-chain bracelet worn on an arm; hash only"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="THIRD_PARTY_NO_COPY",
    supplied_as="a third-party market reference",
)

MENS_CALLIGRAPHY_CUFFLINK_MARKET_REFERENCES = _owner_case(
    "BS-GPC-0019-mens-calligraphy-cufflink-market-references",
    product_type="MENS_CALLIGRAPHY_CUFFLINKS", language="AR",
    layout_style="NAME_AS_ROUND_RELIEF_DISC_OR_OPEN_MONOGRAM", composition_type="DISC_RELIEF_OR_OPENWORK_MONOGRAM",
    construction=["ROUND_DISC_WITH_RELIEF_NAME", "DARKENED_RECESS", "OPENWORK_CALLIGRAPHIC_MONOGRAM", "CUFFLINK_BACK"],
    topology="DISC+CUFFLINK_BACK / OPEN_MONOGRAM+CUFFLINK_BACK",
    attachment_topology="CUFFLINK_POST_ON_REVERSE",
    attachment_points=[{"position": "reverse_center", "kind": "soldered_post_and_toggle", "load": "cuff"}],
    chain_topology="NONE",
    material="925_silver_market_samples", finish="polished_with_darkened_recess", stones=None,
    dna=_dna(product_type="cufflinks", audience="men", material="silver", metal_color="silver",
             script_family="diwani", calligraphy_style="compact_diwani_monogram", composition="stacked",
             shape_envelope="circle_or_compact_blob", construction="relief", stroke_character="modulated_calligraphic",
             swashes="present", tails="curled_inside", symmetry="asymmetric", negative_space="dense",
             frame="circular_rim_or_none", bail_loops="none", chain_attachment="cufflink_post", ornament="minimal",
             geometry_density="high", luxury_score=0.7, minimal_score=0.5, heritage_score=0.7, modern_score=0.5,
             manufacturing_complexity="medium", orientation="square", reference_confidence=0.6,
             copy_risk_indicators=["third_party_brand_watermark"]),
    keywords=["cufflinks", "men cufflinks", "calligraphy cufflinks", "name cufflinks", "monogram", "round cufflink",
              "كبك", "أزرار أكمام", "كبك اسم"],
    lessons=[
        "Men's cufflinks carry a name either as relief on a solid darkened disc (dense, any script) or as an openwork monogram (must satisfy connectivity and ≥0.9 mm stroke because it is a free silhouette on a post).",
        "A compact stacked Diwani monogram reads well at 15–18 mm; horizontal Naskh does not fit a cufflink face.",
        "The cufflink post needs a solid pad on the reverse centre; an openwork monogram must have metal there.",
    ],
    evidence=[
        _ev("style_reference", "d50d71332d940ff87a241828f1ee64c9054b104b12d8af707bab9b605fbbdaaa", 640, 640, 34594, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — branded round relief-name cufflink on a darkened disc"),
        _ev("style_reference", "56e78e7a1866de96253cf86d504565b8feb123d53f5d6ca03dc1d6c596c7cbc4", 720, 717, 17864, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — openwork calligraphic monogram cufflink, origin unknown"),
        _ev("style_reference", "4e407d8290d76dc7261ec9c8cbfbd9726072cc8f5a0edce940b51797a49de115", 533, 768, 41145, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — round relief-calligraphy face on a black recess held in fingers (video frame), origin unknown; hash only"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="THIRD_PARTY_NO_COPY",
    supplied_as="a third-party market reference",
)


# ---------------------------------------------------------------------------
# Owner sample batch 4 (2026-09-10): the Beyond Style product catalogue PDF
# (ring / brooch / necklace pages with product codes and starting prices —
# transcribed into app/data/product_catalogue.json as OWNER_CATALOGUE_STATED),
# two more brand creatives, three third-party references and necklace
# length guides (wearability.json).
# ---------------------------------------------------------------------------

_CATALOGUE_NOTE = "screenshot of the Beyond Style personalised-jewellery catalogue PDF (owner-authored) — product codes, titles and starting prices transcribed to app/data/product_catalogue.json; sample names shown on products are not customer text"

OWNER_PRODUCT_CATALOGUE = _owner_case(
    "BS-GPC-0023-owner-product-catalogue-2026-09",
    product_type="PRODUCT_CATALOGUE", language="MIXED",
    layout_style="CATALOGUE_PAGES", composition_type="CATALOGUE",
    construction=["ENGRAVED_BAND_RINGS", "NAME_BROOCHES_WITH_DISC_DROPS", "NAME_NECKLACES_WITH_PRAYER_DISCS",
                  "OPEN_HEART_NAME_FRAMES", "CRESCENT_CALLIGRAPHY_PENDANTS", "LAYERED_SETS"],
    topology="SEE_PRODUCT_CATALOGUE_JSON",
    attachment_topology="PER_PRODUCT",
    attachment_points=[], chain_topology="PER_PRODUCT",
    material="925_silver_or_gold_plated", finish="per_product", stones=None,
    dimensions={"source": "OWNER_CATALOGUE_STATED", "see": "app/data/product_catalogue.json"},
    dna=_dna(product_type="catalogue", audience="unisex", script_family="mixed", calligraphy_style="mixed",
             composition="mixed", shape_envelope="mixed", construction="mixed", stroke_character="mixed",
             swashes="mixed", tails="mixed", symmetry="mixed", negative_space="mixed", frame="mixed",
             bail_loops="mixed", chain_attachment="mixed", ornament="mixed", geometry_density="mixed",
             luxury_score=0.6, minimal_score=0.5, heritage_score=0.6, modern_score=0.6,
             manufacturing_complexity="medium", orientation="portrait"),
    keywords=["catalogue", "product code", "price", "starting price", "rings", "brooches", "necklaces",
              "engraved ring", "prayer disc", "ayat al kursi disc", "open heart name", "crescent name",
              "كتالوج", "خواتم", "بروشات", "قلادات", "سعر يبدأ من"],
    lessons=[
        "Rings are an engraving product family: text goes on the outer band (relief on darkened enamel or engraved) with an optional inner engraving; no cut-out geometry rules apply, only band width vs. text height.",
        "Name brooches share the bar-pin construction and often carry a hanging engraved disc (word or prayer) — the disc is the brand's standard add-on across brooches and necklaces.",
        "Necklace families: flowing single name; two names joined by a heart; name with prayer disc below; open-heart frame around a name; crescent (hilal) carrying a name or phrase; layered 2–3 chain sets.",
        "Starting prices are per family (AED 165–495) and are owner-stated catalogue values — the platform quotes from them, it never invents a price.",
    ],
    evidence=[
        _ev("catalogue_page", "a168b0d2296ffeb780ee2fa3b9ed2ba82abdc4fd8e753d3b42125eae677b1a36", 1080, 2316, 895349, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — rings p.21"),
        _ev("catalogue_page", "3c504f657d9945879066cb49bceb6538413b44c220301e44cb79139e60e50ad2", 1080, 2316, 819850, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — rings p.20"),
        _ev("catalogue_page", "d58d01132fa9cf1c69741105c23fe17f57aee054db8a36e169466fa9956d0288", 1080, 2316, 676065, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — rings p.19"),
        _ev("catalogue_page", "a87ff7e2f833737113d55d96b77d3abf10d6d252d58cfa0eb775cb1b6f564afa", 1080, 2316, 713534, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — name brooches p.27"),
        _ev("catalogue_page", "41237e48ba7fb6d5eeba1d0a3de3e6b594006af118f75359f5736bc825c37bb6", 1080, 2316, 932478, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — necklaces p.7"),
        _ev("catalogue_page", "14b33cb1d175aee7abd050bfec491d3d6521e2f9522f96a621b8181bfe71a13b", 1080, 2316, 940520, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — necklaces p.5"),
        _ev("catalogue_page", "572bcdef3e682974134144815ed312f148cf12bd57f435aef2dbadc976210619", 1080, 2316, 924382, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — necklaces p.4"),
        _ev("catalogue_page", "f1dd6e7b45baa83750deb3c822053e9f764fcadd2e9fa313c86c60c5c59ac30d", 1080, 2316, 942295, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — necklaces p.8"),
        _ev("catalogue_page", "8a4dc277bc42a7a0505d15faa72fcd139d5c9affafe4b470c385c389a52d181f", 1080, 2316, 946530, PENDING_OBJECT_STORE, _CATALOGUE_NOTE + " — necklaces p.9"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False, supplied_as="the owner's product catalogue",
)

INTERTWINED_CALLIGRAPHY_NAME_PENDANT_LINE = _owner_case(
    "BS-GPC-0024-intertwined-calligraphy-name-pendant-line",
    product_type="ARABIC_CALLIGRAPHY_NAME_PENDANT", language="AR",
    layout_style="TALL_INTERTWINED_LETTERS_SELF_FRAMING", composition_type="STACKED_MONOGRAM_PENDANT",
    construction=["NAME_BODY_INTERTWINED", "SELF_FRAMING_SWASHES", "TOP_LOOP_FROM_ASCENDER", "THICK_PLATE"],
    topology="INTERTWINED_NAME+TOP_LOOP",
    attachment_topology="SINGLE_TOP_LOOP_FORMED_BY_ASCENDER",
    attachment_points=[{"position": "top_ascender", "kind": "integrated_loop", "load": "chain"}],
    chain_topology="SINGLE_CHAIN_THROUGH_TOP_LOOP",
    material="gold_tone_metal", finish="high_polish", stones=None,
    dna=_dna(product_type="pendant", script_family="diwani", calligraphy_style="diwani_jali_intertwined",
             composition="stacked", shape_envelope="tall_vertical", construction="openwork",
             stroke_character="heavy_modulated", swashes="dominant", tails="wrapped_around_body",
             symmetry="asymmetric", negative_space="dense", frame="self_framing", bail_loops="ascender_loop",
             chain_attachment="top_loop", ornament="none", geometry_density="high", luxury_score=0.9,
             minimal_score=0.2, heritage_score=0.8, modern_score=0.5, manufacturing_complexity="high",
             orientation="portrait"),
    keywords=["arabic name pendant", "calligraphy pendant", "diwani pendant", "intertwined name", "statement pendant",
              "large name pendant", "تعليقة اسم عربي", "تعليقة اسم", "ديواني جلي", "خط عربي"],
    lessons=[
        "A statement pendant uses heavy Diwani-jali strokes that wrap around the name so the swashes become the frame — every swash must rejoin the body (no free-ending hairlines) for the piece to be one connected plate.",
        "The chain loop is formed by the tallest ascender curling back on itself; it must be a closed ring in the outline and sit above the centre of gravity or the pendant hangs tilted.",
        "Thick plate (≈1.2–1.5 mm) plus wide strokes is what makes this style feel premium; the same outline at thin stroke reads as cheap and bends.",
    ],
    evidence=[_ev("style_reference", "d1142101b9f87a2188b04f2261e20d239c0d97d5b041321a2378446278564558", 1122, 1402, 1975793,
                  PENDING_OBJECT_STORE, _MARKETING_NOTE + " — large intertwined Arabic calligraphy name pendant held in hand (featured-name creative)")],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

PHRASE_ON_MESH_BRACELET_WITH_CHARMS = _owner_case(
    "BS-GPC-0025-phrase-plate-on-mesh-bracelet-with-charm-drops",
    product_type="PHRASE_PLATE_MESH_BRACELET", language="AR",
    layout_style="PHRASE_PLATE_MOUNTED_ON_MESH_BAND_WITH_DROPS", composition_type="PLATE_ON_BAND",
    construction=["PHRASE_PLATE", "MESH_BAND", "PLATE_MOUNTED_ON_BAND", "TWO_DROP_RINGS_UNDER_PLATE",
                  "HAMSA_CHARM", "EVIL_EYE_BEAD"],
    topology="MESH_BAND+PHRASE_PLATE+2_DROPS",
    attachment_topology="PLATE_FIXED_TO_BAND_PLUS_TWO_BOTTOM_DROP_RINGS",
    attachment_points=[{"position": "plate_reverse", "kind": "solder_or_rivet_to_band", "load": "band"},
                       {"position": "plate_bottom_left", "kind": "integrated_ring", "load": "hamsa_charm"},
                       {"position": "plate_bottom_right", "kind": "integrated_ring", "load": "evil_eye_bead"}],
    chain_topology="MESH_BAND_NO_CHAIN",
    material="silver_tone_metal", finish="polished", stones={"type": "glass_evil_eye_bead", "count": 1, "placement": "drop", "setting": "cap_and_ring"},
    dna=_dna(product_type="bracelet", audience="women", material="silver", metal_color="silver",
             script_family="ruqaa", calligraphy_style="bold_ruqaa_phrase", composition="horizontal",
             shape_envelope="wide_horizontal", construction="plate", stroke_character="bold_uniform",
             swashes="present", tails="short", symmetry="asymmetric", negative_space="open", frame="none",
             bail_loops="two_bottom_drop_rings", chain_attachment="mounted_on_band", ornament="hamsa_and_evil_eye",
             geometry_density="medium", luxury_score=0.5, minimal_score=0.4, heritage_score=0.7, modern_score=0.6,
             manufacturing_complexity="medium", orientation="landscape"),
    keywords=["mashallah bracelet", "phrase bracelet", "mesh bracelet", "hamsa", "evil eye", "charm drops",
              "ruqaa phrase", "سوار ما شاء الله", "سوار عبارة", "كف", "عين زرقاء"],
    lessons=[
        "A phrase plate can be mounted on a mesh band instead of hung from a chain: the plate needs no end rings, but its reverse must have a flat solid zone for fixing to the band.",
        "Charm drops hang from rings integrated at the plate's bottom edge — placed under thick letters, never under a hairline or a dot.",
        "Bold Ruqaa with joined baselines survives as a plate; the shadda/dots are kept as raised islands only because the plate is solid behind them.",
        "The same mesh-band mount carries a Latin script name or an Arabic name: the plate must be one connected piece with two flat feet on the reverse; free-hanging descenders and swashes are fine because the band, not a chain, takes the load.",
    ],
    evidence=[
        _ev("style_reference", "499857f32661c5bcb8c6f3db1a95f8b69b47d22fca58fc76ba2bcb9904fdbc33", 1448, 1086, 162352,
            PENDING_OBJECT_STORE, _MARKETING_NOTE + " — phrase plate on mesh band with hamsa and evil-eye drops"),
        _ev("final_product", "72d8867fccb7e0d7564e4f91b3c5b687fc07762b9ee9303efe73b587ac53de7c", 1200, 1600, 190198,
            PENDING_OBJECT_STORE, "finished gold and silver phrase-plate mesh bracelets on a display pillow (silver with hamsa + evil-eye drops)"),
        _ev("final_product", "2a6ca22883110c274c4885e107bfe65739c0bde4c22bc1acfbe26c50c2acb022", 1254, 1254, 2105633,
            PENDING_OBJECT_STORE, "studio product photo of the gold phrase-plate mesh bracelet on white"),
        _ev("final_product", "ca345faf77688c9b152cd93db29203a3ead9c5ffdd071fc17a19881f149229d3", 2268, 4032, 881973,
            PENDING_OBJECT_STORE, "two finished name plates (Latin script and Arabic) on gold mesh bands, held on a studio glove — same band construction as the phrase plate"),
        _ev("style_reference", "bb5af27318aa14cad2d7a64e8c6945855c483867ae5a9974adcf482605fdad4e", 2048, 2048, 2887110,
            EXCLUDED_PERSONAL_DATA, "same phrase plate with hamsa + evil-eye drops on a green mesh band worn on a wrist — provenance of the photo not established; hash only"),
    ],
    workshop_changes=["gold version made without drops; silver version carries the hamsa and evil-eye drops — the plate outline is identical, the drop rings are optional islands"],
)

MARKET_REFERENCES_PEARL_STRAND_AND_BAR = _owner_case(
    "BS-GPC-0026-market-references-pearl-strand-drop-and-engraved-bar",
    product_type="MARKET_REFERENCE_NECKLACE_AND_BAR", language="MIXED",
    layout_style="PEARL_STRAND_NAME_DROP_OR_ENGRAVED_ID_BAR", composition_type="MIXED",
    construction=["HALF_PEARL_STRAND_HALF_CHAIN", "NAME_STATION_ON_CHAIN_SIDE", "VERTICAL_PAVE_NAME_DROP",
                  "ENGRAVED_ID_BAR_TWO_END_HOLES", "BEZEL_STONE_STATION"],
    topology="PEARLS+CHAIN+NAME_STATION+DROP / CHAIN+BAR+BEZEL+CHAIN",
    attachment_topology="PER_ITEM",
    attachment_points=[{"position": "bar_ends", "kind": "drilled_hole", "load": "chain"}],
    chain_topology="MIXED",
    material="market_samples", finish="polished", stones={"type": "pave_or_single_bezel", "count": "n/a", "placement": "n/a", "setting": "n/a"},
    dna=_dna(product_type="necklace", script_family="naskh", calligraphy_style="thin_naskh_vertical_drop",
             composition="asymmetric", shape_envelope="asymmetric", construction="openwork",
             stroke_character="thin_uniform", swashes="absent", tails="short", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="stations", chain_attachment="stations",
             stones="pave_accent", pearls="half_strand", ornament="minimal", geometry_density="low",
             luxury_score=0.7, minimal_score=0.6, heritage_score=0.3, modern_score=0.8,
             manufacturing_complexity="medium", orientation="square", reference_confidence=0.5,
             copy_risk_indicators=["unknown_origin"]),
    keywords=["pearl strand name necklace", "half pearl necklace", "vertical name drop", "two names necklace",
              "engraved bar bracelet", "id bar", "bezel stone bracelet", "لؤلؤ", "سوار بار", "اسم عمودي"],
    lessons=[
        "Asymmetric necklaces can be half pearl strand / half chain with a small name station on the chain side and a vertical two-name drop at the centre — the drop reads top-to-bottom, so the stacking order is part of the confirmed text.",
        "An engraved ID bar is the simplest name bracelet: a slightly curved bar with a hole at each end; text is engraved, so the only geometry rule is the bar's curvature vs. engraving depth.",
    ],
    evidence=[
        _ev("style_reference", "9276cdafc09d7554c6a2bc5690128fe552257dec8a156667232e188bb639fe90", 735, 602, 38981, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — half pearl strand necklace with vertical pavé name drop worn on a person; hash only"),
        _ev("style_reference", "2583d0b5314e4c78729c50e62f98f556516a86d9d6bc715e7af63a3ac51f3ba6", 739, 1600, 52709, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — engraved curved ID bar bracelet with bezel stone station, origin unknown"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a market reference of unknown origin",
)

NECKLACE_LENGTH_GUIDES = _owner_case(
    "BS-GPC-0028-necklace-length-guides",
    product_type="WEARABILITY_REFERENCE", language="NONE",
    layout_style="NO_TEXT_PRODUCT", composition_type="SIZE_GUIDE",
    construction=["CHAIN_LENGTH_CHART"], topology="NONE", attachment_topology="NONE",
    attachment_points=[], chain_topology="NONE", material=None, finish=None, stones=None,
    dimensions={"source": "INDUSTRY_STANDARD_LENGTH_CHART", "see": "app/data/wearability.json#necklace_lengths_cm"},
    dna=_dna(product_type="chain", audience="unisex", script_family="none", calligraphy_style="none",
             composition="none", shape_envelope="none", construction="none", stroke_character="none",
             swashes="absent", tails="none", symmetry="none", negative_space="none", frame="none",
             bail_loops="none", chain_attachment="none", ornament="none", geometry_density="none",
             luxury_score=0.5, minimal_score=0.5, heritage_score=0.5, modern_score=0.5,
             manufacturing_complexity="low", orientation="portrait", reference_confidence=0.9),
    keywords=["necklace length", "chain length", "choker", "princess length", "size guide", "دليل طول السلاسل",
              "طول السلسلة"],
    lessons=[
        "Standard necklace lengths run 35 cm (choker) to 80 cm (rope); a name pendant reads best at 40–45 cm on women and 55–60 cm on men — the wearability score uses these bands.",
    ],
    evidence=[
        _ev("style_reference", "208b3b5126dfb898cb778a821ae3038e8079fa3ca230c7f1c665c4be56fa6027", 1080, 2316, 424899, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — third-party Instagram length-guide illustration (35–80 cm); values are industry standard"),
        _ev("style_reference", "a3abbeab31b421176159accd03d9768e62f8bc74b56fc8f14ca9b9374c08d1cb", 1080, 1329, 62307, EXCLUDED_THIRD_PARTY, _THIRD_PARTY_NOTE + " — same length-guide illustration, re-shared copy"),
        _ev("style_reference", "7aa5b6ecf1b3502ec7a8a577546844d5746ce84d25411c6a617b637651fa0ea3", 1077, 1089, 94564, EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — chain-length photo guide (16–30 in) on a person; hash only"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="THIRD_PARTY_NO_COPY",
    supplied_as="a third-party size guide",
)


# ---------------------------------------------------------------------------
# Owner sample batch 5 (2026-09-10): finished mesh bracelets (folded into
# BS-GPC-0025), a retail-display survey of stock Arabic name jewellery
# (photographed in a shop — design rights unknown, hash only, lessons only),
# and the Beyond Style packaging board.
# ---------------------------------------------------------------------------

_RETAIL_SURVEY_NOTE = "retail-display survey photo taken by the owner in a shop — stock pieces of unknown design rights; hash only, construction lessons only, sample names on the stock not transcribed"

RETAIL_SURVEY_STOCK_NAME_NECKLACES = _owner_case(
    "BS-GPC-0029-retail-survey-stock-arabic-name-necklaces",
    product_type="MARKET_REFERENCE_STOCK_NAME_NECKLACE", language="AR",
    layout_style="BOLD_STOCK_NAME_ON_FINE_CHAIN_SIZE_GRADED", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS_AT_HIGHEST_OUTER_POINTS", "FINE_CABLE_CHAIN", "SIZE_GRADE_TAG"],
    topology="CHAIN+RING+NAME+RING+CHAIN",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "chain"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="SINGLE_FINE_CHAIN",
    material="gold_plated_stock", finish="polished", stones=None,
    dna=_dna(product_type="necklace", script_family="kufi_naskh_hybrid", calligraphy_style="bold_stock_lettering",
             composition="horizontal", shape_envelope="wide_horizontal", construction="plate",
             stroke_character="bold_uniform", swashes="absent", tails="short", symmetry="asymmetric",
             negative_space="open", frame="none", bail_loops="end_rings", chain_attachment="end_rings",
             ornament="none", geometry_density="medium", luxury_score=0.3, minimal_score=0.7, heritage_score=0.5,
             modern_score=0.6, manufacturing_complexity="low", orientation="square", reference_confidence=0.7,
             copy_risk_indicators=["unknown_origin_stock"]),
    keywords=["stock name necklace", "ready made name necklace", "bold arabic name", "display stand", "size L M",
              "قلادة اسم جاهزة", "اسم عربي عريض"],
    lessons=[
        "Mass-market stock names use one bold uniform stroke (≈1.2–1.5 mm at 30–40 mm width) with every letter joined on a continuous baseline — that is why they survive plating and daily wear; the platform's bold recipes should sit in this stroke band.",
        "The chain rings are placed at the highest outer points of the first and last letter so the name hangs level; when a name ends in a low letter, the ring is added to a raised terminal stroke instead.",
        "Stock is graded L/M by name width (number of letters), not by chain length — the same construction is cut at two scales and re-checked for minimum stroke.",
        "Two-line and descender-heavy names (e.g. names with a final ى/ي or a tall initial) are cut as one plate with the descender free-hanging below the chain line.",
    ],
    evidence=[
        _ev("style_reference", "81dbeff324a7a74fa8ad22540bd9ce02012d93aa3b68be41fe78a078aaaa769e", 2992, 2992, 6480260, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — stand tagged L, pink velvet"),
        _ev("style_reference", "d55cec35127e8fddf02dbe044e8da721f305cb2f5995b82f599bb932c8528b92", 2992, 2992, 5776797, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — cream suede stand, names with the initial م"),
        _ev("style_reference", "1a1cd3ee27962f2e5b632e5d2bcb5f138ad394529f9af2f40eb39bbcccdf5803", 2992, 2992, 6381424, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — cream suede stand tagged H"),
        _ev("style_reference", "fdeb93c13730442c4f4805d3448933e9c96d7e186b4ddb48606813db1cf08047", 2992, 2992, 6512388, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — cream suede stand, names with the initial ن"),
        _ev("style_reference", "77ca57454a2c53dc0342cb4a5b010fd92007f684a19fddd756a9db9f8dae9b41", 2992, 2992, 6140355, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — stand tagged M"),
        _ev("style_reference", "83e13822e21af485629e6be22738698bcf86a00e6f05ca5738c17d7533b26ce6", 2992, 2992, 6376068, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — cream suede stand, close-up"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a retail-display survey",
)

RETAIL_SURVEY_ENGRAVED_BAR_PLATES = _owner_case(
    "BS-GPC-0030-retail-survey-engraved-bar-plates",
    product_type="MARKET_REFERENCE_ENGRAVED_BAR", language="MIXED",
    layout_style="NAME_ENGRAVED_ON_RECTANGULAR_BAR_TWO_HOLES", composition_type="ENGRAVED_PLATE",
    construction=["RECTANGULAR_BAR_PLATE", "ENGRAVED_NAME", "HOLE_AT_EACH_END", "DOUBLE_OR_SINGLE_CHAIN", "ROUND_DISC_VARIANT"],
    topology="CHAIN+HOLE+BAR+HOLE+CHAIN",
    attachment_topology="DRILLED_HOLE_AT_EACH_END",
    attachment_points=[{"position": "bar_left_end", "kind": "drilled_hole", "load": "chain"},
                       {"position": "bar_right_end", "kind": "drilled_hole", "load": "chain"}],
    chain_topology="SINGLE_OR_DOUBLE_CHAIN_THROUGH_END_HOLES",
    material="gold_plated_or_steel_stock", finish="mirror_polished", stones=None,
    dna=_dna(product_type="necklace", script_family="naskh_or_latin_script", calligraphy_style="engraved_naskh_or_copperplate",
             composition="horizontal", shape_envelope="wide_horizontal", construction="engraving",
             stroke_character="engraved_line", swashes="present", tails="short", symmetry="symmetric",
             negative_space="dense", frame="rectangular_plate", bail_loops="end_holes", chain_attachment="end_holes",
             ornament="none", geometry_density="low", luxury_score=0.4, minimal_score=0.9, heritage_score=0.3,
             modern_score=0.8, manufacturing_complexity="low", orientation="square", reference_confidence=0.7,
             copy_risk_indicators=["unknown_origin_stock"]),
    keywords=["bar necklace", "engraved bar", "name plate necklace", "rectangle plate", "double chain bar",
              "قلادة بار", "لوحة اسم محفورة", "نقش"],
    lessons=[
        "An engraved rectangular bar (≈35×12 mm) with a hole at each end is the cheapest name product: text is engraved so Arabic and Latin share one plate geometry and no cut-out rules apply.",
        "Arabic on a bar is engraved in a Naskh-like hand centred on the plate; Latin uses a copperplate script — both are engraving fonts, not the cut-out lettering library.",
        "A double chain through the same two holes is a styling variant with no geometry change; a round disc with a top hole is the same product family.",
    ],
    evidence=[
        _ev("style_reference", "9f761c280ec420a2ce6a9baa0fd2474de2f8163a1e1775426d69697c32943a0b", 2992, 2992, 6557800, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — engraved bars, gold and silver, plus round disc"),
        _ev("style_reference", "20533d10853e193feff9cc195b72bb20b8e49a65dc470f433c4b6d06ec6274bb", 2992, 2992, 6400740, EXCLUDED_THIRD_PARTY, _RETAIL_SURVEY_NOTE + " — engraved bars close-up, double chains"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a retail-display survey",
)

RETAIL_SURVEY_CORD_NAME_BRACELETS = _owner_case(
    "BS-GPC-0031-retail-survey-cord-name-bracelets",
    product_type="MARKET_REFERENCE_CORD_BRACELET", language="AR",
    layout_style="CUTOUT_NAME_BETWEEN_CORD_END_CAPS", composition_type="SINGLE_NAME_END_RINGS",
    construction=["NAME_BODY", "END_RINGS", "JUMP_RINGS", "CORD_END_CAPS", "COLOURED_TWISTED_CORD"],
    topology="CORD+CAP+RING+NAME+RING+CAP+CORD",
    attachment_topology="RINGS_AT_BOTH_ENDS_OF_NAME_TO_CORD_CAPS",
    attachment_points=[{"position": "name_left_end", "kind": "integrated_ring", "load": "cord_cap"},
                       {"position": "name_right_end", "kind": "integrated_ring", "load": "cord_cap"}],
    chain_topology="CORD_WITH_METAL_END_CAPS",
    material="gold_plated_stock_on_cord", finish="polished", stones=None,
    dna=_dna(product_type="bracelet", script_family="kufi_naskh_hybrid", calligraphy_style="bold_stock_lettering",
             composition="horizontal", shape_envelope="wide_horizontal", construction="plate",
             stroke_character="bold_uniform", swashes="absent", tails="descender_below_cord",
             symmetry="asymmetric", negative_space="open", frame="none", bail_loops="end_rings",
             chain_attachment="cord_caps", ornament="coloured_cord", geometry_density="medium", luxury_score=0.3,
             minimal_score=0.6, heritage_score=0.5, modern_score=0.7, manufacturing_complexity="low",
             orientation="square", reference_confidence=0.7, copy_risk_indicators=["unknown_origin_stock"]),
    keywords=["cord bracelet", "string bracelet", "name bracelet cord", "coloured cord", "kids name bracelet",
              "سوار خيط", "سوار اسم بخيط", "خيط ملون"],
    lessons=[
        "A cut-out name on a coloured cord needs the same two end rings as a chain bracelet; the cord terminates in metal caps with rings, so the name's ring size must accept a jump ring (≥1.2 mm inner diameter).",
        "Cord bracelets are sold in many cord colours from one metal outline — colour is a BOM option, never a geometry variant.",
        "Descenders hang below the cord line and are the first thing to bend on a bracelet; keep them ≥1.2 mm stroke or shorten them in the bracelet recipe.",
    ],
    evidence=[
        _ev("style_reference", "fd585f47030457c4af22860b9e70ec30d469e3c6b4d0081ceae796af3b190667", 2992, 2992, 4867989, EXCLUDED_PERSONAL_DATA, _RETAIL_SURVEY_NOTE + " — cord bracelet roll held in hand; hash only"),
        _ev("style_reference", "d7ee6e6c8e9daaaff7c4c2922e174cbfd74c1379da6e622e4ac31c65bae6fb47", 2992, 2992, 5921593, EXCLUDED_PERSONAL_DATA, _RETAIL_SURVEY_NOTE + " — cord bracelet roll held in hand; hash only"),
        _ev("style_reference", "5cac6c77df7a8e7e6e389efa3c15f96b932394a79b5003f95855bc5a215d049b", 2992, 2992, 5716660, EXCLUDED_PERSONAL_DATA, _RETAIL_SURVEY_NOTE + " — cord bracelet roll held in hand; hash only"),
        _ev("style_reference", "127d44575136cf4acd0c811bb1d3e6994b2c9ccd2091e940ebbfe2122ed57f4f", 2992, 2992, 5683440, EXCLUDED_PERSONAL_DATA, _RETAIL_SURVEY_NOTE + " — cord bracelet roll held in hand; hash only"),
        _ev("style_reference", "fa7252a2d6eed72981f891256ec7d98122e7fc27ba0240f304ea98a5c2e6ee4d", 2992, 2992, 4947156, EXCLUDED_PERSONAL_DATA, _RETAIL_SURVEY_NOTE + " — cord bracelet roll held in hand, close-up; hash only"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a retail-display survey",
)

PACKAGING_MATERIALS_BOARD = _owner_case(
    "BS-GPC-0032-packaging-materials-and-finishes-board",
    product_type="PACKAGING_REFERENCE", language="NONE",
    layout_style="NO_TEXT_PRODUCT", composition_type="BRAND_BOARD",
    construction=["RIGID_BOX", "VELVET_INSERT", "TISSUE", "RIBBON", "STICKER", "ROPE_HANDLE_BAG"],
    topology="NONE", attachment_topology="NONE", attachment_points=[], chain_topology="NONE",
    material="paper_board_velvet", finish="champagne_gold_foil", stones=None,
    dimensions={"source": "OWNER_BRAND_BOARD", "see": "app/data/product_catalogue.json#packaging"},
    dna=_dna(product_type="packaging", audience="unisex", script_family="none", calligraphy_style="none",
             composition="none", shape_envelope="none", construction="none", stroke_character="none",
             swashes="absent", tails="none", symmetry="none", negative_space="none", frame="none",
             bail_loops="none", chain_attachment="none", ornament="gold_foil_monogram", geometry_density="none",
             luxury_score=0.8, minimal_score=0.7, heritage_score=0.3, modern_score=0.8,
             manufacturing_complexity="low", orientation="square"),
    keywords=["packaging", "gift box", "velvet insert", "tissue paper", "ribbon", "foil stamping", "brand colours",
              "تغليف", "علبة هدايا", "شريط"],
    lessons=[
        "Brand palette is ivory / warm white / matte black / champagne gold; proof PDFs and the customer approval page should use the same palette so the on-screen proof matches the box the piece arrives in.",
        "The mood board extends the palette with deep blue and sand and positions the line as calligraphy medallions and signet rings for the modern Arab woman — a merchandising direction, not a construction rule.",
    ],
    evidence=[
        _ev("style_reference", "f8df3df3784f78c4857114b2047f7551df5479dff505a63c20aea5e2118b7ffe", 1254, 1254, 1167694,
            PENDING_OBJECT_STORE, "Beyond Style 'Materials & Finishes' packaging board (owner brand creative)"),
        _ev("style_reference", "e90e32adbd33512819f4cfafc16b6ec93ea2bf63c632fb5aa51f9f43fec462df", 5504, 3072, 20888152,
            PENDING_OBJECT_STORE, "'Beyond Jewellery' brand mood board — AI-composited model imagery (synthetic faces, not customers), calligraphy medallions and signet rings, palette gold / black / cream / deep blue / sand; not copied into docs because it carries faces"),
    ],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False, supplied_as="the owner's packaging brand board",
)


# ---------------------------------------------------------------------------
# Owner sample batch 6 (2026-09-10): relief cufflinks creative, letter-station
# bead necklace, vendor font tables / font comparison sheets, a framed
# calligraphy pendant and phrase-library screenshots.
# ---------------------------------------------------------------------------

RELIEF_CALLIGRAPHY_DISC_CUFFLINKS_LINE = _owner_case(
    "BS-GPC-0033-relief-calligraphy-disc-cufflinks-line",
    product_type="RELIEF_CALLIGRAPHY_CUFFLINKS", language="AR",
    layout_style="PHRASE_AS_RELIEF_ON_DARKENED_DISC", composition_type="DISC_RELIEF",
    construction=["ROUND_DISC", "RAISED_CALLIGRAPHY_RELIEF", "DARKENED_RECESS", "POLISHED_RIM", "CUFFLINK_BACK"],
    topology="DISC+RELIEF+CUFFLINK_BACK",
    attachment_topology="CUFFLINK_POST_ON_REVERSE",
    attachment_points=[{"position": "reverse_center", "kind": "soldered_post_and_toggle", "load": "cuff"}],
    chain_topology="NONE",
    material="925_silver_or_silver_tone", finish="polished_relief_oxidised_recess", stones=None,
    dna=_dna(product_type="cufflinks", audience="men", material="silver", metal_color="silver",
             script_family="thuluth", calligraphy_style="compact_thuluth_stacked", composition="stacked",
             shape_envelope="circle", construction="relief", stroke_character="modulated_calligraphic",
             swashes="present", tails="curled_inside_disc", symmetry="asymmetric", negative_space="dense",
             frame="circular_rim", bail_loops="none", chain_attachment="cufflink_post", ornament="minimal",
             geometry_density="high", luxury_score=0.7, minimal_score=0.5, heritage_score=0.8, modern_score=0.4,
             manufacturing_complexity="medium", orientation="square"),
    keywords=["cufflinks", "men cufflinks", "relief cufflinks", "calligraphy disc", "phrase cufflinks", "thuluth cufflinks",
              "كبك", "كبك خط عربي", "أزرار أكمام"],
    lessons=[
        "Relief on a solid disc is the men's calligraphy format: the raised text is polished, the recess darkened, and the rim stays a clean polished ring — no connectivity rule applies because the disc carries everything.",
        "A stacked Thuluth phrase fills a 16–18 mm disc; the same disc geometry serves cufflinks, ring faces and keychains.",
    ],
    evidence=[_ev("style_reference", "05efe79ba4d89f7678c94b7f74723c77fa857645213f17e3230597b328db8e8c", 1024, 1280, 127050,
                  PENDING_OBJECT_STORE, _MARKETING_NOTE + " — round relief calligraphy cufflinks with darkened recess on a shirt cuff")],
    evidence_tier="MARKETING_RENDER_UNMANUFACTURED", manufactured=False,
)

LETTER_STATIONS_BEAD_NECKLACE = _owner_case(
    "BS-GPC-0034-arabic-letter-stations-bead-necklace",
    product_type="LETTER_STATION_NECKLACE", language="AR",
    layout_style="THREE_SHORT_ARABIC_STATIONS_WITH_BEAD_STATIONS", composition_type="LETTER_STATIONS",
    construction=["SHORT_ARABIC_LETTER_OR_WORD_PLATES", "RING_PER_STATION_END", "BOX_CHAIN", "BEAD_STATIONS"],
    topology="CHAIN+BEADS+STATION+CHAIN+BEADS+STATION+CHAIN+STATION+CHAIN",
    attachment_topology="EACH_STATION_HAS_TWO_RINGS_INLINE_WITH_CHAIN",
    attachment_points=[{"position": "each_station_left_and_right", "kind": "integrated_ring", "load": "chain"}],
    chain_topology="BOX_CHAIN_WITH_LETTER_AND_BEAD_STATIONS",
    material="925_silver", finish="polished",
    stones={"type": "turquoise_bead", "count": 8, "placement": "paired_stations_on_chain", "setting": "threaded"},
    dna=_dna(product_type="necklace", material="silver", metal_color="silver", script_family="naskh",
             calligraphy_style="thin_naskh_letter_stations", composition="stations", shape_envelope="linear_stations",
             construction="openwork", stroke_character="thin_uniform", swashes="absent", tails="short",
             symmetry="asymmetric", negative_space="open", frame="none", bail_loops="two_rings_per_station",
             chain_attachment="stations", stones="bead_stations", ornament="minimal", geometry_density="low",
             luxury_score=0.5, minimal_score=0.8, heritage_score=0.4, modern_score=0.8,
             manufacturing_complexity="medium", orientation="portrait"),
    keywords=["station necklace", "letter stations", "initials necklace", "turquoise beads", "family initials",
              "three names necklace", "قلادة حروف", "حروف عائلة", "فيروز"],
    lessons=[
        "Several short Arabic words/letters can be separate stations on one chain, each with two integrated rings; bead pairs between stations set the spacing so the stations do not slide together.",
        "Station order along the chain is the reading order — it must be locked to the confirmed text order in the version lock, exactly like a multi-name layout.",
        "Thin single letters need a solid tail/loop to carry the ring; a lone dot can never be a station on its own.",
    ],
    evidence=[_ev("final_product", "2dd60816c76e1f9a9219d57df0846968cac6d969a312679ad36a339b9676b5c0", 720, 1280, 59141,
                  PENDING_OBJECT_STORE, "finished silver letter-station necklace with turquoise bead pairs on a display bust")],
)


FRAMED_CALLIGRAPHY_PLATE_MARKET_REFERENCE = _owner_case(
    "BS-GPC-0036-framed-calligraphy-plate-pendant-market-reference",
    product_type="MARKET_REFERENCE_FRAMED_PLATE", language="AR",
    layout_style="PHRASE_FILLING_RECTANGULAR_FRAME", composition_type="FRAMED_OPENWORK_PLATE",
    construction=["RECTANGULAR_FRAME", "PIERCED_CALLIGRAPHY_FILL", "TOP_RING", "CORD_WITH_BAIL"],
    topology="FRAME+PIERCED_FILL+TOP_RING",
    attachment_topology="SINGLE_TOP_RING_TO_BAIL",
    attachment_points=[{"position": "top_center", "kind": "integrated_ring", "load": "cord_bail"}],
    chain_topology="CORD_THROUGH_BAIL",
    material="silver_market_sample", finish="polished", stones=None,
    dna=_dna(product_type="pendant", material="silver", metal_color="silver", script_family="nastaliq",
             calligraphy_style="dense_nastaliq_texture", composition="framed", shape_envelope="tall_rectangle",
             construction="openwork", stroke_character="modulated_calligraphic", swashes="present",
             tails="interlocked", symmetry="asymmetric", negative_space="dense", frame="rectangular",
             bail_loops="top_ring", chain_attachment="bail", ornament="none", geometry_density="high",
             luxury_score=0.6, minimal_score=0.3, heritage_score=0.8, modern_score=0.6,
             manufacturing_complexity="high", orientation="portrait", reference_confidence=0.6,
             copy_risk_indicators=["third_party_brand_watermark"]),
    keywords=["framed calligraphy", "rectangle pendant", "poetry pendant", "nastaliq pendant", "cord pendant",
              "تعليقة مستطيلة", "خط نستعليق", "إطار"],
    lessons=[
        "A rectangular frame lets dense calligraphy be pierced as a texture: every stroke must touch the frame or a neighbour, so the frame is the structural member and the text can be as dense as legibility allows.",
        "Framed plates hang from a single top ring on a cord bail — a tall plate needs the ring on the centre line and a thickness ≥1.0 mm or it twists.",
    ],
    evidence=[_ev("style_reference", "4bf3290b4d0e80eac2b70eae9c18ded27ede2cc4b52cfa2a5a1fcdde234c2b6d", 1116, 1304, 165086,
                  EXCLUDED_PERSONAL_DATA, _THIRD_PARTY_NOTE + " — branded gallery watermark, framed pierced calligraphy plate on a cord worn on a person; hash only")],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="THIRD_PARTY_NO_COPY",
    supplied_as="a third-party market reference",
)

_FONT_SHEET_NOTE = "font comparison sheet supplied by the owner — one name set in many fonts; the fonts themselves are not identified or licensed here, so nothing is traced from the sheet"

VENDOR_FONT_TABLES_AND_COMPARISON_SHEETS = _owner_case(
    "BS-GPC-0037-vendor-font-tables-and-font-comparison-sheets",
    product_type="MARKET_REFERENCE_FONT_TABLE", language="MIXED",
    layout_style="ONE_NAME_IN_MANY_FONTS", composition_type="STYLE_PICKER_SHEET",
    construction=["NUMBERED_FONT_TABLE", "DEFAULT_FONT_RULE", "ORDER_NOTE_TEXT_CONFIRMATION"],
    topology="NONE", attachment_topology="NONE", attachment_points=[], chain_topology="NONE",
    material=None, finish=None, stones=None,
    dna=_dna(product_type="style_sheet", audience="unisex", script_family="mixed", calligraphy_style="mixed",
             composition="grid", shape_envelope="none", construction="none", stroke_character="mixed",
             swashes="mixed", tails="mixed", symmetry="none", negative_space="none", frame="none",
             bail_loops="none", chain_attachment="none", ornament="none", geometry_density="none",
             luxury_score=0.5, minimal_score=0.5, heritage_score=0.5, modern_score=0.5,
             manufacturing_complexity="low", orientation="landscape", reference_confidence=0.8,
             copy_risk_indicators=["unidentified_commercial_fonts"]),
    keywords=["font table", "font chart", "choose font", "default font", "font number", "style picker", "script fonts",
              "جدول خطوط", "اختيار الخط", "الخط الافتراضي"],
    lessons=[
        "Mass-market sellers let the customer pick a font by number from a fixed table and fall back to a default when no choice is given — the platform's style picker already does this with named, licensed styles; a numbered shortcut (1–16) is a valid customer-facing alias, never a new font source.",
        "The order note 'please note the text you need' is the sellers' version of exact-text confirmation; the platform requires the confirmed text before any proof, not as a free-text remark.",
        "A proof sheet showing one name in 12–16 fonts at equal size is the sellers' 'diverse options' step; the platform's 10 diverse proofs must differ in construction, not only in font.",
        "Latin script fonts on these sheets are unidentified commercial faces — they are references for the look (brush script, copperplate, slab, rounded sans), not sources: the platform renders only registry fonts with recorded rights.",
    ],
    evidence=[
        _ev("style_reference", "1c0292ef6102581160c213d23ef021d1aa3c9edb3626a4ffaae482307ee8618b", 1080, 1030, 67608, EXCLUDED_THIRD_PARTY, "third-party seller 'Arabic font table' (16 numbered fonts, default 5) — hash only (supplied twice)"),
        _ev("style_reference", "ad224ddd27f2f3598ddef1186f6802fc7a8fa94d20967bcb524647e36ea1a2ce", 861, 602, 51872, EXCLUDED_THIRD_PARTY, _FONT_SHEET_NOTE + " — one Arabic name in 13 Arabic fonts"),
        _ev("style_reference", "9138f490a619c50191fdee3fdc397d80222d2a502ef34fdb6e11bf3aa1c2d9a3", 1600, 900, 88274, EXCLUDED_THIRD_PARTY, _FONT_SHEET_NOTE + " — one short Latin name in 12 script/sans fonts"),
        _ev("style_reference", "d8d87f2ca7fdf8f519d2b41596e4df5a5064c33a1aaab04be751ebd1a9ff7bde", 1600, 900, 145988, EXCLUDED_THIRD_PARTY, _FONT_SHEET_NOTE + " — one long Latin name in 12 script/sans fonts"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a market font-table reference",
)

CALLIGRAPHY_PHRASE_LIBRARY_SCREENSHOTS = _owner_case(
    "BS-GPC-0038-calligraphy-phrase-library-screenshots",
    product_type="MARKET_REFERENCE_PHRASE_LIBRARY", language="AR",
    layout_style="PHRASE_AS_CIRCULAR_OR_FREE_THULUTH_COMPOSITION", composition_type="CALLIGRAPHY_ARTWORK",
    construction=["STACKED_THULUTH_COMPOSITION", "CIRCULAR_ENVELOPE", "HARAKAT_AS_ORNAMENT"],
    topology="NONE", attachment_topology="NONE", attachment_points=[], chain_topology="NONE",
    material=None, finish=None, stones=None,
    dna=_dna(product_type="artwork", audience="unisex", script_family="thuluth", calligraphy_style="classical_thuluth_composition",
             composition="stacked", shape_envelope="circle_or_free", construction="none",
             stroke_character="modulated_calligraphic", swashes="present", tails="interlocked", symmetry="asymmetric",
             negative_space="dense", frame="none", bail_loops="none", chain_attachment="none", harakat_style="full_ornamental",
             ornament="harakat", geometry_density="high", luxury_score=0.8, minimal_score=0.1, heritage_score=1.0,
             modern_score=0.2, manufacturing_complexity="high", orientation="square", reference_confidence=0.6,
             copy_risk_indicators=["third_party_vector_library", "sacred_text"]),
    keywords=["phrase library", "calligraphy artwork", "thuluth composition", "quran verse", "greeting phrase",
              "eid phrase", "مكتبة عبارات", "خط الثلث", "آية", "كل عام وأنتم بخير"],
    lessons=[
        "Phrase artworks from a calligraphy library are third-party vectors until their licence is recorded — they can inspire a composition envelope (circle, stacked) but are never cut as-is.",
        "One of the two screenshots is a Qur'anic verse: sacred text takes the enhanced path — no paraphrase, no generative rewriting, verified letter-by-letter against the canonical text, explicit approval before any proof.",
        "Full harakat drawn as ornament is a Thuluth-artwork convention; on jewellery each mark becomes a free island that must be bridged or dropped, and dropping harakat needs the customer's explicit confirmation.",
    ],
    evidence=[
        _ev("style_reference", "95c3fa18101e3065c91acfa8fc9a29ba446c0078388722bdeaec019f441855e0", 480, 618, 20928, EXCLUDED_THIRD_PARTY, "screenshot of a third-party calligraphy library entry — Qur'anic verse in a free Thuluth composition; hash only, sacred-text path"),
        _ev("style_reference", "3e44a45d6abb81987ef6f6c16a1b0041ee179679b9a33ef29eabe0ff2d8fcfe9", 569, 661, 34659, EXCLUDED_THIRD_PARTY, "screenshot of a third-party calligraphy library entry — greeting phrase in a circular Thuluth composition; hash only"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a third-party phrase-library reference",
)


# ---------------------------------------------------------------------------
# Owner sample batch 7 (2026-09-10): Top Style retail stock survey and
# supplier-catalogue renders (unknown rights) — lessons only, hash only.
# ---------------------------------------------------------------------------

_TOP_STYLE_NOTE = "third-party retail brand ('Top Style' carded stock, made in P.R.C.) photographed/collected by the owner as a market reference — rights not ours, never copied, hash only"

TOP_STYLE_RETAIL_STOCK_SURVEY = _owner_case(
    "BS-GPC-0039-top-style-retail-stock-survey",
    product_type="MARKET_REFERENCE_RETAIL_STOCK", language="AR",
    layout_style="STACKED_PHRASE_PENDANTS_PAVE_FRAMES_AND_SETS", composition_type="MIXED",
    construction=["STACKED_TWO_WORD_PENDANT_WITH_ENAMEL_OUTLINE", "BAIL_ON_TALLEST_STROKE", "PAVE_RECTANGULAR_FRAME_WITH_INNER_WORD",
                  "PAVE_WORD_WITH_STONE_DROP", "MATCHING_EARRING_AND_NECKLACE_SET", "FLOWING_PHRASE_WITH_END_RINGS",
                  "DOUBLE_CHAIN_WITH_FACETED_BEAD_STATIONS"],
    topology="MIXED",
    attachment_topology="PER_ITEM",
    attachment_points=[{"position": "frame_top_corners", "kind": "integrated_ring", "load": "chain"},
                       {"position": "tallest_stroke_top", "kind": "bail", "load": "chain"}],
    chain_topology="MIXED",
    material="brass_or_stainless_stock_plated", finish="polished_with_enamel_or_pave", stones={"type": "cz_pave_or_turquoise_pave", "count": "n/a", "placement": "frame_or_word", "setting": "bead_set"},
    dna=_dna(product_type="necklace", script_family="diwani", calligraphy_style="stacked_diwani_and_flowing_phrase",
             composition="stacked_or_framed", shape_envelope="mixed", construction="plate", stroke_character="bold_uniform",
             swashes="present", tails="interlocked", symmetry="asymmetric", negative_space="dense", frame="pave_rectangle_or_none",
             bail_loops="bail_or_end_rings", chain_attachment="mixed", stones="pave_accent", enamel="white_outline",
             ornament="stone_drop", geometry_density="high", luxury_score=0.4, minimal_score=0.3, heritage_score=0.5,
             modern_score=0.7, manufacturing_complexity="medium", orientation="square", reference_confidence=0.7,
             copy_risk_indicators=["third_party_brand_card", "mass_market_stock", "sacred_word_in_pave"]),
    keywords=["stacked phrase pendant", "enamel outline pendant", "pave frame", "allah pendant", "turquoise pave set",
              "earring necklace set", "double chain", "stainless phrase necklace", "قلادة عبارة", "طقم", "إطار مرصع"],
    lessons=[
        "Stacked two-word pendants read top-to-bottom and hang from a bail on the tallest vertical stroke; a thin white enamel outline along one word separates the two words visually without adding geometry — the outline is a recess in the plate, not a second part.",
        "A pavé rectangular frame with a word inside: the inner word must touch the frame at ≥ 2 points (or sit on a hidden bar) and the chain rings are at the frame's top corners, so the frame carries the load and the word can be delicate.",
        "The sacred word الله appears on mass-market stock as pavé inside a frame — on the platform it takes the sacred-text path (exact canonical spelling, no stylised distortion, enhanced verification, explicit approval).",
        "Matching earring + necklace sets are one word outline cut at two scales (≈ 12 mm and ≈ 30 mm); the earring scale must be re-checked for minimum stroke and gets a single post pad instead of end rings.",
        "Pavé words carry one small prong-set stone drop from the lowest stroke; turquoise-coloured pavé is a bead-set colour option, not a geometry change.",
        "Flowing multi-word phrases in a Diwani-like hand are sold as stainless stock with end rings on the first and last strokes — the phrase must be one connected outline; the platform's connectivity gate reproduces exactly that constraint.",
        "A double-layer chain with faceted bar-bead stations is a chain-only product (no text): stations are threaded parts, never cut geometry.",
    ],
    evidence=[
        _ev("style_reference", "94e45bc9d7aaf21eeb5718719c22a31682bc7a979833036aa35ffaa55ef05e2d", 1080, 2316, 921085, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — social story screenshot: double-layer chain with faceted bar-bead stations"),
        _ev("style_reference", "60e473730996a0e4e574793a38453a78a02b1dd880e03f20b252d10d4343c9c0", 2048, 2048, 1613569, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — catalogue render: flowing phrase necklace with end rings, silver tone"),
        _ev("style_reference", "145c1cdb894c2b3267f0e44717d8f4fba399034ffb14e3a480bcb7eab0220dbe", 2048, 2048, 1174539, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — catalogue render: stacked two-word pendant, white enamel outline, three stones, bail"),
        _ev("style_reference", "1074cb2c291bff1880703708563e3dd170937321109c34d5d7fd90a857641210", 2048, 2048, 2721839, EXCLUDED_PERSONAL_DATA, _TOP_STYLE_NOTE + " — same pendant on a model's neck ('Approx Size'); hash only"),
        _ev("style_reference", "9f0fef768ef0159184a21ec1dbbb2c70ad445246f1125db65c48cc26a6990c84", 2048, 2048, 2960461, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — same pendant in a gift box render"),
        _ev("style_reference", "9e35ed90d9f689ec9a4555b5cdd4b4692a9ffa55a37576999aa916003fb1ac94", 2992, 2992, 6589202, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — carded stock of the same pendant, held in hand"),
        _ev("style_reference", "876a2d252a57953df4a5659312185554245be275777d41a4f571b7c9bbad683a", 2992, 2992, 5648960, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — carded stock: pavé rectangular frame with pavé sacred word inside"),
        _ev("style_reference", "f5dc0fa370c01612d1bc3524a3ce47905d087cb2d129aa476e3d92e1057c998b", 2992, 2992, 6487644, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — carded stock: turquoise pavé word earrings + necklace set with stone drops, silver tone"),
        _ev("style_reference", "7175831f6bb82a627c10dfbdb6b00162c2d8ae4a64185e9430121d8ea214459e", 2992, 2992, 6130481, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — carded stock: same set in gold tone"),
        _ev("style_reference", "8731d40d6d205e381acca8e934e1f9433dd2b95ecbe9890f8341227ff6ba8523", 2992, 2992, 6854024, EXCLUDED_THIRD_PARTY, _TOP_STYLE_NOTE + " — carded stock: flowing phrase necklace, gold tone, 'MADE IN P.R.C' card"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="THIRD_PARTY_NO_COPY",
    supplied_as="a third-party retail stock survey",
)

_SUPPLIER_RENDER_NOTE = "supplier/marketplace product render of unknown origin supplied by the owner as a style reference — rights not established, never copied, hash only"

SUPPLIER_CATALOGUE_RENDERS_STRAP_CUFF_FRAME = _owner_case(
    "BS-GPC-0040-supplier-renders-leather-strap-rope-cuff-pave-frame",
    product_type="MARKET_REFERENCE_SUPPLIER_RENDERS", language="AR",
    layout_style="PHRASE_ON_STRAP_NAME_IN_CUFF_WORD_IN_FRAME", composition_type="MIXED",
    construction=["PHRASE_PLATE_RIVETED_ON_LEATHER_STRAP", "TWO_DROP_RINGS_UNDER_PLATE", "HAMSA_CHARM", "EVIL_EYE_BEAD",
                  "OPEN_ROPE_TWIST_CUFF", "PAVE_NAME_SPANNING_BETWEEN_CUFF_WIRES", "PAVE_HALO_FRAME_WITH_INNER_WORD"],
    topology="MIXED",
    attachment_topology="PER_ITEM",
    attachment_points=[{"position": "plate_reverse", "kind": "rivet_to_strap", "load": "strap"},
                       {"position": "name_both_ends", "kind": "soldered_to_cuff_wires", "load": "cuff"},
                       {"position": "word_to_frame", "kind": "two_contact_points", "load": "frame"}],
    chain_topology="STRAP_OR_CUFF_OR_CHAIN",
    material="plated_brass_market_samples", finish="polished_or_pave", stones={"type": "cz_pave", "count": "n/a", "placement": "name_or_frame", "setting": "bead_set"},
    dna=_dna(product_type="bracelet", script_family="diwani", calligraphy_style="bold_diwani_phrase_or_pave_name",
             composition="horizontal", shape_envelope="wide_horizontal", construction="plate", stroke_character="bold_uniform",
             swashes="present", tails="short", symmetry="asymmetric", negative_space="open", frame="rope_cuff_or_pave_rectangle",
             bail_loops="two_bottom_drop_rings", chain_attachment="strap_or_cuff", stones="pave", ornament="hamsa_and_evil_eye",
             geometry_density="medium", luxury_score=0.5, minimal_score=0.4, heritage_score=0.6, modern_score=0.7,
             manufacturing_complexity="medium", orientation="square", reference_confidence=0.6,
             copy_risk_indicators=["unknown_origin_render"]),
    keywords=["leather bracelet", "mashallah leather strap", "rope cuff", "bangle name", "pave name cuff", "pave frame",
              "love pendant frame", "سوار جلد", "أسورة اسم", "إسوارة مرصعة", "إطار"],
    lessons=[
        "A phrase plate can be riveted onto a leather strap with a buckle — the plate needs two flat feet for rivets and its drop rings hang below the strap edge so the charms swing free of the leather.",
        "An open rope-twist cuff can carry a pavé name spanning between the two twisted wires: the name is soldered at both ends to the wires, so the outline needs a straight solid terminal at each end and no free-hanging descender below the lower wire.",
        "A pavé halo frame with an inner word is the premium version of the frame construction: the frame carries the stones and the load; the inner word connects at two points and stays plain polished for contrast.",
    ],
    evidence=[
        _ev("style_reference", "dda25b3a0843d46c0ccd2a75dec758b8e22ea33902d8992a221a2a87cf1d89d4", 2048, 2048, 2343332, EXCLUDED_THIRD_PARTY, _SUPPLIER_RENDER_NOTE + " — pavé halo rectangular frame with an inner cursive word, gold"),
        _ev("style_reference", "9e97dd6ec603fbc1ff0f19143424bf0c4faff3439ae1236e190f7bc695b753b9", 2048, 2048, 2728325, EXCLUDED_THIRD_PARTY, _SUPPLIER_RENDER_NOTE + " — phrase plate on burgundy leather strap with hamsa + evil-eye drops"),
        _ev("style_reference", "122f0182ab3609cd7ad09888078aaa84c46b4a66c524aa03de0d72bf4b583438", 2048, 2048, 2541149, EXCLUDED_PERSONAL_DATA, _SUPPLIER_RENDER_NOTE + " — same leather strap on a wrist ('Approx Size'); hash only"),
        _ev("style_reference", "1902e4508b55a766fe257b08c49e9ef2ef5035cf633cf5c7bb035af4545eecb7", 2048, 2048, 2538322, EXCLUDED_THIRD_PARTY, _SUPPLIER_RENDER_NOTE + " — open rope-twist cuff with a pavé Arabic name spanning the wires"),
    ],
    evidence_tier="EXTERNAL_INSPIRATION", manufactured=False, rights_provenance="UNKNOWN_RIGHTS",
    supplied_as="a supplier-render market reference",
)


GOLDEN_PRODUCTION_CASES = [
    ARABIC_LETTER_PEARL_EARRINGS,
    LAYERED_NAME_NECKLACE_ADAM_OMAR,
    NAME_ON_BASELINE_BAR_PENDANT,
    PAVE_NAME_NECKLACE_ON_BAR,
    LATIN_SCRIPT_NAME_BRACELET,
    OPEN_NAME_RING_WITH_HEART,
    ENAMEL_CALLIGRAPHY_CUFFLINKS,
    LAYERED_CHARM_NECKLACE_LINE,
    LAYERED_NAME_SET_LINE,
    CUSTOM_CHARM_BRACELET_LINE,
    ENGRAVED_DISC_KEYCHAIN,
    CUTOUT_NAME_DISC_WITH_HEART_AND_DATE,
    LARIAT_SEPARATED_LETTER_NECKLACE,
    ENAMEL_ORCHID_BROOCH,
    ARABIC_NAME_BAR_PIN_BROOCH,
    ARABIC_NAME_NECKLACE_STONE_DOT_LINE,
    MENS_SILVER_CHAIN_CATALOGUE,
    KIDS_NAME_JEWELLERY_MARKET_REFERENCES,
    MENS_CALLIGRAPHY_CUFFLINK_MARKET_REFERENCES,
    CAR_MIRROR_HANGER_LINE,
    NAME_BRACELET_LINE,
    NAME_NECKLACE_STATIONS_AND_DROPS_LINE,
    OWNER_PRODUCT_CATALOGUE,
    INTERTWINED_CALLIGRAPHY_NAME_PENDANT_LINE,
    PHRASE_ON_MESH_BRACELET_WITH_CHARMS,
    MARKET_REFERENCES_PEARL_STRAND_AND_BAR,
    NECKLACE_LENGTH_GUIDES,
    RETAIL_SURVEY_STOCK_NAME_NECKLACES,
    RETAIL_SURVEY_ENGRAVED_BAR_PLATES,
    RETAIL_SURVEY_CORD_NAME_BRACELETS,
    PACKAGING_MATERIALS_BOARD,
    RELIEF_CALLIGRAPHY_DISC_CUFFLINKS_LINE,
    LETTER_STATIONS_BEAD_NECKLACE,
    FRAMED_CALLIGRAPHY_PLATE_MARKET_REFERENCE,
    VENDOR_FONT_TABLES_AND_COMPARISON_SHEETS,
    CALLIGRAPHY_PHRASE_LIBRARY_SCREENSHOTS,
    TOP_STYLE_RETAIL_STOCK_SURVEY,
    SUPPLIER_CATALOGUE_RENDERS_STRAP_CUFF_FRAME,
]
