"""Models sometimes send null for optional tool arguments (seen live with Groq)."""
from app.agent.tool_schemas import TOOLS_OPENAI
from app.tools import run_tool


def test_search_aids_accepts_null_free_text():
    result = run_tool("search_aids", {"profile": {"region": "Aragón", "livestock_type": ["sheep"]},
                                      "free_text": None, "only_open": None}, {})
    assert "results" in result


def test_free_text_schema_is_nullable():
    search = next(t["function"] for t in TOOLS_OPENAI if t["function"]["name"] == "search_aids")
    assert "null" in search["parameters"]["properties"]["free_text"]["type"]
