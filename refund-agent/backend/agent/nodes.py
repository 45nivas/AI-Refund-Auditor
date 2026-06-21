import os
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import Literal

from backend.agent.websocket_manager import manager
from backend.agent.tools import get_customer_profile, get_refund_policy, log_decision
import backend.agent.validation as val
from backend.agent.prompts import CLASSIFICATION_PROMPT, DECISION_PROMPT, RESPONSE_PROMPT
from backend.agent.llm_client import query_three_tier_llm

# Pydantic Schemas for Structured Outputs
class ClassificationResponse(BaseModel):
    request_type: Literal["standard_refund", "damaged_item", "cancellation", "abuse", "out_of_policy", "intent_mismatch"] = Field(
        description="The category of the customer request."
    )
    explanation: str = Field(
        description="A brief explanation of why this classification was chosen."
    )

class DecisionResponse(BaseModel):
    decision: Literal["APPROVE", "DENY", "ESCALATE", "PARTIAL"] = Field(
        description="The final refund decision."
    )
    policy_clause_cited: str = Field(
        description="Specific policy clause cited from the policy rules, e.g., 'Clause 1', 'Clause 4'."
    )
    reason: str = Field(
        description="Detailed reason for this decision, referencing customer profile data and policy rules."
    )
    agent_notes: str = Field(
        description="Internal agent notes or details explaining the auditing decision."
    )

class ChatResponse(BaseModel):
    customer_message: str = Field(
        description="The empathetic, polite, and professional customer-facing response message."
    )
    agent_notes: str = Field(
        description="Internal logs or notes on the customer interaction style."
    )

# Nodes implementation

async def fetch_customer_data(state: Dict[str, Any]) -> Dict[str, Any]:
    customer_id = state.get("customer_id", "")
    session_id = state.get("session_id", "default")
    logs = []
    
    msg = f"Fetching CRM record for customer '{customer_id}'..."
    logs.append(f"[TOOL] {msg}")
    await manager.broadcast("TOOL", msg, session_id)
    
    # Tool call
    profile = get_customer_profile.func(customer_id_or_email=customer_id)
    
    if "error" in profile:
        err_msg = f"Customer profile not found for '{customer_id}'."
        logs.append(f"[ERROR] {err_msg}")
        await manager.broadcast("ERROR", err_msg, session_id)
        return {
            "crm_data": None,
            "reasoning_log": logs,
            "tool_calls_made": ["get_customer_profile"]
        }
    
    success_msg = f"Retrieved profile for {profile['name']} ({profile['email']}). Order ID: {profile['order_id']}."
    logs.append(f"[TOOL] {success_msg}")
    await manager.broadcast("TOOL", success_msg, session_id)
    
    return {
        "crm_data": profile,
        "reasoning_log": logs,
        "tool_calls_made": ["get_customer_profile"]
    }

