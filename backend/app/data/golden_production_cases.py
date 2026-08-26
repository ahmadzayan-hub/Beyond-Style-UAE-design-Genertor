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


def _ev(role, sha256, width, height, size_bytes, storage_status, note):
    return {
        "role": role,
        "sha256": sha256,
        "media_type": "image/jpeg",
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


GOLDEN_PRODUCTION_CASES = [
    ARABIC_LETTER_PEARL_EARRINGS,
    LAYERED_NAME_NECKLACE_ADAM_OMAR,
]
