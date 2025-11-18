import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.config import settings

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional dependency
    AsyncOpenAI = None  # type: ignore

logger = logging.getLogger(__name__)

VIDEO_CATEGORY_GROUPS: Dict[str, Dict[str, Any]] = {
    "process_safety": {
        "label": "Process Safety / Major Accident Hazards",
        "emoji": "🟥",
        "tags": [
            {"key": "lsr", "label": "LSR / Life Saving Rules"},
            {"key": "psm", "label": "PSM (Process Safety Management)"},
            {"key": "lopc", "label": "LOPC (Loss of Primary Containment)"},
            {"key": "gas_detection", "label": "Gas detection & flammable vapors"},
            {"key": "confined_space", "label": "Confined space / inerting"},
            {"key": "hot_work", "label": "Hot work ignition hazards"},
            {"key": "static_electricity", "label": "Static electricity & bonding/grounding"},
            {"key": "pressure_systems", "label": "Pressure systems / overpressure & relief devices"},
            {"key": "line_opening", "label": "Line opening / blinding"},
            {"key": "piping_instrumentation", "label": "Piping & instrumentation (P&ID) basics"},
            {"key": "chemical_handling", "label": "Chemicals handling (MSDS / SDS)"},
        ],
    },
    "personal_safety": {
        "label": "Personal Safety / Occupational Safety",
        "emoji": "🟧",
        "tags": [
            {"key": "ppe_selection", "label": "PPE selection and correct use"},
            {"key": "slips_trips", "label": "Slips, trips and falls"},
            {"key": "working_at_height", "label": "Working at height / ladders / scaffolding"},
            {"key": "manual_handling", "label": "Manual handling / ergonomics"},
            {"key": "housekeeping", "label": "Housekeeping"},
            {"key": "noise_exposure", "label": "Noise exposure"},
            {"key": "hand_safety", "label": "Hand safety / pinch points / tool safety"},
            {"key": "eye_face_protection", "label": "Eye and face protection"},
            {"key": "thermal_stress", "label": "Heat stress / cold stress"},
            {"key": "fatigue_management", "label": "Fatigue management"},
        ],
    },
    "youtube_channel": {
        "label": "SnSD YouTube Channel",
        "emoji": "🟦",
        "tags": [
            {"key": "lsr", "label": "LSR / Life Saving Rules"},
            {"key": "psm", "label": "PSM (Process Safety Management)"},
            {"key": "lopc", "label": "LOPC (Loss of Primary Containment)"},
            {"key": "gas_detection", "label": "Gas detection & flammable vapors"},
            {"key": "confined_space", "label": "Confined space / inerting"},
            {"key": "hot_work", "label": "Hot work ignition hazards"},
            {"key": "static_electricity", "label": "Static electricity & bonding/grounding"},
            {"key": "pressure_systems", "label": "Pressure systems / overpressure & relief devices"},
            {"key": "line_opening", "label": "Line opening / blinding"},
            {"key": "piping_instrumentation", "label": "Piping & instrumentation (P&ID) basics"},
            {"key": "chemical_handling", "label": "Chemicals handling (MSDS / SDS)"},
            {"key": "ppe_selection", "label": "PPE selection and correct use"},
            {"key": "slips_trips", "label": "Slips, trips and falls"},
            {"key": "working_at_height", "label": "Working at height / ladders / scaffolding"},
            {"key": "manual_handling", "label": "Manual handling / ergonomics"},
            {"key": "housekeeping", "label": "Housekeeping"},
            {"key": "noise_exposure", "label": "Noise exposure"},
            {"key": "hand_safety", "label": "Hand safety / pinch points / tool safety"},
            {"key": "eye_face_protection", "label": "Eye and face protection"},
            {"key": "thermal_stress", "label": "Heat stress / cold stress"},
            {"key": "fatigue_management", "label": "Fatigue management"},
        ],
    },
}

CATEGORY_TAG_KEYS: Dict[str, Set[str]] = {
    key: {tag["key"] for tag in data["tags"]}
    for key, data in VIDEO_CATEGORY_GROUPS.items()
}

CATEGORY_TAG_LABELS: Dict[str, str] = {
    tag["key"]: tag["label"]
    for data in VIDEO_CATEGORY_GROUPS.values()
    for tag in data["tags"]
}

CATEGORY_TAG_KEYWORDS: Dict[str, List[str]] = {
    "lsr": ["life saving", "lsr"],
    "psm": ["psm", "process safety management"],
    "lopc": ["lopc", "loss of primary containment", "containment"],
    "gas_detection": ["gas detection", "flammable vapor", "flammable vapour", "gas monitor"],
    "confined_space": ["confined space", "inerting", "permit-required"],
    "hot_work": ["hot work", "welding", "spark ignition", "grinding"],
    "static_electricity": ["static electricity", "bonding", "grounding"],
    "pressure_systems": ["overpressure", "relief device", "pressure relief", "rupture disk"],
    "line_opening": ["line opening", "blinding", "blind flange"],
    "piping_instrumentation": ["p&id", "piping and instrumentation", "instrumentation diagram"],
    "chemical_handling": ["chemical handling", "msds", "sds", "material safety data"],
    "ppe_selection": ["ppe", "personal protective equipment", "protective gear"],
    "slips_trips": ["slip", "trip", "fall protection"],
    "working_at_height": ["ladder", "scaffold", "working at height", "tie-off"],
    "manual_handling": ["manual handling", "ergonomic", "lifting", "body mechanics"],
    "housekeeping": ["housekeeping", "clean workspace", "5s"],
    "noise_exposure": ["noise exposure", "hearing protection", "decibel"],
    "hand_safety": ["hand safety", "pinch point", "tool safety", "glove"],
    "eye_face_protection": ["eye protection", "face shield", "goggles", "safety glasses"],
    "thermal_stress": ["heat stress", "cold stress", "temperature extreme", "thermal stress"],
    "fatigue_management": ["fatigue", "rest break", "sleep deprivation", "fatigue management"],
}

