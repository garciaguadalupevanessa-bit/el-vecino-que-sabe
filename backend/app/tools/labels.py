"""Ready-to-show Spanish labels, computed in code so the LLM does not have to translate internal values."""


def _date_es(iso: str | None) -> str:
    """'2026-11-12' -> '12/11/2026'. Leaves anything unexpected as it is."""
    parts = str(iso or "").split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else str(iso or "")


def reliability_label_es(aid: dict) -> str:
    reliability = aid.get("reliability")
    when = _date_es(aid.get("verified_on"))
    if reliability == "verified":
        if aid.get("verification_method") == "agent":
            return (f"Verificada automáticamente contra la fuente oficial el {when} "
                    "(no revisada por una persona).")
        return f"Verificada por una persona contra la fuente oficial el {when}."
    if reliability == "extracted":
        return f"Sin verificar: datos extraídos de la fuente el {when}, pendientes de revisión."
    return f"Sin verificar: solo tenemos los datos básicos de la ficha (registrada el {when})."


RECOMMENDATION_ES = {
    "not_met": ("Con los datos actuales esta ayuda no encaja, porque no se cumple al menos un requisito obligatorio. "
                "No recomiendes solicitarla: explica qué requisito falla y busca alternativas."),
    "unknown": ("Todavía no se puede saber si encaja: faltan datos o requisitos por confirmar. "
                "Explica qué falta antes de recomendar solicitarla."),
    "met": ("Con los datos actuales se cumplen los requisitos comprobados. "
            "Recuerda que la concesión la decide la administración."),
}
