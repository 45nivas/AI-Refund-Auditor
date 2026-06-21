# Architecture Audit Report — AI Customer Support Agent (refund-agent)

This report details the architectural audit conducted on the `refund-agent` repository. It evaluates the system across all ten designated check areas, identifies critical defects, highlights software bugs, highlights missing implementations, notes areas of strengths, and provides an actionable sequence of remediation.

---

## ARCHITECTURE SCORE: 6.5/10

The project features a well-conceived **3-tier LLM fallback chain** (Gemini → Ollama → Deterministic rules) and an interactive **LangGraph StateGraph** architecture to model customer support flows. However, the system's score is lowered to **6.5/10** due to critical flaws: the primary AI model tier is completely broken due to a model name typo, the StateGraph fails to short-circuit intent mismatches, database connection handles are leaked on SQL exceptions (posing resource exhaustion risks), and local Docker Compose environments fail to boot out-of-the-box because host volume mounts overwrite container database seeding.

---

## 1. Detailed Review of the 10 Check Areas

### 1. Project Structure & Separation of Concerns
The codebase is divided into:
- **Backend (FastAPI)**: Configured in `backend/main.py` to expose chat, customer retrieval, decision history, logs, and Web Audio text-to-speech (TTS) streaming.
- **Agent Core (LangGraph)**: Defined under `backend/agent/` separating graph states (`graph.py`), tool execution (`tools.py`), validation logic (`validation.py`), prompts (`prompts.py`), and the custom LLM router (`llm_client.py`).
- **Frontend (React)**: Structured with modular UI components (`CustomerList.jsx`, `ChatPanel.jsx`, etc.) and event hooks (`useVoice.js`, `useWebSocket.js`).

**Critique**: The structure is clean, but the file boundary between the Docker environment and the application runtime is violated. In `docker-compose.yml`, mounting the host's `./backend` directory to the container's `/app` directory overwrites the container filesystem. Thus, the database files seeded during the container build (`crm.db` and `decisions.db`) are hidden at runtime unless they already exist on the host, causing application crashes on startup.

### 2. LangGraph StateGraph Schema, Nodes, Edges, Routing, and Short-Circuiting
The state graph is managed in `backend/agent/graph.py` via `StateGraph(AgentState)` utilizing a typed dictionary (`AgentState`) tracking inputs, CRM profiles, intent classifications, decisions, and reasoning logs.
- **Routing & Short-Circuiting**: Nodes represent standard checks (window, history, delivery, and value). 
- **Critique**: The StateGraph's routing is flawed. After `classify_request_type`, an unconditional transition runs `validate_refund_window` (lines 84-85). This bypasses the ability to short-circuit when an intent mismatch is detected. The validation nodes execute regardless of the mismatch, overwriting the denial reason with unrelated policy failures (such as refund window expiration), and unnecessarily polluting the reasoning log.

### 3. 3-Tier LLM Fallback Chain Logic and Exception Handling
The LLM manager (`backend/agent/llm_client.py`) implements a 3-tier fallback architecture:
1. **Tier 1 (Gemini 1.5 Flash)**: Queried via direct HTTP calls to avoid SDK dependencies.
2. **Tier 2 (Ollama)**: Local LLM running `qwen2.5:3b` as a backup.
3. **Tier 3 (Deterministic Mock)**: Python-based rule synthesis.

**Critique**: The primary tier (Gemini) is fully non-functional. An invalid model name (`gemini-2.5-flash`) is hardcoded in the API endpoint URL on line 38, causing Google’s servers to return a `400 Bad Request` on every request. This forces the system to immediately fall back to Tier 2 (which hangs if Ollama is not running due to an excessive 180s client timeout) or Tier 3.

### 4. Intent Classification Correctness & Intent Mismatch Handling
The system uses the LLM (or Tier 3 keywords) to classify customer queries into types (e.g., standard refunds, damaged items, cancellations, abuse, or intent mismatches).
- **Critique**: Under an `intent_mismatch` classification (e.g., customer `CUST002` requesting a subscription cancellation for a physical item order), the node correctly populates the state's `refund_decision` as `"DENY"` and updates the `denial_reason`. However, because the state graph does not short-circuit, the subsequent `validate_refund_window` node runs and overwrites these fields because it checks the physical order's age (which is 35 days for `CUST002`) and updates `denial_reason` with a window violation message, masking the classification mismatch.

