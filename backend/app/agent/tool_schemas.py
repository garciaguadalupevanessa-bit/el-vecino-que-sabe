"""Tool schemas for function calling. The descriptions guide the LLM's decisions."""

PROFILE_SCHEMA = {
    "type": "object",
    "description": (
        "Farm characteristics for agricultural, livestock, or mixed holdings. Include only data the user has given; never invent any. "
        "Translate colloquial language into the allowed values."
    ),
    "properties": {
        "region": {"type": "string", "description": "Autonomous community, e.g. Aragón."},
        "province": {"type": "string"},
        "municipality": {"type": "string", "description": "Municipality where the holding is located, if known."},
        "farm_activities": {"type": "array", "items": {"type": "string", "enum": ["agriculture", "livestock"]}},
        "crop_types": {"type": "array", "items": {"type": "string"}, "description": "Crops the holding grows, if provided."},
        "agricultural_area_hectares": {"type": "number", "description": "Total agricultural area in hectares."},
        "irrigated_hectares": {"type": "number", "description": "Irrigated area in hectares."},
        "livestock_type": {
            "type": "array",
            "items": {"type": "string",
                      "enum": ["cattle", "sheep", "goat", "pig", "equine", "poultry", "bees", "other"]},
        },
        "head_count": {"type": "integer", "description": "Number of animals the user says they have, e.g. '20 ovejas' -> 20, '300 cabezas' -> 300. Always fill it when the user gives a number of animals."},
        "production_system": {"type": "string", "enum": ["extensive", "intensive", "organic", "mixed"]},
        "legal_form": {
            "type": "string",
            "enum": ["individual", "limited_company", "corporation", "cooperative", "joint_property", "other"],
        },
        "holder_age": {"type": "integer", "description": "Age of the holder in years, e.g. 'tengo 29 años' -> 29."},
        "years_active": {"type": "integer", "description": "Years as holder of the farm, e.g. 'llevo 2 años' -> 2."},
        "pasture_hectares": {"type": "number"},
        "rega_registered": {"type": "boolean"},
        "active_farmer": {"type": "boolean", "description": "True if the user says they are an active farmer ('soy agricultor activo')."},
        "goal": {
            "type": "string",
            "enum": ["income", "start_up", "modernization", "insurance", "animal_health", "organic", "other"],
        },
    },
}

TOOL_SCHEMAS = [
    {
        "name": "search_aids",
        "description": (
            "Searches public aids that may apply to an agricultural, livestock, or mixed holding. "
            "Use it when the user asks which aids exist or which ones they could get. "
            "Returns candidates with a preliminary fit; it does NOT confirm eligibility "
            "(use check_eligibility for that). Location and activity are optional: match national, community, "
            "province and municipality aid scopes when those details are available; search national aids if location is unknown. "
            "Do not require livestock details for crop-only farms. Ask for more data only when it materially narrows results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": PROFILE_SCHEMA,
                "free_text": {"type": "string",
                              "description": "Keywords for the goal, e.g. 'milking machinery'."},
                "only_open": {"type": "boolean",
                              "description": "If true, discards aids whose application window is closed."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["profile"],
        },
    },
    {
        "name": "check_eligibility",
        "description": (
            "Evaluates, requirement by requirement, whether the profile meets a specific aid. Use it after "
            "search_aids when the user asks whether they qualify, what is missing or what an aid requires. "
            "Returns met/not_met only when the aid and rules are verified; otherwise both the overall result and each rule are unknown. "
            "Never state that the aid will be granted: only report requirements."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "aid_id": {"type": "string", "description": "Identifier returned by search_aids."},
                "profile": PROFILE_SCHEMA,
            },
            "required": ["aid_id", "profile"],
        },
    },
    {
        "name": "get_application_guide",
        "description": (
            "Explains how to apply for an aid: agency, deadline, documents and steps. Use it when the "
            "user asks how to get it, where to apply or which papers are needed. It withholds deadlines, documents and steps "
            "unless the aid is verified against its official rules."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"aid_id": {"type": "string", "description": "Identifier returned by search_aids."}},
            "required": ["aid_id"],
        },
    },
    {
        "name": "find_alternatives",
        "description": (
            "Suggests alternatives when the user does not qualify for an aid or there are no results: "
            "related aids and what change or data would make the farm eligible. Use it if "
            "check_eligibility returns unmet requirements or if search_aids returns nothing useful."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": PROFILE_SCHEMA,
                "aid_id": {"type": "string", "description": "The aid the user does not qualify for, if any."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["profile"],
        },
    },
]


# OpenAI/Groq-compatible function calling format, derived from the schemas above
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
    }
    for t in TOOL_SCHEMAS
]
