import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END

from backend.agent.nodes import (
    fetch_customer_data,
    load_policy,
    classify_request_type,
    validate_refund_window,
    check_refund_history,
    check_delivery_status,
    check_order_value,
    make_decision,
    generate_response
)

# State Definition
class AgentState(TypedDict):
    customer_id: str
    user_message: str
    conversation_history: List[Dict[str, str]]
    crm_data: Optional[Dict[str, Any]]
    policy_rules: Optional[str]
    classification_result: Optional[str]
    refund_decision: Optional[str]
    denial_reason: Optional[str]
    reasoning_log: Annotated[List[str], operator.add]
    tool_calls_made: Annotated[List[str], operator.add]
    session_id: str

# Conditional Routing Helper Functions

def route_after_fetch(state: AgentState) -> str:
    """If customer data is not found in database, route directly to decision synthesis."""
    if state.get("crm_data") is None:
        return "make_decision"
    return "load_policy"

def route_after_window(state: AgentState) -> str:
    """If refund window check fails (decision is set), route to decision synthesis."""
    if state.get("refund_decision") is not None:
        return "make_decision"
    return "check_refund_history"

def route_after_history(state: AgentState) -> str:
    """If previous refunds check fails, route to decision synthesis."""
    if state.get("refund_decision") is not None:
        return "make_decision"
    return "check_delivery_status"

def route_after_delivery(state: AgentState) -> str:
    """If delivery status check fails, route to decision synthesis."""
    if state.get("refund_decision") is not None:
        return "make_decision"
    return "check_order_value"

def route_after_classification(state: AgentState) -> str:
    """If classification result is intent_mismatch, route directly to decision synthesis."""
    if state.get("classification_result") == "intent_mismatch":
        return "make_decision"
    return "validate_refund_window"

# StateGraph construction
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("fetch_customer_data", fetch_customer_data)
workflow.add_node("load_policy", load_policy)
workflow.add_node("classify_request_type", classify_request_type)
workflow.add_node("validate_refund_window", validate_refund_window)
workflow.add_node("check_refund_history", check_refund_history)
workflow.add_node("check_delivery_status", check_delivery_status)
workflow.add_node("check_order_value", check_order_value)
workflow.add_node("make_decision", make_decision)
workflow.add_node("generate_response", generate_response)

# Set Entry Point
workflow.set_entry_point("fetch_customer_data")

# Add Edges
workflow.add_conditional_edges(
    "fetch_customer_data",
    route_after_fetch,
    {
        "make_decision": "make_decision",
        "load_policy": "load_policy"
    }
)

workflow.add_edge("load_policy", "classify_request_type")
workflow.add_conditional_edges(
    "classify_request_type",
    route_after_classification,
    {
        "make_decision": "make_decision",
        "validate_refund_window": "validate_refund_window"
    }
)

workflow.add_conditional_edges(
    "validate_refund_window",
    route_after_window,
    {
        "make_decision": "make_decision",
        "check_refund_history": "check_refund_history"
    }
)

workflow.add_conditional_edges(
    "check_refund_history",
    route_after_history,
    {
        "make_decision": "make_decision",
        "check_delivery_status": "check_delivery_status"
    }
)

workflow.add_conditional_edges(
    "check_delivery_status",
    route_after_delivery,
    {
        "make_decision": "make_decision",
        "check_order_value": "check_order_value"
    }
)

workflow.add_edge("check_order_value", "make_decision")
workflow.add_edge("make_decision", "generate_response")
workflow.add_edge("generate_response", END)

# Compile Graph
agent_app = workflow.compile()
