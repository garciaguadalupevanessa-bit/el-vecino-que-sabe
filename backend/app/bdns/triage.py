"""Conservative, evidence-linked triage suggestions for imported BDNS calls."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("pac_direct", "P1", (
        "pago basico", "ayuda basica a la renta", "pago redistributivo", "ecorregimen",
        "derechos de pago", "ayudas directas pac",
    )),
    ("pac_coupled", "P1", (
        "ayuda asociada", "pago asociado", "ayuda acoplada", "produccion asociada",
    )),
    ("young_farmer_startup", "P1", (
        "joven agricultor", "joven agricultora", "incorporacion de jovenes", "primera instalacion",
        "establecimiento de jovenes", "empresa agraria joven",
    )),
    ("farm_modernisation", "P1", (
        "modernizacion de explotaciones", "modernizacion agraria", "mejora de explotaciones",
        "maquinaria agricola", "eficiencia de explotaciones",
    )),
    ("agro_environment_organic", "P1", (
        "agroambiental", "agricultura ecologica", "ganaderia ecologica", "produccion ecologica",
        "conversion ecologica", "practicas agroambientales",
    )),
    ("agricultural_insurance", "P1", (
        "seguro agrario", "seguros agrarios", "seguro agricola", "seguro ganadero",
        "prima de seguro agrario", "enesa", "agroseguro",
    )),
    ("animal_health", "P2", (
        "sanidad animal", "bioseguridad ganadera", "enfermedades animales", "erradicacion de enfermedades",
        "ads ganaderas",
    )),
    ("extensive_livestock", "P2", (
        "ganaderia extensiva", "explotacion extensiva", "pastoreo extensivo", "aprovechamiento de pastos",
    )),
    ("native_breeds", "P2", (
        "razas autoctonas", "razas ganaderas autoctonas", "conservacion de razas", "libro genealogico",
    )),
    ("investment", "P3", (
        "inversiones en explotaciones agrarias", "inversion agraria", "inversiones ganaderas",
        "infraestructura agraria",
    )),
    ("emergency_aid", "P3", (
        "sequia", "incendio", "inundacion", "helada", "adversidad climatica", "catastrofe",
        "danos agrarios",
    )),
)

ACTIVITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("agriculture", (
        "agricultur", "agrari", "cultivo", "cultivos", "cereal", "olivar", "horticol", "frutal",
        "vinic", "viñed", "regadio", "invernadero", "produccion vegetal",
    )),
    ("livestock", (
        "ganader", "vacun", "bovin", "ovin", "caprin", "porcin", "apicol", "avicol", "equino",
        "pastos", "leche", "raza autoctona", "sanidad animal", "ganaderia extensiva",
    )),
)

FARM_BENEFICIARY_TERMS = (
    "agricultor", "agricultora", "ganadero", "ganadera", "titular de explotacion",
    "titulares de explotaciones", "explotacion agraria", "explotaciones agrarias",
    "productor agrario", "productores agrarios", "agricultores profesionales",
)
INSTITUTIONAL_BENEFICIARY_TERMS = (
    "universidad", "ayuntamiento", "entidad local", "centro de investigacion", "fundacion",
    "administracion publica", "organismo publico", "asociacion", "federacion",
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _matches(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = _normalize(text)
    found: list[str] = []
    for term in terms:
        needle = _normalize(term)
        if " " in needle or len(needle) <= 5:
            pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
            matched = re.search(pattern, normalized) is not None
        else:
            matched = needle in normalized
        if matched:
            found.append(term)
    return found


def suggest_bdns_triage(record: dict[str, Any]) -> dict[str, Any]:
    """Return suggestions only; never alter source review, reliability, or eligibility."""
    call = record.get("call") or {}
    title = call.get("title") if isinstance(call.get("title"), str) else ""
    purpose = call.get("purpose") if isinstance(call.get("purpose"), dict) else {}
    fields: list[tuple[str, str]] = [
        ("call.title", title),
        ("call.purpose.label", purpose.get("label") if isinstance(purpose.get("label"), str) else ""),
    ]
    for index, item in enumerate(call.get("economic_sectors") or []):
        if isinstance(item, dict) and isinstance(item.get("label"), str):
            fields.append((f"call.economic_sectors[{index}].label", item["label"]))
    for index, item in enumerate(call.get("objectives") or []):
        if isinstance(item, dict):
            label = item.get("descripcion") or item.get("description")
            if isinstance(label, str):
                fields.append((f"call.objectives[{index}]", label))
    beneficiary_values = [
        item.get("label") for item in (call.get("beneficiary_categories") or [])
        if isinstance(item, dict) and isinstance(item.get("label"), str)
    ]
    beneficiary_text = " | ".join(beneficiary_values)

    category_suggestions = []
    for category, priority, terms in CATEGORY_RULES:
        evidence = []
        for field, value in fields:
            matches = _matches(value, terms)
            if matches:
                evidence.append({"field": field, "value": value[:240], "matched_terms": matches[:3]})
        if evidence:
            category_suggestions.append({
                "category": category, "priority": priority, "evidence": evidence[:3],
            })

    activity_evidence = {}
    for activity, terms in ACTIVITY_RULES:
        matches = []
        for field, value in fields:
            for term in _matches(value, terms):
                matches.append({"field": field, "value": value[:240], "matched_term": term})
        if matches:
            activity_evidence[activity] = matches[:3]

    farm_beneficiaries = _matches(beneficiary_text, FARM_BENEFICIARY_TERMS)
    institutional_beneficiaries = _matches(beneficiary_text, INSTITUTIONAL_BENEFICIARY_TERMS)
    has_agri_signal = bool(category_suggestions or activity_evidence)
    if has_agri_signal and farm_beneficiaries:
        relevance = "prioritize"
        explanation = "Hay señales agrarias y beneficiarios que parecen ser productores o titulares de explotaciones."
    elif has_agri_signal:
        relevance = "check_beneficiaries"
        explanation = "Hay señales agrarias, pero los metadatos no confirman que las explotaciones sean beneficiarias directas."
    else:
        relevance = "low_signal"
        explanation = "Los metadatos consultados no muestran señales agrarias claras; puede faltar información en las bases."

    campaign_match = re.search(r"(?:campa(?:ñ|n)a|ejercicio)\s+(20\d{2})", title, re.IGNORECASE)
    campaign = None
    if campaign_match:
        campaign = {
            "year": int(campaign_match.group(1)),
            "evidence": {"field": "call.title", "value": title[:240]},
        }

    return {
        "version": "1.0",
        "relevance_suggestion": relevance,
        "explanation": explanation,
        "farm_beneficiary_terms": farm_beneficiaries,
        "institutional_beneficiary_terms": institutional_beneficiaries,
        "activity_suggestions": activity_evidence,
        "category_suggestions": category_suggestions,
        "campaign_suggestion": campaign,
        "human_confirmation_required": True,
    }