### 5. FastAPI Backend Routes, CORS, WebSockets, and ElevenLabs Integration
FastAPI handles HTTP routes, CORS rules, text-to-speech rendering, and real-time logs via WebSocket connections (`/ws/{session_id}`).
- **ElevenLabs Integration**: Streamed successfully over the `/voice/tts` endpoint.
- **Critique**: The database operations inside `get_customers` (lines 95-106) and `get_decisions` (lines 116-121) in `backend/main.py` fail to clean up connection handles when SQLite errors occur. If a query fails, the connection remains open, leaking system resources.

### 6. SQLite Database Schema, Seeding Profiles, and Query Safety
The database includes `crm.db` (customer metadata) and `decisions.db` (decision logs). Seeding is handled via `backend/data/seed_db.py`.
- **Query Safety**: SQL queries in `tools.py` use parameterized queries (`customer_id = ? OR email = ?`), which prevents SQL injection attacks.
- **Critique**: Connection leaks exist in `backend/agent/tools.py`. Both `get_customer_profile` and `log_decision` close connections at the end of their `try` blocks. Any runtime exception (e.g. database locking or column mismatch) bypasses `conn.close()`, eventually locking the databases.

### 7. Tool Functions
The system uses decorated `@tool` functions (`get_customer_profile`, `get_refund_policy`, `check_eligibility`, and `log_decision`).
- **Critique**: The functions are functionally complete but lack proper resource safety. The DB connection handles are not wrapped in a `finally` block or custom context manager, creating resource leaks.

### 8. Reasoning Log Formats, Tag Quality, and Clause Citations
Telemetry is streamed to the frontend via WebSockets in a tagged format: `[TOOL]`, `[CHECK]`, `[DECISION]`, `[RESPONSE]`, and `[FALLBACK]`.
- **Critique**: For pre-shipment cancellations (covered by Clause 8 of the refund policy), the deterministic fallback decision path in `backend/agent/nodes.py` (line 373) logs a generic citation `"Clauses Met"` instead of referencing `"Clause 8"`.

### 9. React UI Components, WebSocket Connections, Badges, Statistics Counters, and Voice Pipeline
The frontend is a single-page React dashboard built with Tailwind CSS. It aggregates customer states, runs, decisions, and reasoning logs.
- **Critique**:
  1. The WebSocket connection status badge is hardcoded to green `"Agent Online"`, ignoring the hook's `isConnected` variable.
  2. Emojis like ✅, ❌, or ⚠️ are not stripped before synthesis in `useVoice.js`, causing the browser's voice synthesis engine to vocally speak them (e.g., "warning sign").
  3. The `SpeechRecognition` initialization in `useVoice.js` does not return a cleanup function, leaving stale listeners registered on unmount.

### 10. Error Resiliency
Resiliency features include the 3-tier fallback and voice synthesis fallbacks.
- **Critique**:
  1. If fields like `days_since_delivery` or `previous_refund_count` are present but set to `NULL` (Python `None`) in the database, `validation.py` operations like `days > 30` fail with `TypeError: '>' not supported between instances of 'NoneType' and 'int'`, causing the entire graph to crash.
  2. The WebSocket connection hook `useWebSocket.js` does not implement auto-reconnection logic when the socket connection drops.

---

## 2. CRITICAL ISSUES (Must Fix Before Demo)

### 1. Gemini API Endpoint Model Name Typo
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\llm_client.py`
- **Line Number**: 38
- **Verbatim Code**:
  ```python
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
  ```
- **Description**: The hardcoded model `gemini-2.5-flash` does not exist on the Google API, causing a 400 Bad Request error. This breaks the primary LLM tier.
- **Exact Fix Code**:
  ```python
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
  ```

### 2. StateGraph Routing Bug (No Short-Circuiting on Intent Mismatch)
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\graph.py`
- **Line Number**: 85
- **Verbatim Code**:
  ```python
  workflow.add_edge("classify_request_type", "validate_refund_window")
  ```
