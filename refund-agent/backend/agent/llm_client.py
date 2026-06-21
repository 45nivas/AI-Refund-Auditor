import os
import json
import httpx
from pydantic import BaseModel
from backend.agent.websocket_manager import manager

async def query_three_tier_llm(
    system_prompt: str,
    user_prompt: str,
    schema_class,
    session_id: str,
    logs: list
):
    """Executes a 3-tier resilient LLM stack query:
    Tier 1: Google Gemini 1.5 Flash (via direct HTTP, no SDK package required)
    Tier 2: Local Ollama (qwen2.5:3b)
    Tier 3: Local Deterministic Fallback Engine (returns None)
    
    Logs all fallback actions dynamically.
    """
    schema_schema = schema_class.model_json_schema()
    schema_keys = list(schema_schema.get("properties", {}).keys())

    # Build prompt that strictly enforces JSON output structure
    full_prompt = (
        f"{system_prompt}\n\n"
        f"IMPORTANT: You must respond ONLY with a raw JSON object. Do not include markdown code blocks, do not include triple backticks, and do not wrap in 'json'. Output only the pure JSON text.\n"
        f"The JSON object must strictly adhere to the following JSON schema:\n"
        f"{json.dumps(schema_schema, indent=2)}\n\n"
        f"Query/Context:\n{user_prompt}"
    )

    # -------------------------------------------------------------
    # TIER 1: Gemini Flash
    # -------------------------------------------------------------
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip() != "" and gemini_key != "YOUR_GEMINI_API_KEY":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, timeout=12.0)
                if res.status_code == 200:
                    data = res.json()
                    text_response = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    parsed = json.loads(text_response)
                    # Verify required keys exist
                    if all(k in parsed for k in schema_keys):
                        return schema_class(**parsed)
                    else:
                        raise ValueError(f"Missing keys in Gemini JSON. Expected: {schema_keys}, Got: {list(parsed.keys())}")
                elif res.status_code == 429:
                    msg = "Gemini API rate limit (429) hit"
                    await log_fallback("Gemini rate limit → Ollama", msg, session_id, logs)
                else:
                    msg = f"Gemini API returned status {res.status_code}"
                    await log_fallback("Gemini status error → Ollama", msg, session_id, logs)
        except Exception as e:
            msg = f"Gemini API call error: {str(e)}"
            await log_fallback("Gemini connection error → Ollama", msg, session_id, logs)
    else:
        msg = "Gemini API key is not configured"
        await log_fallback("Gemini key missing → Ollama", msg, session_id, logs)

    # -------------------------------------------------------------
    # TIER 2: Ollama (local LLM)
    # -------------------------------------------------------------
    ollama_host = os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434"
    ollama_url = f"{ollama_host.rstrip('/')}/api/chat"
    ollama_model = os.environ.get("OLLAMA_MODEL") or "qwen2.5:3b"
    
    ollama_payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Return ONLY raw JSON matching this schema:\n{json.dumps(schema_schema)}\n\nQuery: {user_prompt}"}
        ],
        "format": "json",
        "options": {
            "temperature": 0
        },
        "stream": False
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(ollama_url, json=ollama_payload, timeout=180.0)
            if res.status_code == 200:
                data = res.json()
                text_response = data["message"]["content"].strip()
                parsed = json.loads(text_response)
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                return schema_class(**parsed)
            else:
                msg = f"Ollama server returned status {res.status_code}"
                await log_fallback("Ollama error → Deterministic fallback", msg, session_id, logs)
    except Exception as e:
        msg = f"Ollama connection failed (local model '{ollama_model}' not running or Ollama down)"
        await log_fallback("Ollama connection failed → Deterministic fallback", msg, session_id, logs)

    # -------------------------------------------------------------
    # TIER 3: Local Deterministic Fallback
    # -------------------------------------------------------------
    msg = "All LLM tiers unavailable. Triggered local Deterministic Fallback Engine."
    logs.append(f"[FALLBACK] {msg}")
    await manager.broadcast("FALLBACK", msg, session_id)
    return None

async def log_fallback(action: str, error_msg: str, session_id: str, logs: list):
    """Helper to append and broadcast fallback logs."""
    log_text = f"[FALLBACK] {action} ({error_msg})"
    logs.append(log_text)
    await manager.broadcast("FALLBACK", f"{action} ({error_msg})", session_id)
