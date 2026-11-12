"""Deterministic requirements engine: the LLM does not compute eligibility, this code does."""


FIELD_LABELS = {
    "holder_age": "Edad de la persona titular",
    "years_active": "Años como titular",
    "agricultural_area_hectares": "Superficie agrícola",
    "irrigated_hectares": "Superficie de regadío",
    "livestock_type": "Tipo de ganado",
    "head_count": "Número de animales",
    "production_system": "Sistema de producción",
    "legal_form": "Forma jurídica",
    "pasture_hectares": "Superficie de pastos",
    "rega_registered": "Inscripción en REGA",
    "active_farmer": "Condición de agricultor activo",
    "farm_activities": "Actividad de la explotación",
    "crop_types": "Cultivos declarados",
}
VALUE_LABELS = {
    "cattle": "vacuno", "sheep": "ovino", "goat": "caprino", "pig": "porcino",
    "equine": "equino", "poultry": "avícola", "bees": "apícola", "other": "otro",
    "extensive": "extensivo", "intensive": "intensivo", "organic": "ecológico", "mixed": "mixto",
    "individual": "persona física", "limited_company": "sociedad limitada",
    "corporation": "sociedad anónima", "cooperative": "cooperativa",
    "joint_property": "comunidad de bienes",
}


def _display_value(value):
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, list):
        return ", ".join(_display_value(item) for item in value)
    if isinstance(value, str):
        return VALUE_LABELS.get(value, value)
    return str(value)


def evaluate_requirement(req: dict, profile: dict) -> dict:
    """Returns met/not_met only for evaluable, verified rules; otherwise returns unknown."""
    base = {
        "description": req.get("description"),
        "missing_field": None,
        "needs_verification": bool(req.get("needs_verification")),
        "source_url": req.get("source_url"),
        "citation": req.get("citation"),
    }
    field, op, value = req.get("field"), req.get("operator"), req.get("value")

    if not field:  # not evaluable by code
        return {**base, "status": "unknown", "reason": "Needs to be checked in the official rules.",
                "explanation_es": "Esta condición requiere revisar las bases oficiales."}

    data = profile.get(field)
    if data is None:
        return {**base, "status": "unknown", "reason": "This data is missing.", "missing_field": field,
                "explanation_es": f"Falta indicar en el perfil: {FIELD_LABELS.get(field, 'un dato de la explotación')}."}

    # A provisional rule is useful for explaining what to check, but it must
    # never be presented as a confirmed match or failure.
    if req.get("needs_verification"):
        return {**base, "status": "unknown", "reason": "This requirement needs verification against the official rules.",
                "explanation_es": "Esta regla aún debe confirmarse en la fuente oficial."}

    try:
        if op == "==":
            ok = data == value
        elif op == "<=":
            ok = data <= value
        elif op == ">=":
            ok = data >= value
        elif op == "in":
            ok = bool(set(data) & set(value)) if isinstance(data, list) else data in value
        else:
            return {**base, "status": "unknown", "reason": f"Unsupported operator: {op}",
                    "explanation_es": "Esta regla no se puede calcular automáticamente; hay que revisar las bases."}
    except TypeError:
        return {**base, "status": "unknown", "reason": "The provided data cannot be compared.",
                "explanation_es": "No se puede comparar este dato con la regla; hay que revisarlo."}

    status = "met" if ok else "not_met"
    operator_labels = {"==": "debe ser", "<=": "debe ser como máximo", ">=": "debe ser como mínimo", "in": "debe coincidir con"}
    outcome = "cumple" if ok else "no cumple"
    explanation = (
        f"{FIELD_LABELS.get(field, field)}: { _display_value(data) }; "
        f"la condición {operator_labels[op]} {_display_value(value)}. El dato {outcome}."
    )
    return {**base, "status": status, "reason": f"{field}={data} (required {op} {value})",
            "explanation_es": explanation}


def expand_requirements(aid: dict, blocks: dict) -> list[dict]:
    """Replaces {"ref": "..."} references with the requirements of the reusable block."""
    out: list[dict] = []
    for r in aid["requirements"]:
        if r.get("ref"):
            out.extend(blocks[r["ref"]])
        else:
            out.append(r)
    return out
