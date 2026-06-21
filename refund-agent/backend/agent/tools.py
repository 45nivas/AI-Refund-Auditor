import os
import sqlite3
from langchain_core.tools import tool
from backend.agent.validation import evaluate_all_rules

def get_db_paths():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    crm_db = os.path.join(backend_dir, "data", "crm.db")
    decisions_db = os.path.join(backend_dir, "data", "decisions.db")
    policy_file = os.path.join(backend_dir, "data", "refund_policy.txt")
    return crm_db, decisions_db, policy_file

@tool
def get_customer_profile(customer_id_or_email: str) -> dict:
    """Fetch the CRM customer profile details using customer ID or email address.
    Returns customer metadata, order status, payment method, delivery status, and previous refund count.
    """
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
def get_refund_policy() -> str:
    """Fetch the store's refund policy rules as a text document containing instructions and clauses."""
    _, _, policy_path = get_db_paths()
    if os.path.exists(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Refund policy file not found."

@tool
def check_eligibility(customer_id: str) -> dict:
    """Evaluate all deterministic policy constraints for a customer (window, refund limits, COD status).
    Returns a dictionary of check results indicating whether the request is eligible, partial, or escalated.
    """
    profile = get_customer_profile.func(customer_id)
    if "error" in profile:
        return profile
    
    return evaluate_all_rules(profile)

@tool
def log_decision(customer_id: str, decision: str, reason: str, agent_notes: str = "") -> bool:
    """Log the final refund decision (APPROVE, DENY, ESCALATE, PARTIAL) to the admin database table.
    Must be called for every resolved request.
    """
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
