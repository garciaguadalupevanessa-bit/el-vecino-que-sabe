"""Reads farm data from the farmer's Spanish chat messages, with deterministic rules.

Used by the single-call agent (AGENT_MODE=single), where code (not the LLM) decides which
tools to run, so the profile has to come from the conversation without an extra LLM call.
The form profile always wins over what is read here.
"""
import re
import unicodedata

PROVINCE_REGION = {
    "teruel": "Aragón", "huesca": "Aragón", "zaragoza": "Aragón", "aragon": "Aragón",
    "avila": "Castilla y León", "burgos": "Castilla y León", "leon": "Castilla y León", "palencia": "Castilla y León",
    "salamanca": "Castilla y León", "segovia": "Castilla y León", "soria": "Castilla y León",
    "valladolid": "Castilla y León", "zamora": "Castilla y León", "castilla y leon": "Castilla y León",
    "albacete": "Castilla-La Mancha", "ciudad real": "Castilla-La Mancha", "cuenca": "Castilla-La Mancha",
    "guadalajara": "Castilla-La Mancha", "toledo": "Castilla-La Mancha", "castilla-la mancha": "Castilla-La Mancha",
    "castilla la mancha": "Castilla-La Mancha",
    "caceres": "Extremadura", "badajoz": "Extremadura", "extremadura": "Extremadura",
    "almeria": "Andalucía", "cadiz": "Andalucía", "cordoba": "Andalucía", "granada": "Andalucía", "huelva": "Andalucía",
    "jaen": "Andalucía", "malaga": "Andalucía", "sevilla": "Andalucía", "andalucia": "Andalucía",
    "a coruna": "Galicia", "lugo": "Galicia", "ourense": "Galicia", "pontevedra": "Galicia", "galicia": "Galicia",
    "asturias": "Asturias", "cantabria": "Cantabria", "navarra": "Navarra", "la rioja": "La Rioja",
    "murcia": "Región de Murcia", "madrid": "Comunidad de Madrid",
    "barcelona": "Cataluña", "girona": "Cataluña", "lleida": "Cataluña", "tarragona": "Cataluña", "cataluna": "Cataluña",
    "alicante": "Comunitat Valenciana", "castellon": "Comunitat Valenciana", "valencia": "Comunitat Valenciana",
    "alava": "País Vasco", "bizkaia": "País Vasco", "vizcaya": "País Vasco", "gipuzkoa": "País Vasco",
    "guipuzcoa": "País Vasco", "pais vasco": "País Vasco",
    "baleares": "Illes Balears", "mallorca": "Illes Balears", "canarias": "Canarias",
}
REGIONS = set(PROVINCE_REGION.values())

LIVESTOCK = [
    (r"ovej|ovino|cordero", "sheep"), (r"cabra|caprino|chivo", "goat"), (r"vaca|vacuno|bovino|ternero|novill", "cattle"),
    (r"cerdo|porcino|cochino", "pig"), (r"caball|yegua|equino", "equine"), (r"gallina|pollo|avicola|aves\b", "poultry"),
    (r"colmena|abeja|apicola", "bees"),
]
ANIMAL_WORDS = r"(?:ovejas|cabras|vacas|cerdos|cabezas|animales|reses|hembras|colmenas|gallinas|caballos|yeguas|terneros)"

NUMBER_WORDS = {
    "diez": 10, "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientas": 200, "doscientos": 200,
    "trescientas": 300, "trescientos": 300, "cuatrocientas": 400, "cuatrocientos": 400, "quinientas": 500,
    "quinientos": 500, "seiscientas": 600, "seiscientos": 600, "setecientas": 700, "setecientos": 700,
    "ochocientas": 800, "ochocientos": 800, "novecientas": 900, "novecientos": 900,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}

YES = re.compile(r"^\s*(si|claro|correcto|afirmativo|si,? lo (soy|estoy|esta|tengo))\b")
NO = re.compile(r"^\s*(no)\b(?!\s+(lo\s+)?se\b)")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _number(text: str) -> int | None:
    digits = re.search(r"\d{1,3}(?:[.\s]\d{3})+|\d+", text)
    if digits:
        return int(re.sub(r"[.\s]", "", digits.group(0)))
    total = current = 0
    for word in text.split():
        if word == "mil":
            total += (current or 1) * 1000
            current = 0
        elif word in NUMBER_WORDS:
            current += NUMBER_WORDS[word]
    return (total + current) or None


