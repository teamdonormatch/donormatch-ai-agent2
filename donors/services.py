"""
Donor services: geolocation, compatibility, and AI-powered ranking.
"""
import math
import json
import logging
from datetime import date, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

# Blood group compatibility map: key can donate TO values
COMPATIBILITY = {
    'O-':  ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
    'O+':  ['O+', 'A+', 'B+', 'AB+'],
    'A-':  ['A-', 'A+', 'AB-', 'AB+'],
    'A+':  ['A+', 'AB+'],
    'B-':  ['B-', 'B+', 'AB-', 'AB+'],
    'B+':  ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'],
}


def get_compatible_blood_groups(needed: str) -> list[str]:
    """Return all blood groups that can donate to the needed group."""
    return [bg for bg, can_donate_to in COMPATIBILITY.items() if needed in can_donate_to]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two coordinates in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def days_since_last_donation(donor) -> int | None:
    if not donor.last_donation_date:
        return None
    return (date.today() - donor.last_donation_date).days


def compute_fatigue_score(donor) -> float:
    """Return 0.0 (fatigued) – 1.0 (fully rested). 56 days between donations is standard."""
    days = days_since_last_donation(donor)
    if days is None:
        return 1.0
    if days < 56:
        return round(days / 56, 3)
    return 1.0


def rank_donors_locally(candidates: list, hospital_lat: float, hospital_lon: float) -> list:
    """
    Simple local ranking when the AI service is unavailable.
    Returns list of (donor, score, distance_km) tuples sorted by score descending.
    """
    ranked = []
    for donor in candidates:
        dist = haversine_km(donor.latitude, donor.longitude, hospital_lat, hospital_lon)
        proximity_score = max(0, 1 - dist / 200)
        fatigue_score = compute_fatigue_score(donor)
        response_score = donor.response_rate
        history_score = min(donor.total_donations / 10, 1.0)
        speed_score = max(0, 1 - donor.avg_response_time_hours / 48)

        score = (
            proximity_score * 0.30 +
            response_score  * 0.25 +
            fatigue_score   * 0.20 +
            history_score   * 0.15 +
            speed_score     * 0.10
        )
        ranked.append((donor, round(score, 4), round(dist, 2)))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def rank_donors_with_ai(candidates: list, hospital_lat: float, hospital_lon: float,
                         blood_group: str, urgency: str) -> list:
    """
    Use OpenAI GPT to rank donors intelligently.
    Falls back to local ranking if the API call fails.
    """
    try:
        import urllib.request

        donor_data = []
        for d in candidates:
            dist = haversine_km(d.latitude, d.longitude, hospital_lat, hospital_lon)
            donor_data.append({
                "id": d.pk,
                "blood_group": d.blood_group,
                "distance_km": round(dist, 2),
                "total_donations": d.total_donations,
                "response_rate": d.response_rate,
                "fatigue_score": compute_fatigue_score(d),
                "avg_response_time_hours": d.avg_response_time_hours,
                "days_since_last_donation": days_since_last_donation(d),
            })

        system_prompt = (
            "You are an AI engine for an emergency blood donor coordination system. "
            "Rank donors by suitability for an urgent blood request. "
            "Consider: proximity (30%), response probability (25%), fatigue (20%), "
            "donation history (15%), response speed (10%). "
            "Return ONLY valid JSON: {\"rankings\": [{\"donor_id\": <int>, \"score\": <float 0-1>, "
            "\"rationale\": \"<brief reason>\"}]} sorted by score descending."
        )
        user_prompt = (
            f"Emergency blood request details:\n"
            f"- Blood group needed: {blood_group}\n"
            f"- Urgency: {urgency}\n"
            f"- Available donors: {json.dumps(donor_data)}\n\n"
            f"Rank these donors and return the JSON rankings."
        )

        payload = json.dumps({
            "model": "gpt-4o-mini",
            "max_tokens": 1000,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        content = result["choices"][0]["message"]["content"]
        clean = content.strip().lstrip("```json").rstrip("```").strip()
        ai_rankings = json.loads(clean)["rankings"]

        donor_map = {d.pk: d for d in candidates}
        ranked = []
        for item in ai_rankings:
            donor = donor_map.get(item["donor_id"])
            if donor:
                dist = haversine_km(donor.latitude, donor.longitude, hospital_lat, hospital_lon)
                ranked.append((donor, item["score"], round(dist, 2), item.get("rationale", "")))
        return ranked

    except Exception as exc:
        logger.warning("AI ranking unavailable (%s), using local fallback.", exc)
        local = rank_donors_locally(candidates, hospital_lat, hospital_lon)
        return [(d, s, dist, "Local fallback ranking") for d, s, dist in local]
