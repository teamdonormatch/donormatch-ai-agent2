"""
Main coordinator: ties together donor selection, AI ranking, and outreach dispatch.
"""
import logging
from django.utils import timezone
from donors.models import Donor
from donors.services import get_compatible_blood_groups, rank_donors_with_ai
from emergency.models import DonorOutreach
from emergency.services import (
    initiate_vapi_call, trigger_n8n_emergency_workflow,
    notify_n8n_call_update, sync_to_supabase,
)

logger = logging.getLogger(__name__)

MAX_DONORS_TO_CONTACT = 5


def process_emergency_request(emergency_request) -> dict:
    """
    Full pipeline:
      1. Trigger n8n workflow
      2. Find compatible available donors
      3. AI-rank by proximity + intelligence factors
      4. Create outreach records
      5. Initiate VAPI calls
      6. Sync status to Supabase
    """
    result = {"request_id": emergency_request.pk, "steps": []}

    # Step 1 — Notify n8n
    n8n_resp = trigger_n8n_emergency_workflow(emergency_request)
    if n8n_resp.get("executionId"):
        emergency_request.n8n_execution_id = n8n_resp["executionId"]
    emergency_request.status = "processing"
    emergency_request.save()
    result["steps"].append({"step": "n8n_triggered", "response": n8n_resp})

    # Step 2 — Find compatible donors
    compatible_groups = get_compatible_blood_groups(emergency_request.blood_group_needed)
    candidates = list(
        Donor.objects.filter(
            blood_group__in=compatible_groups,
            status="available",
            is_active=True,
        ).exclude(
            outreaches__emergency_request=emergency_request
        )
    )

    if not candidates:
        emergency_request.status = "failed"
        emergency_request.save()
        result["steps"].append({"step": "no_donors_found"})
        return result

    result["steps"].append({"step": "candidates_found", "count": len(candidates)})

    # Step 3 — AI ranking
    hospital = emergency_request.hospital
    ranked = rank_donors_with_ai(
        candidates,
        hospital.latitude, hospital.longitude,
        emergency_request.blood_group_needed,
        emergency_request.urgency_level,
    )
    result["steps"].append({"step": "ai_ranking_complete", "ranked_count": len(ranked)})

    # Step 4 & 5 — Create outreach + initiate calls
    calls_initiated = 0
    for position, item in enumerate(ranked[:MAX_DONORS_TO_CONTACT], start=1):
        donor, score, distance_km = item[0], item[1], item[2]
        rationale = item[3] if len(item) > 3 else ""

        outreach = DonorOutreach.objects.create(
            emergency_request=emergency_request,
            donor=donor,
            ai_rank_score=score,
            rank_position=position,
            distance_km=distance_km,
            ai_ranking_rationale=rationale,
            call_status="queued",
        )

        try:
            call_resp = initiate_vapi_call(donor, emergency_request)
            outreach.vapi_call_id = call_resp.get("id", "")
            outreach.call_status = "initiated"
            outreach.contacted_at = timezone.now()
            donor.status = "contacted"
            donor.save()
            calls_initiated += 1
        except Exception as exc:
            logger.error("VAPI call failed for donor %s: %s", donor.pk, exc)
            outreach.call_status = "failed"

        outreach.save()
        notify_n8n_call_update(outreach, "call_initiated")

    emergency_request.status = "donors_contacted"
    emergency_request.save()

    # Step 6 — Supabase sync
    sync_to_supabase("emergency_requests", {
        "id": emergency_request.pk,
        "status": emergency_request.status,
        "blood_group": emergency_request.blood_group_needed,
        "hospital_name": hospital.name,
        "calls_initiated": calls_initiated,
        "updated_at": timezone.now().isoformat(),
    })

    result["steps"].append({"step": "calls_initiated", "count": calls_initiated})
    result["success"] = True
    return result