def _head_count(t: str) -> int | None:
    m = re.search(r"((?:[\w.]+\s+){1,3})" + ANIMAL_WORDS, t)
    if not m:
        return None
    words = [w for w in m.group(1).split() if w not in ("unas", "unos", "de", "mas", "menos", "aproximadamente", "casi")]
    return _number(" ".join(words))


def _from_message(t: str, out: dict) -> None:
    # Longest names first, so "castilla y leon" is not read as the province "leon".
    for name, region in sorted(PROVINCE_REGION.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(name)}\b", t):
            out["region"] = region
            if name not in {_norm(r) for r in REGIONS} and region != name:
                out["province"] = name.title()
            break

    animals = [code for pattern, code in LIVESTOCK if re.search(pattern, t)]
    if animals:
        out["livestock_type"] = animals
        out["farm_activities"] = sorted(set(out.get("farm_activities", [])) | {"livestock"})
    if re.search(r"agricol|cultiv|cereal|olivo|olivar|vinedo|vina\b|regadio|secano|hectareas de (trigo|cebada)", t):
        out["farm_activities"] = sorted(set(out.get("farm_activities", [])) | {"agriculture"})

    heads = _head_count(t)
    if heads is not None:
        out["head_count"] = heads

    for pattern, value in [(r"semiextensiv|extensiv", "extensive"), (r"intensiv", "intensive"),
                           (r"ecologic", "organic"), (r"\bmixt", "mixed")]:
        if re.search(pattern, t):
            out["production_system"] = value
            break

    age = re.search(r"(?:tengo|con)\s+(\d{2})\s+anos", t)
    if age and 16 <= int(age.group(1)) <= 110:
        out["holder_age"] = int(age.group(1))
    years = re.search(r"(?:llevo|desde hace|hace)\s+(\d{1,2}|[a-z]+)\s+(?:anos?|como titular|de actividad)", t)
    if years:
        n = _number(years.group(1))
        if n is not None and n <= 80:
            out["years_active"] = n

    if re.search(r"\bno\s+(soy|estoy de alta como)\s+agricultor(a)?\s+activ", t):
        out["active_farmer"] = False
    elif re.search(r"\b(soy|estoy de alta como)\s+agricultor(a)?\s+activ", t):
        out["active_farmer"] = True
    if re.search(r"\bno\s+(estoy|esta|tengo)\b[^.]{0,30}\brega\b", t):
        out["rega_registered"] = False
    elif re.search(r"\b(inscrit[oa]|registrad[oa]|dad[oa] de alta|tengo)\b[^.]{0,30}\brega\b", t):
        out["rega_registered"] = True

    for pattern, goal in [(r"joven|incorpora|empezar|primera instalacion", "start_up"), (r"moderniz|maquinaria|invertir|inversion", "modernization"),
                          (r"seguro", "insurance"), (r"sanidad|veterinari", "animal_health"), (r"ecologic", "organic")]:
        if re.search(pattern, t):
            out["goal"] = goal
            break


def _answer_to_question(question: str, answer: str, out: dict) -> None:
    """'Sí' / 'No' typed after the assistant asked about active farmer or REGA."""
    field = "active_farmer" if re.search(r"agricultor(a)?\s+activ", question) else (
        "rega_registered" if re.search(r"\brega\b", question) else None)
    if field and YES.search(answer):
        out[field] = True
    elif field and NO.search(answer):
        out[field] = False


def extract_profile(messages: list[dict]) -> dict:
    """Profile fields (FarmProfile names) read from the conversation; later messages win."""
    out: dict = {}
    last_question = ""
    for m in messages:
        text = _norm(m.get("content") or "")
        if m.get("role") == "assistant":
            last_question = text[text.rfind("¿"):] if "?" in text else ""
            continue
        _from_message(text, out)
        if last_question:
            _answer_to_question(last_question, text, out)
    return out
