"""Checks the LLM key, lists the available models and tests function calling.

Usage (with the repo stack):
    docker compose run --rm backend python scripts/probe_groq.py
    docker compose run --rm backend python scripts/probe_groq.py --model <id> --attempts 5

Reads LLM_API_KEY, LLM_BASE_URL and LLM_MODEL from the environment (the same .env the backend uses).
Exit code: 0 if every tool-calling attempt succeeds, 1 otherwise, 2 if the key or the SDK is missing.
"""
import argparse
import json
import os
import sys
import time

QUESTION = "Tengo 300 ovejas en Teruel (Aragón). ¿Qué ayudas puedo pedir?"
TOOL = {
    "type": "function",
    "function": {
        "name": "search_aids",
        "description": "Searches public aids for a livestock farm.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "livestock_type": {"type": "string", "enum": ["cattle", "sheep", "goat"]},
            },
            "required": ["region", "livestock_type"],
        },
    },
}


def list_models(client) -> list[str]:
    return sorted(m.id for m in client.models.list().data)


def probe_tool_calling(client, model: str, attempts: int = 3, pause: float = 1.5) -> dict:
    """Asks the model to use a test tool. Returns how many attempts worked and why the others failed."""
    correct, failures = 0, []
    for i in range(attempts):
        if i and pause:
            time.sleep(pause)  # avoids hitting per-minute rate limits
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": QUESTION}],
                tools=[TOOL],
                tool_choice="auto",
                temperature=0.2,
                max_tokens=300,
            )
            calls = resp.choices[0].message.tool_calls
            if not calls:
                failures.append("the model answered without calling the tool")
                continue
            args = json.loads(calls[0].function.arguments or "{}")
            good = (
                calls[0].function.name == "search_aids"
                and args.get("livestock_type") == "sheep"
                and "arag" in str(args.get("region", "")).lower()
            )
            if good:
                correct += 1
            else:
                failures.append(f"unexpected arguments: {args}")
        except json.JSONDecodeError:
            failures.append("the tool arguments are not valid JSON")
        except Exception as e:  # noqa: BLE001 - the reason is shown, not hidden
            failures.append(f"{type(e).__name__}: {str(e)[:160]}")
    return {"attempts": attempts, "correct": correct, "failures": failures}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"))
    ap.add_argument("--attempts", type=int, default=3)
    args = ap.parse_args(argv)

    key = os.getenv("LLM_API_KEY", "")
    if not key:
        print("❌ LLM_API_KEY is missing. Fill it in .env (and run the script with docker compose run).")
        return 2
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ The 'openai' package is not installed. Run the script inside the backend container.")
        return 2

    client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"), timeout=30)
    print(f"Endpoint: {client.base_url}")

    try:
        models = list_models(client)
        print(f"✅ The key works. Available models ({len(models)}):")
        for m in models:
            print(f"   - {m}{'   <- the one being tested' if m == args.model else ''}")
        if args.model not in models:
            print(f"⚠️  Model '{args.model}' is not in the list; check LLM_MODEL.")
    except Exception as e:  # noqa: BLE001
        print(f"❌ Could not list the models: {type(e).__name__}: {str(e)[:200]}")
        print("   Check the key, LLM_BASE_URL and your connection.")
        return 1

    print(f"\nTesting function calling with '{args.model}' ({args.attempts} attempts)...")
    r = probe_tool_calling(client, args.model, args.attempts)
    print(f"Result: {r['correct']}/{r['attempts']} correct")
    for f in r["failures"]:
        print(f"   ✗ {f}")
    if r["correct"] == r["attempts"]:
        print("✅ The model calls tools correctly. Record the model and the usage limits in docs/decisions.md")
        return 0
    print("⚠️  There are failures. If they are occasional the backend retries; if frequent, try another model.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
