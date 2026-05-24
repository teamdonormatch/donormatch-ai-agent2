import json
import logging
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from donors.models import Donor
from emergency.models import EmergencyRequest, Hospital, DonorOutreach
from emergency.coordinator import process_emergency_request

logger = logging.getLogger(__name__)


# ── REST API Views ────────────────────────────────────────────────────────────

class EmergencyRequestCreateView(APIView):
    """POST /api/emergency/ — submit a new blood request and trigger the full workflow."""

    def post(self, request):
        data = request.data
        try:
            hospital = Hospital.objects.get(pk=data["hospital_id"])
        except Hospital.DoesNotExist:
            return Response({"error": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)

        er = EmergencyRequest.objects.create(
            hospital=hospital,
            blood_group_needed=data["blood_group_needed"],
            units_needed=data.get("units_needed", 1),
            urgency_level=data.get("urgency_level", "urgent"),
            patient_condition=data.get("patient_condition", ""),
        )

        result = process_emergency_request(er)
        return Response({"request_id": er.pk, "workflow": result}, status=status.HTTP_201_CREATED)


class EmergencyRequestDetailView(APIView):
    """GET /api/emergency/<pk>/ — status of an emergency request."""

    def get(self, request, pk):
        try:
            er = EmergencyRequest.objects.prefetch_related(
                "outreaches__donor", "hospital"
            ).get(pk=pk)
        except EmergencyRequest.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        outreaches = [
            {
                "donor": f"{o.donor.first_name} {o.donor.last_name}",
                "blood_group": o.donor.blood_group,
                "distance_km": o.distance_km,
                "rank": o.rank_position,
                "score": o.ai_rank_score,
                "call_status": o.call_status,
                "rationale": o.ai_ranking_rationale,
            }
            for o in er.outreaches.all()
        ]

        return Response({
            "id": er.pk,
            "hospital": er.hospital.name,
            "blood_group_needed": er.blood_group_needed,
            "units_needed": er.units_needed,
            "urgency_level": er.urgency_level,
            "status": er.status,
            "created_at": er.created_at,
            "outreaches": outreaches,
        })


# ── Webhook Endpoints ─────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def vapi_webhook(request):
    """
    POST /webhooks/vapi/ — receives call status updates from VAPI AI.
    Updates outreach records and triggers escalation via n8n if needed.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = payload.get("type", "")
    call = payload.get("call", {})
    metadata = call.get("metadata", {})

    vapi_call_id = call.get("id", "")
    donor_id = metadata.get("donor_id")
    er_id = metadata.get("emergency_request_id")

    logger.info("VAPI webhook: %s for call %s", event_type, vapi_call_id)

    if not vapi_call_id:
        return JsonResponse({"status": "ignored"})

    try:
        outreach = DonorOutreach.objects.get(vapi_call_id=vapi_call_id)
    except DonorOutreach.DoesNotExist:
        logger.warning("Outreach not found for VAPI call ID %s", vapi_call_id)
        return JsonResponse({"status": "not_found"})

    status_map = {
        "call-started": "in_progress",
        "call-ended": "completed",
        "no-answer": "no_answer",
    }

    if event_type in status_map:
        outreach.call_status = status_map[event_type]

    if event_type == "call-ended":
        outreach.responded_at = timezone.now()
        duration = call.get("endedAt", 0)
        if isinstance(duration, (int, float)):
            outreach.call_duration_seconds = int(duration)

        # Extract donor response from transcript summary
        analysis = payload.get("analysis", {})
        summary = analysis.get("summary", "")
        if "yes" in summary.lower() or "accept" in summary.lower():
            outreach.call_status = "accepted"
            outreach.donor.status = "responding"
            outreach.donor.save()
            outreach.emergency_request.status = "donor_confirmed"
            outreach.emergency_request.save()
        elif "no" in summary.lower() or "decline" in summary.lower():
            outreach.call_status = "declined"
            outreach.donor.status = "available"
            outreach.donor.save()

        outreach.donor_response = summary

    outreach.save()
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_http_methods(["POST"])
def n8n_webhook(request):
    """
    POST /webhooks/n8n/ — receives workflow status callbacks from n8n.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event = payload.get("event")
    er_id = payload.get("request_id")

    if event and er_id:
        try:
            er = EmergencyRequest.objects.get(pk=er_id)
            if event == "workflow_completed":
                logger.info("n8n workflow completed for request %s", er_id)
            elif event == "escalate":
                er.urgency_level = "critical"
                er.save()
                logger.warning("Request %s escalated to critical by n8n", er_id)
        except EmergencyRequest.DoesNotExist:
            pass

    return JsonResponse({"status": "received"})
