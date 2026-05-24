from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from donors.models import Donor


class DonorListView(APIView):
    def get(self, request):
        donors = Donor.objects.filter(is_active=True).values(
            "id", "first_name", "last_name", "blood_group",
            "city", "status", "total_donations", "response_rate"
        )
        return Response(list(donors))

    def post(self, request):
        d = request.data
        donor = Donor.objects.create(
            first_name=d["first_name"],
            last_name=d["last_name"],
            phone=d["phone"],
            email=d.get("email", ""),
            blood_group=d["blood_group"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            city=d["city"],
            total_donations=d.get("total_donations", 0),
            response_rate=d.get("response_rate", 0.8),
        )
        return Response({"id": donor.pk, "name": donor.full_name}, status=status.HTTP_201_CREATED)


class DonorDetailView(APIView):
    def get(self, request, pk):
        try:
            d = Donor.objects.get(pk=pk)
        except Donor.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response({
            "id": d.pk, "name": d.full_name, "blood_group": d.blood_group,
            "city": d.city, "status": d.status, "total_donations": d.total_donations,
            "response_rate": d.response_rate, "avg_response_time_hours": d.avg_response_time_hours,
        })

    def patch(self, request, pk):
        try:
            d = Donor.objects.get(pk=pk)
        except Donor.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        for field in ("status", "total_donations", "response_rate", "last_donation_date"):
            if field in request.data:
                setattr(d, field, request.data[field])
        d.save()
        return Response({"status": "updated"})
