import asyncio
import os
import sys

# Add backend to path so we can run from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.graph import agent_app

# Expected results mapping: Customer ID -> (Expected Decision, Scenario Description)
EXPECTED_DECISIONS = {
    "CUST001": ("APPROVE", "Clean refund (delivered 5 days ago, 0 prior refunds)"),
    "CUST002": ("DENY", "Delivered 35 days ago (past 30-day window)"),
    "CUST003": ("DENY", "Order in transit (not delivered yet)"),
    "CUST004": ("DENY", "3 previous refunds (abuse prevention limit met)"),
    "CUST005": ("DENY", "COD order with physical return not initiated"),
    "CUST006": ("PARTIAL", "Partial refund (damaged item, keeping product)"),
    "CUST007": ("ESCALATE", "High-value order > INR 10,000 (requires manager approval)"),
    "CUST008": ("APPROVE", "Order cancelled before shipment"),
    "CUST009": ("DENY", "Digital product purchase (non-refundable)"),
    "CUST010": ("APPROVE", "COD order with return completed/returned"),
    "CUST011": ("ESCALATE", "Disputed completed order (escalation check)"),
    "CUST012": ("DENY", "Multiple policy violations (past window & 3 prior refunds)"),
    "CUST013": ("APPROVE", "Clean refund with 1 prior refund"),
    "CUST014": ("PARTIAL", "Partial refund (damaged item, keeping product, value INR 5,000)"),
    "CUST015": ("DENY", "In transit and High-Value (first delivery status check fails)")
}

async def run_test_cases():
    print("=" * 80)
    print("RUNNING LANGRAPH AGENT TEST SUITE FOR 15 MOCK CUSTOMERS")
    print("=" * 80)
    
    passed_tests = 0
    failed_tests = 0
    
    for customer_id, (expected_decision, scenario) in EXPECTED_DECISIONS.items():
        print(f"\n[TEST] Running case for {customer_id}: {scenario}")
        
        initial_state = {
            "customer_id": customer_id,
            "user_message": "I would like to request a refund for my order.",
            "conversation_history": [],
            "crm_data": None,
            "policy_rules": None,
            "classification_result": None,
            "refund_decision": None,
            "denial_reason": None,
            "reasoning_log": [],
            "tool_calls_made": [],
            "session_id": f"test_{customer_id}"
        }
        
        try:
            # Execute the agent graph
            final_state = await agent_app.ainvoke(initial_state)
            actual_decision = final_state.get("refund_decision")
            actual_reason = final_state.get("denial_reason", "No reason provided.")
            
            if actual_decision == expected_decision:
                print(f"[PASS] {customer_id} returned expected decision '{actual_decision}'")
                passed_tests += 1
            else:
                print(f"[FAIL] {customer_id} expected '{expected_decision}', got '{actual_decision}'")
                print(f"   Reason details: {actual_reason}")
                failed_tests += 1
                
        except Exception as e:
            print(f"[ERR] ERROR running test for {customer_id}: {e}")
            failed_tests += 1

    # Run the custom subscription mismatch test case
    print("\n[TEST] Running intent mismatch test case for CUST001 (Subscription Mismatch)")
    mismatch_state = {
        "customer_id": "CUST001",
        "user_message": "I want to cancel my subscription",
        "conversation_history": [],
        "crm_data": None,
        "policy_rules": None,
        "classification_result": None,
        "refund_decision": None,
        "denial_reason": None,
        "reasoning_log": [],
        "tool_calls_made": [],
        "session_id": "test_mismatch"
    }
    try:
        final_state = await agent_app.ainvoke(mismatch_state)
        actual_decision = final_state.get("refund_decision")
        actual_response = final_state.get("user_message", "")
        
        if actual_decision == "DENY" and "Wireless Headphones" in actual_response and "subscription" in actual_response:
            print("[PASS] Intent Mismatch successfully caught and clarified!")
            passed_tests += 1
        else:
            print(f"[FAIL] Intent Mismatch failed. Decision: '{actual_decision}', Response: '{actual_response}'")
            failed_tests += 1
    except Exception as e:
        print(f"[ERR] ERROR running mismatch test: {e}")
        failed_tests += 1

    print("\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print(f"Total Run: {passed_tests + failed_tests}")
    print(f"Passed:    {passed_tests}")
    print(f"Failed:    {failed_tests}")
    print("=" * 80)
    
    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_test_cases())
