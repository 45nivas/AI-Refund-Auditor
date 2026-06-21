def check_refund_window(crm_data: dict) -> dict:
    """Check if the order is within the 30-day refund window from delivery date."""
    if crm_data.get("order_status") == "cancelled" and crm_data.get("delivery_status") == "not_shipped":
        return {"eligible": True, "reason": "Order cancelled before shipment. Window check bypassed."}
    
    days = crm_data.get("days_since_delivery")
    if days is None:
        days = 0
    if days > 30:
        return {
            "eligible": False, 
            "reason": f"Days since delivery is {days}, which exceeds the 30-day refund window limit (Clause 1)."
        }
    return {
        "eligible": True, 
        "reason": f"Days since delivery is {days}, which is within the 30-day window (Clause 1)."
    }

def check_refund_history(crm_data: dict) -> dict:
    """Check if the customer has reached the lifetime maximum of 3 refunds."""
    refunds = crm_data.get("previous_refund_count")
    if refunds is None:
        refunds = 0
    if refunds >= 3:
        return {
            "eligible": False, 
            "reason": f"Customer has {refunds} previous refund(s), reaching or exceeding the maximum limit of 3 refunds (Clause 2)."
        }
    return {
        "eligible": True, 
        "reason": f"Customer has {refunds} previous refund(s), which is under the limit of 3 refunds (Clause 2)."
    }

def check_delivery_status(crm_data: dict) -> dict:
    """Check if delivery status is eligible for refund (must be delivered unless cancelled)."""
    # If order is cancelled and not shipped, it is eligible
    if crm_data.get("order_status") == "cancelled" and crm_data.get("delivery_status") == "not_shipped":
        return {"eligible": True, "reason": "Order is cancelled and not shipped, eligible for refund."}
    
    status = crm_data.get("delivery_status")
    if status == "in_transit":
        return {
            "eligible": False, 
            "reason": "Order status is 'in_transit'. Refunds are not eligible until the order is delivered (Clause 5)."
        }
    elif status == "not_shipped":
        return {
            "eligible": False, 
            "reason": "Order has not been shipped yet and is not cancelled. Standard refund is not eligible."
        }
    
    return {
        "eligible": True, 
        "reason": "Order delivery status is 'delivered', eligible for refund check (Clause 5)."
    }

def check_payment_method_and_return(crm_data: dict) -> dict:
    """Check if COD orders have initiated a physical return."""
    if crm_data.get("order_status") == "cancelled" and crm_data.get("delivery_status") == "not_shipped":
        return {"eligible": True, "reason": "Order cancelled before shipment. COD return check bypassed."}

    pay_method = crm_data.get("payment_method")
    ret_status = crm_data.get("return_status")
    if pay_method == "COD" and ret_status not in ["returned", "initiated"]:
        return {
            "eligible": False, 
            "reason": "COD payment method requires a physical return to be initiated or returned before refund approval (Clause 3)."
        }
    return {
        "eligible": True, 
        "reason": "Payment method requirements met. COD return has been initiated/returned or order is pre-paid (Clause 3)."
    }

def check_order_value_escalation(crm_data: dict) -> dict:
    """Check if the order value exceeds ₹10,000 or is disputed, requiring escalation."""
    amount = crm_data.get("order_amount")
    if amount is None:
        amount = 0.0
    status = crm_data.get("order_status", "")
    
    if amount > 10000.0:
        return {
            "escalate": True, 
            "reason": f"Order amount is ₹{amount:,.2f}, which exceeds the auto-approval limit of ₹10,000 and requires manager approval (Clause 4)."
        }
    if status == "disputed":
        return {
            "escalate": True,
            "reason": "Order status is 'disputed' in CRM. All disputed orders require manager review."
        }
    return {
        "escalate": False, 
        "reason": f"Order amount is ₹{amount:,.2f}, within the ₹10,000 automatic limit (Clause 4)."
    }

def check_product_type(crm_data: dict) -> dict:
    """Check if the product is a non-refundable digital item."""
    if crm_data.get("is_digital") == 1:
        return {
            "eligible": False, 
            "reason": f"Product '{crm_data.get('product_name')}' is a digital product and is strictly non-refundable (Clause 6)."
        }
    return {
        "eligible": True, 
        "reason": f"Product '{crm_data.get('product_name')}' is a physical product, eligible for refund check (Clause 6)."
    }

def evaluate_all_rules(crm_data: dict) -> dict:
    """Runs all rules in sequence and returns a structured diagnostic dictionary."""
    results = {}
    
    # 1. Product type check
    prod_check = check_product_type(crm_data)
    results["product_type"] = prod_check
    
    # 2. Delivery status check
    delivery_check = check_delivery_status(crm_data)
    results["delivery_status"] = delivery_check
    
    # 3. Window check
    window_check = check_refund_window(crm_data)
    results["refund_window"] = window_check
    
    # 4. History check
    history_check = check_refund_history(crm_data)
    results["refund_history"] = history_check
    
    # 5. COD check
    cod_check = check_payment_method_and_return(crm_data)
    results["cod_return"] = cod_check
    
    # 6. Escalation check
    escalate_check = check_order_value_escalation(crm_data)
    results["escalation"] = escalate_check

    # Synthesize overall eligibility
    all_eligible = (
        prod_check["eligible"] and 
        delivery_check["eligible"] and 
        window_check["eligible"] and 
        history_check["eligible"] and 
        cod_check["eligible"]
    )
    
    results["eligible"] = all_eligible
    
    # Determine immediate decision outcome if we want to auto-triage
    if not all_eligible:
        results["suggested_decision"] = "DENY"
        # Extract first failure reason
        reasons = []
        if not prod_check["eligible"]: reasons.append(prod_check["reason"])
        if not delivery_check["eligible"]: reasons.append(delivery_check["reason"])
        if not window_check["eligible"]: reasons.append(window_check["reason"])
        if not history_check["eligible"]: reasons.append(history_check["reason"])
        if not cod_check["eligible"]: reasons.append(cod_check["reason"])
        results["reason"] = "; ".join(reasons)
    elif escalate_check["escalate"]:
        results["suggested_decision"] = "ESCALATE"
        results["reason"] = escalate_check["reason"]
    else:
        # Check if item condition is damaged (partial refund clause)
        if crm_data.get("item_condition") == "damaged" and crm_data.get("return_status") != "returned":
            results["suggested_decision"] = "PARTIAL"
            results["reason"] = f"Item is damaged and customer is keeping product. Eligible for 50% partial refund of ₹{crm_data.get('order_amount')/2:,.2f} (Clause 7)."
        else:
            results["suggested_decision"] = "APPROVE"
            results["reason"] = "All validation criteria successfully met."

    return results