- **Description**: The graph unconditionally routes to the refund window validation node after classification. On an intent mismatch, the validation nodes overwrite the classification denial reason with standard policy violation reasons.
- **Exact Fix Code**:
  Add a routing helper function in `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\graph.py`:
  ```python
  def route_after_classification(state: AgentState) -> str:
      """If classification result is intent_mismatch, route directly to decision synthesis."""
      if state.get("classification_result") == "intent_mismatch":
          return "make_decision"
      return "validate_refund_window"
  ```
  Replace line 85 in `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\graph.py` with:
  ```python
  workflow.add_conditional_edges(
      "classify_request_type",
      route_after_classification,
      {
          "make_decision": "make_decision",
          "validate_refund_window": "validate_refund_window"
      }
  )
  ```

### 3. Database Connection Leaks on Exceptions
- **File Paths**: 
  - `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\tools.py` (lines 20-31, 67-74)
  - `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\main.py` (lines 95-106, 116-121)
- **Description**: SQLite connections are not closed if database operations raise exceptions, leading to locked databases and handle exhaustion.
- **Exact Fix Code**:
  Modify `get_customer_profile` and `log_decision` in `tools.py`:
  ```python
  @tool
  def get_customer_profile(customer_id_or_email: str) -> dict:
      crm_db_path, _, _ = get_db_paths()
      conn = None
      try:
          conn = sqlite3.connect(crm_db_path)
          conn.row_factory = sqlite3.Row
          cursor = conn.cursor()
          customer_id_or_email = customer_id_or_email.strip()
          cursor.execute("""
              SELECT * FROM customers 
              WHERE customer_id = ? OR email = ?
          """, (customer_id_or_email, customer_id_or_email))
          row = cursor.fetchone()
          if row:
              return dict(row)
          return {"error": f"Customer with ID or Email '{customer_id_or_email}' not found."}
      finally:
          if conn:
              conn.close()

  @tool
  def log_decision(customer_id: str, decision: str, reason: str, agent_notes: str = "") -> bool:
      profile = get_customer_profile.func(customer_id)
      name = profile.get("name", "Unknown Customer") if "error" not in profile else "Unknown Customer"
      _, decisions_db_path, _ = get_db_paths()
      conn = None
      try:
          conn = sqlite3.connect(decisions_db_path)
          cursor = conn.cursor()
          cursor.execute("""
              INSERT INTO decisions (customer_id, name, decision, reason, agent_notes)
              VALUES (?, ?, ?, ?, ?)
          """, (customer_id, name, decision, reason, agent_notes))
          conn.commit()
          return True
      except Exception as e:
          print(f"Error logging decision to DB: {e}")
          return False
      finally:
          if conn:
              conn.close()
  ```
  Modify the `get_customers` and `get_decisions` routes in `backend/main.py` to use `try...finally`:
  ```python
  @app.get("/customers")
  def get_customers():
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
  ```

### 4. Docker Compose Mounting Bug (Missing Databases on Startup)
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\docker-compose.yml`
- **Line Number**: 15
- **Verbatim Code**:
  ```yaml
  volumes:
    - ./backend:/app
  ```
- **Description**: The host volume mount overrides `/app` in the container. If databases aren't seeded on the host before running `docker-compose up`, they won't exist inside the running app.
- **Exact Fix Code**:
  Add an auto-seeding verification block inside the startup phase of `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\main.py`:
  ```python
  # Add to backend/main.py near the database imports/configurations
  crm_db_path, decisions_db_path, _ = get_db_paths()
  if not os.path.exists(crm_db_path) or not os.path.exists(decisions_db_path):
      try:
          from backend.data.seed_db import seed_databases
          seed_databases()
      except Exception as e:
          print(f"Error seeding databases at startup: {e}")
  ```

---

## 3. BUGS FOUND

### 5. Hardcoded "Agent Online" WebSocket Connection Status Badge
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\frontend\src\App.jsx`
- **Line Number**: 184-187
- **Verbatim Code**:
  ```jsx
  <div className="flex items-center gap-1.5 text-xs text-green-500 bg-green-500/10 border border-green-500/25 px-2.5 py-1 rounded-full font-mono font-medium">
    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
    Agent Online
  </div>
  ```
