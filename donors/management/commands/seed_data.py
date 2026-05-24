from django.core.management.base import BaseCommand
from donors.models import Donor
from emergency.models import Hospital
from datetime import date, timedelta
import random

SEED_DONORS = [
    ("Amara", "Okafor", "+2348011111111", "O+", 6.5244, 3.3792, "Lagos Island"),
    ("Chukwuemeka", "Adeyemi", "+2348022222222", "A+", 6.4698, 3.5852, "Victoria Island"),
    ("Ngozi", "Eze", "+2348033333333", "B+", 6.6018, 3.3515, "Ikeja"),
    ("Segun", "Bello", "+2348044444444", "O-", 6.4550, 3.3841, "Surulere"),
    ("Fatima", "Abdullahi", "+2348055555555", "AB+", 6.5790, 3.3470, "Maryland"),
    ("Tunde", "Akinwale", "+2348066666666", "A-", 6.4281, 3.4219, "Lekki"),
    ("Chidinma", "Nwosu", "+2348077777777", "B-", 6.5952, 3.3351, "Ojodu"),
    ("Emeka", "Obi", "+2348088888888", "O+", 6.4351, 3.4714, "Ajah"),
]

SEED_HOSPITALS = [
    ("Lagos University Teaching Hospital", "Idi-Araba, Surulere", "Lagos", 6.5040, 3.3634, "+2341234567890"),
    ("Lagos Island General Hospital", "Lagos Island", "Lagos", 6.4550, 3.3950, "+2341234567891"),
    ("Reddington Hospital", "Victoria Island", "Lagos", 6.4328, 3.4176, "+2341234567892"),
]

class Command(BaseCommand):
    help = "Seed the database with test donors and hospitals"

    def handle(self, *args, **options):
        for name, address, city, lat, lon, phone in SEED_HOSPITALS:
            Hospital.objects.get_or_create(name=name, defaults=dict(
                address=address, city=city, latitude=lat, longitude=lon, contact_phone=phone))
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(SEED_HOSPITALS)} hospitals"))

        created = 0
        for first, last, phone, bg, lat, lon, city in SEED_DONORS:
            if not Donor.objects.filter(phone=phone).exists():
                Donor.objects.create(
                    first_name=first, last_name=last, phone=phone,
                    blood_group=bg, latitude=lat, longitude=lon, city=city,
                    total_donations=random.randint(0, 15),
                    response_rate=round(random.uniform(0.6, 1.0), 2),
                    avg_response_time_hours=round(random.uniform(1, 36), 1),
                    last_donation_date=date.today() - timedelta(days=random.randint(60, 365)),
                )
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} donors"))
