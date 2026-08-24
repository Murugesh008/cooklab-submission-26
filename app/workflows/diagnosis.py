import json
import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

DIAGNOSIS_FIELDS = (
    "failed_step",
    "failure_type",
    "root_cause",
    "confidence",
    "recommended_actions",
    "maintenance_message",
)


def unavailable_diagnosis(reason: str) -> dict:
    return {
        "failed_step": "unknown",
        "failure_type": "diagnosis_unavailable",
        "root_cause": "AI diagnosis unavailable: " + reason,
        "confidence": 0.0,
        "recommended_actions": [
            "Review the workflow audit events and affected service logs.",
            "Verify service health and retry the failed workflow after recovery.",
        ],
        "maintenance_message": "Gemini could not produce an incident diagnosis; investigate using the recorded audit context.",
    }


def _service_health() -> dict[str, Any]:
    services = {
        "inventory": os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8001"),
        "crm": os.getenv("CRM_SERVICE_URL", "http://localhost:8002"),
        "notification": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8003"),
    }
    result = {}
    for name, url in services.items():
        try:
            response = requests.get(f"{url}/admin/status", timeout=2)
            result[name] = {"url": url, "online": response.ok, "details": response.json()}
        except Exception as exc:
            result[name] = {"url": url, "online": False, "error": str(exc)}
    return result


def diagnose_failed_workflow(workflow, audit_events) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return unavailable_diagnosis("GEMINI_API_KEY is not configured")

    context = {
        "workflow_id": workflow.id,
        "overall_status": workflow.status.value,
        "workflow_payload": workflow.payload or {},
        "executed_steps": [
            {
                "step": event.step,
                "event_type": event.event_type.value,
                "attempt": event.attempt,
                "timestamp": event.timestamp.isoformat(),
                "error": event.error_message,
                "metadata": event.event_data or {},
            }
            for event in audit_events
        ],
        "service_health": _service_health(),
    }
    prompt = (
        "Diagnose this failed workflow for a maintenance team. Explicitly identify the failed step "
        "and infer the likely root cause only from the supplied evidence. Recommend practical "
        "debugging or maintenance actions. Do not suggest changing files or executing commands. "
        "Return JSON with exactly these fields: failed_step, failure_type, root_cause, confidence "
        "(number from 0 to 1), recommended_actions (array of strings), maintenance_message.\n\n"
        + json.dumps(context, default=str)
    )
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
            },
            timeout=20,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        diagnosis = json.loads(text)
        if set(diagnosis) != set(DIAGNOSIS_FIELDS):
            raise ValueError("Gemini returned an unexpected diagnosis schema")
        diagnosis["confidence"] = max(0.0, min(1.0, float(diagnosis["confidence"])))
        if not isinstance(diagnosis["recommended_actions"], list):
            raise ValueError("recommended_actions must be an array")
        return {field: diagnosis[field] for field in DIAGNOSIS_FIELDS}
    except Exception as exc:
        logger.warning("Gemini incident diagnosis unavailable for workflow %s: %s", workflow.id, exc)
        return unavailable_diagnosis(str(exc))