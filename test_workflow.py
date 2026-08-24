import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_full_workflow_with_recovery():
    print("--- 1. Testing Normal Execution ---")
    res = requests.post(f"{BASE_URL}/api/order/create", json={
        "customer_email": "test_user@example.com",
        "sku": "ITEM-001",
        "quantity": 2
    })
    order_data = res.json()
    order_id = order_data["order_id"]
    print(f"Created Order: {order_id}, Status: {order_data['status']}")
    
    # Query history
    hist = requests.get(f"{BASE_URL}/api/order/history/{order_id}").json()
    print(f"Final Status: {hist['status']}")
    for evt in hist["events"]:
        print(f"  [{evt['step'] or 'ORCHESTRATOR'}] {evt['event_type']} - Attempt {evt['attempt']}")

    print("\n--- 2. Simulating CRM Service Failure ---")
    requests.post(f"{BASE_URL}/api/admin/services/crm/simulate-failure")
    print("CRM failure simulation enabled.")

    print("\n--- 3. Triggering Workflow with CRM Down ---")
    res_fail = requests.post(f"{BASE_URL}/api/order/create", json={
        "customer_email": "fail_demo@example.com",
        "sku": "ITEM-002",
        "quantity": 1
    })
    order_fail_id = res_fail.json()["order_id"]

    hist_fail = requests.get(f"{BASE_URL}/api/order/history/{order_fail_id}").json()
    print(f"Fault-Tolerant Status: {hist_fail['status']}")
    for evt in hist_fail["events"]:
        print(f"  [{evt['step'] or 'ORCHESTRATOR'}] {evt['event_type']} - Attempt {evt['attempt']} | {evt.get('error_message') or 'OK'}")

    print("\n--- 4. Recovering CRM Service ---")
    requests.post(f"{BASE_URL}/api/admin/services/crm/recover")
    print("CRM Service recovered.")

if __name__ == "__main__":
    test_full_workflow_with_recovery()