PROCESS_KEYWORDS = [
    "process safety",
    "psm",
    "containment",
    "pressure",
    "flammable",
    "gas detection",
    "hot work",
    "p&id",
    "chemical",
    "relief device",
    "confined space",
]

PERSONAL_KEYWORDS = [
    "ppe",
    "slip",
    "trip",
    "fall",
    "height",
    "ladder",
    "manual handling",
    "ergonomics",
    "noise",
    "hand safety",
    "heat stress",
    "fatigue",
]

YOUTUBE_CATEGORY_KEY = "youtube_channel"


def _normalize_category_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace("&", "and")
    normalized = re.sub(r"[^a-z_]", "", normalized)
    if normalized in VIDEO_CATEGORY_GROUPS:
        return normalized
    return None


def _normalize_tag_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace("&", "and")
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    return normalized or None


def _build_classification_payload(
    main_category: Optional[str],
    tag_keys: Optional[List[str]],
    source: str,
    confidence: Optional[float] = None
) -> Dict[str, Any]:
    category_key = _normalize_category_key(main_category) or "process_safety"
    allowed_tags = CATEGORY_TAG_KEYS.get(category_key, set())
    normalized_tags: List[str] = []
    if tag_keys:
        for tag in tag_keys:
            normalized = _normalize_tag_key(tag)
            if normalized and normalized in allowed_tags and normalized not in normalized_tags:
                normalized_tags.append(normalized)

    tag_labels = [CATEGORY_TAG_LABELS.get(tag, tag.title()) for tag in normalized_tags]
    category_info = VIDEO_CATEGORY_GROUPS.get(category_key)
    label = category_info["label"] if category_info else category_key.replace("_", " ").title()

    return {
        "main_category": category_key,
        "main_category_label": label,
        "main_category_emoji": category_info.get("emoji") if category_info else "",
        "tags": normalized_tags,
        "tag_labels": tag_labels,
        "source": source,
        "confidence": confidence,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }


def _fallback_classification(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    process_score = sum(1 for kw in PROCESS_KEYWORDS if kw in lowered)
    personal_score = sum(1 for kw in PERSONAL_KEYWORDS if kw in lowered)
    category = "process_safety" if process_score >= personal_score else "personal_safety"

    matched_tags: List[str] = []
    for tag_key, keywords in CATEGORY_TAG_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched_tags.append(tag_key)

    return _build_classification_payload(category, matched_tags, source="heuristic")


async def classify_script_categories(
    text: str,
    use_openai: bool = True
) -> Optional[Dict[str, Any]]:
    snippet = (text or "").strip()
    if not snippet:
        return None

    fallback = _fallback_classification(snippet)
    if not use_openai or not AsyncOpenAI:
        return fallback

    allowed_categories_text = "\n".join(
        f"- {key}: {data['label']}"
        for key, data in VIDEO_CATEGORY_GROUPS.items()
        if key != YOUTUBE_CATEGORY_KEY
    )
    allowed_tags_text = "\n".join(
        f"- {tag['key']}: {tag['label']} ({category_key})"
        for category_key, info in VIDEO_CATEGORY_GROUPS.items()
        if category_key != YOUTUBE_CATEGORY_KEY
        for tag in info["tags"]
    )

    system_prompt = (
        "You categorize workplace safety training scripts. "
        "Choose exactly one main category and up to four subcategory tags from the allowed list."
    )
    user_prompt = (
        f"Allowed main categories:\n{allowed_categories_text}\n\n"
        f"Allowed tags:\n{allowed_tags_text}\n\n"
        "Return JSON like {\"main_category\": \"process_safety\", \"tags\": [\"psm\", \"lopc\"]}.\n"
        "Never invent new tags.\n\n"
        f"SCRIPT SNIPPET:\n{snippet[:4000]}"
    )

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (
            completion.choices[0].message.content
            if completion.choices and completion.choices[0].message
            else ""
        )
        parsed: Dict[str, Any] = json.loads(content or "{}")
        main_category = parsed.get("main_category")
        tags = parsed.get("tags") or []
        classification = _build_classification_payload(
            main_category,
            tags,
            source="openai",
            confidence=0.9
        )
        return classification or fallback
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning("[CategoryClassifier] Classification failed, using fallback: %s", exc)
        return fallback


__all__ = [
    "VIDEO_CATEGORY_GROUPS",
    "CATEGORY_TAG_LABELS",
    "YOUTUBE_CATEGORY_KEY",
    "classify_script_categories",
    "_build_classification_payload",  # exported for advanced uses
]
