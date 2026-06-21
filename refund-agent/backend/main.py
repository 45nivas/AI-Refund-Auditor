import os
import sys

# Add the parent directory to sys.path so we can import 'backend' when run from this folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from backend.agent.websocket_manager import manager
from backend.agent.tools import get_db_paths
from backend.agent.graph import agent_app

app = FastAPI(title="AI Refund Agent Backend")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class ChatRequest(BaseModel):
    customer_id: str
    message: str
    session_id: str

class TTSRequest(BaseModel):
    text: str

# WebSocket Route
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        # Loop to keep connection alive and receive any client messages if needed
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception:
        manager.disconnect(websocket, session_id)

# HTTP Routes
session_histories = {}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Executes the LangGraph StateGraph agent for the refund request."""
    # Pre-check if customer ID is supplied
    customer_id = req.customer_id.strip() if req.customer_id else ""
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required.")
        
    if req.session_id not in session_histories:
        session_histories[req.session_id] = []
    history = session_histories[req.session_id]
        
    initial_state = {
        "customer_id": customer_id,
        "user_message": req.message,
        "conversation_history": history,
        "crm_data": None,
        "policy_rules": None,
        "classification_result": None,
        "refund_decision": None,
        "denial_reason": None,
        "reasoning_log": [],
        "tool_calls_made": [],
        "session_id": req.session_id
    }
    
    try:
        final_state = await agent_app.ainvoke(initial_state)
        
        # Append turn to session history
        response_text = final_state.get("user_message", "I'm sorry, I was unable to resolve your request.")
        session_histories[req.session_id].append({"role": "user", "content": req.message})
        session_histories[req.session_id].append({"role": "assistant", "content": response_text})
        
        return {
            "response": response_text,
            "decision": final_state.get("refund_decision", "DENY"),
            "session_id": req.session_id
        }
    except Exception as e:
        # Log error to WebSocket before raising HTTP error
        await manager.broadcast("ERROR", f"Graph execution error: {str(e)}", req.session_id)
        raise HTTPException(status_code=500, detail=f"Agent runtime error: {str(e)}")

@app.get("/customers")
def get_customers():
    """Returns all 15 customer profiles from crm.db."""
    crm_db_path, _, _ = get_db_paths()
    conn = None
    try:
        conn = sqlite3.connect(crm_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT customer_id, name, email, order_id, product_name, order_date, 
                   order_amount, payment_method, delivery_status, days_since_delivery, 
                   previous_refund_count, account_age_days, order_status, return_status,
                   is_digital, item_condition 
            FROM customers
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/admin/decisions")
def get_decisions():
    """Returns all historical refund decisions from decisions.db."""
    _, decisions_db_path, _ = get_db_paths()
    conn = None
    try:
        conn = sqlite3.connect(decisions_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, customer_id, name, decision, reason, agent_notes, timestamp FROM decisions ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/admin/logs")
def get_logs():
    """Returns the last 50 agent reasoning logs from memory."""
    return manager.all_logs[-50:]

@app.post("/voice/tts")
async def voice_tts(req: TTSRequest):
    """Calls ElevenLabs API to convert text to speech, returning an audio stream."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key or api_key == "YOUR_ELEVENLABS_API_KEY" or api_key.strip() == "":
        raise HTTPException(
            status_code=400, 
            detail="ElevenLabs API key is missing or not configured."
        )
    
    # Using voice ID from env, or default 'Rachel' voice ID
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": req.text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    async def stream_audio():
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, json=data, headers=headers, timeout=15.0) as response:
                    if response.status_code != 200:
                        error_detail = await response.aread()
                        print(f"ElevenLabs error status: {response.status_code}, detail: {error_detail.decode()}")
                        # Yield simple silence or small error frame so client doesn't freeze
                        yield b""
                        return
                    
                    async for chunk in response.iter_bytes():
                        yield chunk
            except Exception as e:
                print(f"Exception during ElevenLabs stream: {str(e)}")
                yield b""

    return StreamingResponse(stream_audio(), media_type="audio/mpeg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
