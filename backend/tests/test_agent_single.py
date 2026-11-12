"""AGENT_MODE=single: code runs the tools, the LLM is called exactly once (fake client, no network)."""
import json
from types import SimpleNamespace as NS

import pytest

from app.agent import agent, single
from app.agent.profile_extract import extract_profile


class FakeClient:
    def __init__(self, answer="Respuesta"):
        self.answer = answer
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return NS(choices=[NS(message=NS(content=self.answer, tool_calls=None))])


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(agent.config, "AGENT_MODE", "single")
    c = FakeClient()
    monkeypatch.setattr(agent, "_client", c)
    return c


def user(text):
    return {"role": "user", "content": text}


def test_profile_is_read_from_spanish_chat():
    p = extract_profile([user("Tengo 20 ovejas en extensivo en Teruel y soy agricultor activo.")])
    assert p == {"region": "Aragón", "province": "Teruel", "livestock_type": ["sheep"], "farm_activities": ["livestock"],
                 "head_count": 20, "production_system": "extensive", "active_farmer": True}
    p = extract_profile([user("Tengo unas trescientas ovejas en Teruel, tengo 29 años y llevo 2 como titular.")])
    assert p["head_count"] == 300 and p["holder_age"] == 29 and p["years_active"] == 2
    assert extract_profile([user("No soy agricultor activo")])["active_farmer"] is False
    assert extract_profile([user("Tengo vacas en Castilla y León")])["region"] == "Castilla y León"
    assert "province" not in extract_profile([user("Tengo vacas en Castilla y León")])


def test_yes_no_after_a_question_fills_the_field():
    msgs = [user("Tengo 300 ovejas en Teruel"),
            {"role": "assistant", "content": "He encontrado 2 ayudas. ¿Estás dado de alta como agricultor activo?"},
            user("Sí.")]
    assert extract_profile(msgs)["active_farmer"] is True
    msgs[-1] = user("No lo sé")
    assert "active_farmer" not in extract_profile(msgs)


def test_question_routing():
    assert single.intent_of("Tengo 20 ovejas en Teruel") == "search"
    assert single.intent_of("Vale, ¿y cómo la pido?") == "guide"
    assert single.intent_of("¿Qué documentación necesito?") == "guide"
    assert single.intent_of("No cumplo, ¿qué alternativas tengo?") == "alternatives"
    assert single.intent_of("¿Qué es ser agricultor activo? Explícamelo.") == "explain"


def test_single_mode_makes_one_llm_call_without_tools(fake):
    r = agent.run_agent([user("Tengo 20 ovejas en extensivo en Teruel y soy agricultor activo.")], {})
    assert len(fake.calls) == 1
    assert "tools" not in fake.calls[0]
    assert r["answer"] == "Respuesta"
    tools = [t["tool"] for t in r["trace"]]
    assert tools[0] == "search_aids" and "check_eligibility" in tools
    sheep = next(a for a in r["aids"] if a["id"] == "cap_coupled_sheep_goat_meat")
    assert sheep["overall_result"] == "not_met"  # 20 sheep < minimum of 30, computed by code
    results = fake.calls[0]["messages"][-1]["content"]
    assert "TOOL RESULTS" in results and "citation" not in results  # compact: no long source quotes


def test_form_profile_wins_over_chat(fake):
    r = agent.run_agent([user("Tengo 20 ovejas en Teruel")], {"head_count": 300})
    assert r["trace"][0]["input"]["profile"]["head_count"] == 300


def test_guide_question_targets_the_aid_under_discussion(fake):
    msgs = [user("Tengo 300 ovejas en extensivo en Teruel"),
            {"role": "assistant", "content": "La que mejor encaja es la ayuda asociada a los ganaderos extensivos de ovino y caprino de carne."},
            user("¿Y cómo la pido?")]
    r = agent.run_agent(msgs, {})
    guide = next(t for t in r["trace"] if t["tool"] == "get_application_guide")
    assert guide["input"]["aid_id"] == "cap_coupled_sheep_goat_meat"


def test_explain_question_runs_no_tools(fake):
    r = agent.run_agent([user("¿Qué es ser agricultor activo?")], {})
    assert r["trace"] == [] and len(fake.calls) == 1


def test_results_message_stays_small():
    _, calls = single.plan_and_run([user("Tengo 300 ovejas en extensivo en Teruel, tengo 29 años")], {})
    msg = single.results_message("search", {}, calls)
    assert len(msg) < 9000, len(msg)  # ~2300 tokens: one call fits Groq's free 8000 tokens/minute
    json.loads(msg[msg.index("["):])