- **Description**: The WebSocket connection status badge is hardcoded and ignores the state of the connection (`isConnected`).
- **Exact Fix Code**:
  In `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\frontend\src\App.jsx`, extract `isConnected` on line 72:
  ```javascript
  const { logs, clearLogs, isConnected } = useWebSocket(sessionId);
  ```
  And replace lines 184-187 with:
  ```jsx
  {isConnected ? (
    <div className="flex items-center gap-1.5 text-xs text-green-500 bg-green-500/10 border border-green-500/25 px-2.5 py-1 rounded-full font-mono font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
      Agent Online
    </div>
  ) : (
    <div className="flex items-center gap-1.5 text-xs text-red-500 bg-red-500/10 border border-red-500/25 px-2.5 py-1 rounded-full font-mono font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
      Agent Offline
    </div>
  )}
  ```

### 6. Database `None` Values Causing Policy Validation Crashes
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\validation.py`
- **Line Numbers**: 6, 19, 72
- **Verbatim Code**:
  ```python
  days = crm_data.get("days_since_delivery", 0) # line 6
  refunds = crm_data.get("previous_refund_count", 0) # line 19
  amount = crm_data.get("order_amount", 0.0) # line 72
  ```
- **Description**: Dict lookup returns `None` if the database has a `NULL` value, causing runtime `TypeError` crashes when comparisons are performed.
- **Exact Fix Code**:
  Update `validation.py` to ensure type-safe fallbacks:
  ```python
  # line 6:
  days = crm_data.get("days_since_delivery")
  if days is None:
      days = 0
  ```
  ```python
  # line 19:
  refunds = crm_data.get("previous_refund_count")
  if refunds is None:
      refunds = 0
  ```
  ```python
  # line 72:
  amount = crm_data.get("order_amount")
  if amount is None:
      amount = 0.0
  ```

### 7. Vocalization of Emojis in Browser TTS Fallback
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\frontend\src\hooks\useVoice.js`
- **Line Numbers**: 127-128
- **Verbatim Code**:
  ```javascript
  const cleanText = text.replace(/[₹]/g, " Rupees ");
  const utterance = new SpeechSynthesisUtterance(cleanText);
  ```
- **Description**: The fallback browser SpeechSynthesis reads raw emojis aloud (e.g. "cross mark" instead of being silent), sounding unprofessional.
- **Exact Fix Code**:
  Modify lines 127-128 in `useVoice.js` to strip out standard emojis:
  ```javascript
  const cleanText = text
    .replace(/[₹]/g, " Rupees ")
    .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}]/gu, "");
  const utterance = new SpeechSynthesisUtterance(cleanText);
  ```

### 8. Lack of `SpeechRecognition` Component Unmount Cleanup
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\frontend\src\hooks\useVoice.js`
- **Line Numbers**: 14-45
- **Description**: The browser SpeechRecognition event listener effect lacks a return/cleanup function, which causes memory leaks and updates to unmounted components.
- **Exact Fix Code**:
  Add a cleanup return block to the `useEffect` on line 45:
  ```javascript
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (err) {
          console.error("Error aborting SpeechRecognition:", err);
        }
      }
    };
  ```

### 9. Incorrect Clause Citation for Cancellations in Mock Fallback
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\agent\nodes.py`
- **Line Number**: 373
- **Verbatim Code**:
  ```python
  else:
      clause = "Clauses Met"
  ```
- **Description**: For orders cancelled before shipment (governed by Clause 8), the fallback decision engine logs `"Clauses Met"` instead of referencing the correct policy `"Clause 8"`.
- **Exact Fix Code**:
  Replace line 373 with:
  ```python
  else:
      if crm and crm.get("order_status") == "cancelled" and crm.get("delivery_status") == "not_shipped":
          clause = "Clause 8"
      else:
          clause = "Clauses Met"
  ```

---

## 4. MISSING IMPLEMENTATIONS