async def load_policy(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    logs = []
    
    msg = "Loading refund policy document..."
    logs.append(f"[TOOL] {msg}")
    await manager.broadcast("TOOL", msg, session_id)
    
    policy_text = get_refund_policy.func()
    
    success_msg = "Refund policy rules parsed successfully."
    logs.append(f"[TOOL] {success_msg}")
    await manager.broadcast("TOOL", success_msg, session_id)
    
    return {
        "policy_rules": policy_text,
        "reasoning_log": logs,
        "tool_calls_made": ["get_refund_policy"]
    }

async def classify_request_type(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    user_msg = state.get("user_message", "")
    crm = state.get("crm_data")
    logs = []
    
    msg = "Analyzing message intent and history..."
    logs.append(f"[TOOL] {msg}")
    await manager.broadcast("TOOL", msg, session_id)
    
    history_str = json.dumps(state.get("conversation_history", []))
    crm_str = json.dumps(crm) if crm else "No CRM profile loaded"
    user_prompt = f"Customer CRM Profile: {crm_str}\nConversation History: {history_str}\nNew Message: {user_msg}"
    
    # Run 3-tier LLM query
    result = await query_three_tier_llm(
        system_prompt=CLASSIFICATION_PROMPT,
        user_prompt=user_prompt,
        schema_class=ClassificationResponse,
        session_id=session_id,
        logs=logs
    )
    
    if result is None:
        # Tier 3 fallback: Deterministic Mock Fallback
        explanation = "Deterministic Fallback Engine (Mock Mode). "
        if crm and not crm.get("is_digital", 0) and ("subscription" in user_msg.lower() or "subscribe" in user_msg.lower()):
            req_type = "intent_mismatch"
            explanation += f"Detected subscription request for physical item '{crm.get('product_name')}'."
        elif crm and crm.get("item_condition") == "damaged":
            req_type = "damaged_item"
            explanation += "Detected damaged item from CRM metadata."
        elif crm and crm.get("order_status") == "cancelled":
            req_type = "cancellation"
            explanation += "Detected cancelled order status."
        elif crm and crm.get("previous_refund_count", 0) >= 3:
            req_type = "abuse"
            explanation += "High previous refund count suggests potential abuse request."
        elif "cancel" in user_msg.lower() or "cancellation" in user_msg.lower():
            req_type = "cancellation"
            explanation += "User message contains cancellation request."
        elif "damage" in user_msg.lower() or "broken" in user_msg.lower() or "defective" in user_msg.lower():
            req_type = "damaged_item"
            explanation += "User message contains damage-related terms."
        else:
            req_type = "standard_refund"
            explanation += "Categorized request as a standard refund."
            
        result = ClassificationResponse(request_type=req_type, explanation=explanation)

    check_msg = f"Classified request as: {result.request_type.upper()} — {result.explanation}"
    logs.append(f"[CHECK] {check_msg}")
    await manager.broadcast("CHECK", check_msg, session_id)
    
    ret = {
        "classification_result": result.request_type,
        "reasoning_log": logs
    }
    
    if result.request_type == "intent_mismatch":
        prod_name = crm.get("product_name", "physical item") if crm else "physical item"
        ret["refund_decision"] = "DENY"
        ret["denial_reason"] = f"Intent mismatch: Customer requested subscription cancellation but holds order for physical item '{prod_name}'."
        
    return ret

async def validate_refund_window(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    logs = []
    
    if not crm:
        return {}
    
    msg = "Evaluating refund window policy..."
    logs.append(f"[CHECK] {msg}")
    await manager.broadcast("CHECK", msg, session_id)
    
    check_res = val.check_refund_window(crm)
    
    if not check_res["eligible"]:
        fail_msg = f"Days since delivery: {crm.get('days_since_delivery')} — exceeds 30-day window limit."
        logs.append(f"[CHECK] {fail_msg}")
        await manager.broadcast("CHECK", fail_msg, session_id)
        return {
            "refund_decision": "DENY",
            "denial_reason": check_res["reason"],
            "reasoning_log": logs
        }
    
    pass_msg = f"Days since delivery: {crm.get('days_since_delivery')} — within 30-day window."
    logs.append(f"[CHECK] {pass_msg}")
    await manager.broadcast("CHECK", pass_msg, session_id)
    return {
        "reasoning_log": logs
    }

async def check_refund_history(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    logs = []
    
    if not crm:
        return {}
        
    msg = "Evaluating customer lifetime refund history..."
    logs.append(f"[CHECK] {msg}")
    await manager.broadcast("CHECK", msg, session_id)
    
    check_res = val.check_refund_history(crm)
    
    if not check_res["eligible"]:
        fail_msg = f"Previous refund count: {crm.get('previous_refund_count')} — exceeds max limit of 3 refunds."
        logs.append(f"[CHECK] {fail_msg}")
        await manager.broadcast("CHECK", fail_msg, session_id)
        return {
            "refund_decision": "DENY",
            "denial_reason": check_res["reason"],
            "reasoning_log": logs
        }
        
    pass_msg = f"Previous refund count: {crm.get('previous_refund_count')} — within limit."
    logs.append(f"[CHECK] {pass_msg}")
    await manager.broadcast("CHECK", pass_msg, session_id)
    return {
        "reasoning_log": logs
    }

async def check_delivery_status(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    logs = []
    
    if not crm:
        return {}
        
    msg = "Evaluating order delivery status..."
    logs.append(f"[CHECK] {msg}")
    await manager.broadcast("CHECK", msg, session_id)
    
    check_res = val.check_delivery_status(crm)
    
    if not check_res["eligible"]:
        fail_msg = f"Delivery status: '{crm.get('delivery_status')}' — not eligible for standard refund."
        logs.append(f"[CHECK] {fail_msg}")
        await manager.broadcast("CHECK", fail_msg, session_id)
        return {
            "refund_decision": "DENY",
            "denial_reason": check_res["reason"],
            "reasoning_log": logs
        }
        
    pass_msg = f"Delivery status: '{crm.get('delivery_status')}' — eligible."
    logs.append(f"[CHECK] {pass_msg}")
    await manager.broadcast("CHECK", pass_msg, session_id)
    return {
        "reasoning_log": logs
    }

async def check_order_value(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    logs = []
    
    if not crm:
        return {}
        
    msg = "Evaluating transaction value escalation limits..."
    logs.append(f"[CHECK] {msg}")
    await manager.broadcast("CHECK", msg, session_id)
    
    check_res = val.check_order_value_escalation(crm)
    
    if check_res["escalate"]:
        esc_msg = f"Order value: ₹{crm.get('order_amount')} — exceeds the ₹10,000 auto-approval threshold."
        logs.append(f"[CHECK] {esc_msg}")
        await manager.broadcast("CHECK", esc_msg, session_id)
        return {
            "refund_decision": "ESCALATE",
            "denial_reason": check_res["reason"],
            "reasoning_log": logs
        }
        
    pass_msg = f"Order value: ₹{crm.get('order_amount')} — within limits."
    logs.append(f"[CHECK] {pass_msg}")
    await manager.broadcast("CHECK", pass_msg, session_id)
    return {
        "reasoning_log": logs
    }

async def make_decision(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    policy = state.get("policy_rules", "")
    classification = state.get("classification_result", "standard_refund")
    pre_decision = state.get("refund_decision")
    pre_reason = state.get("denial_reason")
    logs = []
    
    # Check if a customer was not loaded
    if not crm:
        msg = "No customer loaded. Directing to response generation."
        logs.append(f"[DECISION] DENY — {msg}")
        await manager.broadcast("DECISION", f"DENY — {msg}", session_id)
        return {
            "refund_decision": "DENY",
            "denial_reason": "Customer profile not found.",
            "reasoning_log": logs
        }

    msg = "Auditing all parameters and synthesizing final policy decision..."
    logs.append(f"[TOOL] {msg}")
    await manager.broadcast("TOOL", msg, session_id)
    
    # If short-circuited by a validation node
    if pre_decision:
        dec_msg = f"{pre_decision} — {pre_reason}"
        logs.append(f"[DECISION] {dec_msg}")
        await manager.broadcast("DECISION", dec_msg, session_id)
        
        # Log to decisions DB
        log_decision.func(
            customer_id=crm["customer_id"],
            decision=pre_decision,
            reason=pre_reason,
            agent_notes="Auto-decision triggered by deterministic validation nodes."
        )
        
        return {
            "reasoning_log": logs,
            "tool_calls_made": ["log_decision"]
        }
        
    # Standard evaluation path
    det_results = val.evaluate_all_rules(crm)
    user_prompt = DECISION_PROMPT.format(
        crm_data=json.dumps(crm),
        policy_rules=policy,
        classification_result=classification,
        eligibility_result=json.dumps(det_results)
    )
    
    # Run 3-tier LLM query
    result = await query_three_tier_llm(
        system_prompt="You are an expert e-commerce refund compliance auditor. Verify all policy clauses and output only valid JSON.",
        user_prompt=user_prompt,
        schema_class=DecisionResponse,
        session_id=session_id,
        logs=logs
    )
    
    if result is None:
        # Tier 3 fallback: Deterministic Mock Fallback
        decision = det_results["suggested_decision"]
        reason = det_results["reason"]
        
        # Determine policy clause
        if decision == "DENY":
            if "window" in reason.lower():
                clause = "Clause 1"
            elif "refund" in reason.lower():
                clause = "Clause 2"
            elif "cod" in reason.lower():
                clause = "Clause 3"
            elif "digital" in reason.lower():
                clause = "Clause 6"
            elif "transit" in reason.lower() or "delivery" in reason.lower():
                clause = "Clause 5"
            else:
                clause = "General Policy Violation"
        elif decision == "ESCALATE":
            clause = "Clause 4"
        elif decision == "PARTIAL":
            clause = "Clause 7"
        else:
            if crm and crm.get("order_status") == "cancelled" and crm.get("delivery_status") == "not_shipped":
                clause = "Clause 8"
            else:
                clause = "Clauses Met"
            
        result = DecisionResponse(
            decision=decision,
            policy_clause_cited=clause,
            reason=reason,
            agent_notes="Fallback decision engine. Verified all policy clauses deterministically."
        )

    dec_msg = f"{result.decision} — {result.reason} ({result.policy_clause_cited})"
    logs.append(f"[DECISION] {dec_msg}")
    await manager.broadcast("DECISION", dec_msg, session_id)
    
    # Log to decisions DB
    log_decision.func(
        customer_id=crm["customer_id"],
        decision=result.decision,
        reason=f"{result.reason} ({result.policy_clause_cited})",
        agent_notes=result.agent_notes
    )
    
    return {
        "refund_decision": result.decision,
        "denial_reason": result.reason,
        "reasoning_log": logs,
        "tool_calls_made": ["log_decision"]
    }

async def generate_response(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("session_id", "default")
    crm = state.get("crm_data")
    decision = state.get("refund_decision", "DENY")
    reason = state.get("denial_reason", "Policy checks not met.")
    logs = []
    
    msg = "Generating customer-facing response message..."
    logs.append(f"[RESPONSE] {msg}")
    await manager.broadcast("RESPONSE", msg, session_id)
    
    # Check if customer not loaded
    if not crm:
        response_msg = "Hello, I was unable to find your customer profile or order details in our database. Please double-check your Customer ID or email and try again."
        logs.append(f"[RESPONSE] Completed generation.")
        return {
            "user_message": response_msg,
            "reasoning_log": logs
        }
        
    user_prompt = RESPONSE_PROMPT.format(
        decision=decision,
        reason=reason,
        crm_data=json.dumps(crm)
    )
    
    # Run 3-tier LLM query
    result = await query_three_tier_llm(
        system_prompt="You are an empathetic, professional customer service agent representing an e-commerce platform.",
        user_prompt=user_prompt,
        schema_class=ChatResponse,
        session_id=session_id,
        logs=logs
    )
    
    if result is None:
        # Tier 3 fallback: Deterministic Mock Fallback
        name = crm.get("name", "Customer")
        product = crm.get("product_name", "product")
        amount = crm.get("order_amount", 0.0)
        
        classification = state.get("classification_result")
        if classification == "intent_mismatch":
            response_msg = f"I see you have {product} on your account, not a subscription. Did you mean to request a refund for that order?"
        elif decision == "APPROVE":
            response_msg = f"Hi {name}, I have approved a full refund of ₹{amount:,.2f} for your order {crm.get('order_id')} ({product}). The refund has been initiated and should reflect back in your payment method in 5-7 business days."
        elif decision == "DENY":
            response_msg = f"Hi {name}, thank you for contacting support regarding your order {crm.get('order_id')} ({product}). Unfortunately, we are unable to approve your refund request at this time. Reason: {reason}."
        elif decision == "PARTIAL":
            response_msg = f"Hi {name}, I see that your order {crm.get('order_id')} ({product}) arrived damaged. Since you mentioned you would like to keep the item, you are eligible for a 50% partial refund of ₹{amount/2:,.2f}. If you accept this resolution, please let me know, and I will process it immediately! Alternatively, you can ship the product back to us for a full 100% refund."
        else: # ESCALATE
            response_msg = f"Hi {name}, because the value of your order {crm.get('order_id')} ({product}) is ₹{amount:,.2f} (which exceeds our threshold) or because of your account status, your refund request requires manual manager review. I have escalated this case to our operations team. A manager will contact you within 24 hours with an update."
            
        result = ChatResponse(customer_message=response_msg, agent_notes="Generated conversational fallback response.")

    logs.append(f"[RESPONSE] Completed generation.")
    
    return {
        "user_message": result.customer_message,
        "reasoning_log": logs
    }
