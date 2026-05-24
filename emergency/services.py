"""
Emergency coordination services: VAPI voice calls, n8n webhooks, workflow orchestration.
"""
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── VAPI Voice Call Integration ──────────────────────────────────────────────

def initiate_vapi_call(donor, emergency_request) -> dict:
    """
    Trigger an outbound AI voice call via VAPI to a donor.
    Returns the VAPI call object or raises on failure.
    """
    message = (
        f"Hello {donor.first_name}, this is an urgent automated call from the "
        f"BloodCoord emergency system. A patient at {emergency_request.hospital.name} "
        f"urgently needs {emergency_request.blood_group_needed} blood. "
        f"You are a compatible donor in our database. "
        f"If you are available to donate, please press 1 or say YES. "
        f"If you are unable to donate at this time, press 2 or say NO. "
        f"Your response will be recorded immediately. Thank you for your generosity."
    )

    payload = json.dumps({
        "phoneNumberId": settings.VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": donor.phone,
            "name": donor.full_name,
        },
        "assistant": {
            "firstMessage": message,
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "system",
                    "content": (
                        "You are an emergency blood donation coordinator. "
                        "You are calling a blood donor to request urgent donation. "
                        "Be empathetic, clear, and brief. Record their yes/no response."
                    )
                }]
            },
            "voice": {"provider": "11labs", "voiceId": "rachel"},
        },
        "metadata": {
            "emergency_request_id": str(emergency_request.pk),
            "donor_id": str(donor.pk),
        }
    }).encode()

    req = urllib.request.Request(
        "https://api.vapi.ai/call/phone",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.VAPI_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ── n8n Workflow Webhooks ─────────────────────────────────────────────────────

def trigger_n8n_emergency_workflow(emergency_request) -> dict:
    """
    POST the emergency request payload to n8n to kick off the full workflow.
    n8n orchestrates: fetch donors → rank with AI → initiate VAPI calls → monitor responses.
    """
    payload = json.dumps({
        "event": "emergency_blood_request",
        "request_id": emergency_request.pk,
        "hospital": {
            "id": emergency_request.hospital.pk,
            "name": emergency_request.hospital.name,
            "latitude": emergency_request.hospital.latitude,
            "longitude": emergency_request.hospital.longitude,
        },
        "blood_group_needed": emergency_request.blood_group_needed,
        "units_needed": emergency_request.units_needed,
        "urgency_level": emergency_request.urgency_level,
        "patient_condition": emergency_request.patient_condition,
        "timestamp": emergency_request.created_at.isoformat(),
    }).encode()

    req = urllib.request.Request(
        f"{settings.N8N_WEBHOOK_URL}/emergency-blood-request",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("n8n webhook failed: %s", exc)
        return {"status": "webhook_unavailable", "error": str(exc)}


def notify_n8n_call_update(outreach, event: str) -> None:
    """Send call status updates back to n8n for monitoring and escalation logic."""
    payload = json.dumps({
        "event": event,
        "outreach_id": outreach.pk,
        "emergency_request_id": outreach.emergency_request.pk,
        "donor_id": outreach.donor.pk,
        "call_status": outreach.call_status,
        "vapi_call_id": outreach.vapi_call_id,
        "timestamp": timezone.now().isoformat(),
    }).encode()

    req = urllib.request.Request(
        f"{settings.N8N_WEBHOOK_URL}/call-status-update",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as exc:
        logger.warning("n8n call update webhook failed: %s", exc)


# ── Supabase Sync ─────────────────────────────────────────────────────────────

def sync_to_supabase(table: str, data: dict) -> dict:
    """
    Upsert a record to Supabase for cross-system access (e.g. n8n reads from here).
    """
    payload = json.dumps([data]).encode()
    req = urllib.request.Request(
        f"{settings.SUPABASE_URL}/rest/v1/{table}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Prefer": "resolution=merge-duplicates",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return json.loads(body) if body else {"status": "ok"}
    except Exception as exc:
        logger.warning("Supabase sync failed for table %s: %s", table, exc)
        return {"status": "sync_failed", "error": str(exc)}