### 10. Backend Conversation History State Preservation
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\backend\main.py`
- **Line Number**: 67
- **Verbatim Code**:
  ```python
  "conversation_history": [],
  ```
- **Description**: The `/chat` endpoint is stateless; it initializes the conversation history to an empty list on every API call, losing conversational context.
- **Exact Fix Code**:
  Implement an in-memory session history store inside `backend/main.py`:
  ```python
  # Add to top level of backend/main.py
  session_histories = {}
  ```
  And update `/chat` endpoint logic:
  ```python
  @app.post("/chat")
  async def chat_endpoint(req: ChatRequest):
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
          session_histories[req.session_id].append({"role": "user", "content": req.message})
          session_histories[req.session_id].append({"role": "assistant", "content": final_state.get("user_message", "")})
          
          return {
              "response": final_state.get("user_message", "I'm sorry, I was unable to resolve your request."),
              "decision": final_state.get("refund_decision", "DENY"),
              "session_id": req.session_id
          }
  ```

### 11. WebSocket Reconnection Logic in React Client
- **File Path**: `c:\Users\matta\OneDrive\Desktop\project1\refund-agent\frontend\src\hooks\useWebSocket.js`
- **Line Numbers**: 44-52
- **Description**: The WebSocket hook turns `isConnected` to `false` on close or error but never attempts reconnection, meaning the telemetry log feed breaks permanently if the server restarts.
- **Exact Fix Code**:
  Modify the `useEffect` block in `useWebSocket.js` to implement connection retries:
  ```javascript
  // Rewrite of useWebSocket useEffect logic:
  useEffect(() => {
    if (!sessionId) return;
    setLogs([]);

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = "localhost:8080";
    const wsUrl = `${wsProtocol}//${wsHost}/ws/${sessionId}`;
    
    let reconnectTimeout;

    const connect = () => {
      console.log(`Connecting to WebSocket: ${wsUrl}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connection established");
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const logEntry = JSON.parse(event.data);
          setLogs((prevLogs) => {
            const isDuplicate = prevLogs.some(
              (l) => l.timestamp === logEntry.timestamp && l.text === logEntry.text
            );
            if (isDuplicate) return prevLogs;
            return [...prevLogs, logEntry];
          });
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        console.log("WebSocket connection closed, retrying in 3 seconds...");
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsConnected(false);
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);
  ```

---

## 5. WHAT IS WORKING WELL

1. **3-Tier Resiliency Architecture**: The core fallback design is excellent. Even when Tier 1 (Gemini) fails, the local Ollama and local deterministic engines are triggered to ensure the user receives a response.
2. **Dynamic telemetry streaming**: Real-time websocket telemetry broadcasts log states (TOOL, CHECK, DECISION, RESPONSE) directly to the dashboard, providing transparency into the agent's reasoning.
3. **Robust Database Seeding**: Seeding data includes comprehensive representative customer personas (cancellation, damaged, high-value, abuse) that thoroughly map out the boundaries of the refund policies.
4. **FastAPI & ElevenLabs integration**: TTS streaming is highly responsive and configured using standard FastAPI streaming response wrappers.
5. **Secure Query Patterns**: Avoids dynamic string formatting for database operations, preventing SQL injection issues.

---

## 6. RECOMMENDED FIXES ORDER

To resolve the identified architectural and software defects efficiently:

1. **Fix model name typo** in `backend/agent/llm_client.py:38` to restore the primary Gemini AI model.
2. **Fix StateGraph routing** in `backend/agent/graph.py` to route intent mismatches directly to decision synthesis.
3. **Wrap SQLite connections in `finally` blocks** inside `tools.py` and `main.py` to prevent database locks.
4. **Implement backend startup database auto-seeding check** in `main.py` to bypass Docker Volume mount overrides.
5. **Implement stateful chat history** in `main.py` to preserve context across multiple conversation turns.
6. **Correct the WebSocket badge display** in `App.jsx` by binding it to `isConnected`.
7. **Clean up SpeechSynthesis emoji vocalization and SpeechRecognition cleanup** in `useVoice.js`.
8. **Add WebSocket auto-reconnect logic** in `useWebSocket.js`.
9. **Fix `validation.py` type safety** for potential database `None` values.
10. **Fix Clause 8 citation naming** inside `nodes.py:373`.
