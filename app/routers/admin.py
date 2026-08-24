"""
Admin & Failure Simulation API routes for Orchestrator.
Allows the dashboard UI to monitor and simulate failures on downstream services.
"""
from fastapi import APIRouter, HTTPException
import requests
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

SERVICE_URLS = {
    "inventory": os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8001"),
    "crm": os.getenv("CRM_SERVICE_URL", "http://localhost:8002"),
    "notification": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8003"),
}

@router.get("/services/status")
def get_all_services_status():
    """Query health & failure simulation status for all 3 independent services."""
    results = {}
    for service_name, base_url in SERVICE_URLS.items():
        try:
            resp = requests.get(f"{base_url}/admin/status", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                results[service_name] = {
                    "online": True,
                    "is_failed": data.get("is_failed", False),
                    "failure_message": data.get("failure_message", ""),
                    "url": base_url
                }
            else:
                results[service_name] = {"online": False, "is_failed": True, "error": f"HTTP {resp.status_code}", "url": base_url}
        except Exception as e:
            results[service_name] = {"online": False, "is_failed": True, "error": str(e), "url": base_url}
    return results

@router.post("/services/{service_name}/simulate-failure")
def simulate_service_failure(service_name: str):
    """Trigger simulated failure mode on target service."""
    if service_name not in SERVICE_URLS:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service_name}")
    
    base_url = SERVICE_URLS[service_name]
    try:
        resp = requests.post(f"{base_url}/admin/simulate-failure", timeout=3)
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to reach {service_name} at {base_url}: {e}")
        raise HTTPException(status_code=502, detail=f"Could not connect to {service_name}: {str(e)}")

@router.post("/services/{service_name}/recover")
def recover_service(service_name: str):
    """Reset failure simulation mode on target service."""
    if service_name not in SERVICE_URLS:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service_name}")
    
    base_url = SERVICE_URLS[service_name]
    try:
        resp = requests.post(f"{base_url}/admin/recover", timeout=3)
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to reach {service_name} at {base_url}: {e}")
        raise HTTPException(status_code=502, detail=f"Could not connect to {service_name}: {str(e)}")
