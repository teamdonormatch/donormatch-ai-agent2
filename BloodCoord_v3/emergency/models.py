from django.db import models
from donors.models import Donor


class Hospital(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField()
    city = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class EmergencyRequest(models.Model):
    URGENCY_LEVELS = [
        ('critical', 'Critical'),
        ('urgent', 'Urgent'),
        ('standard', 'Standard'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('donors_contacted', 'Donors Contacted'),
        ('donor_confirmed', 'Donor Confirmed'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='requests')
    blood_group_needed = models.CharField(max_length=5, choices=Donor.BLOOD_GROUPS)
    units_needed = models.IntegerField(default=1)
    urgency_level = models.CharField(max_length=10, choices=URGENCY_LEVELS, default='urgent')
    patient_condition = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    n8n_execution_id = models.CharField(max_length=200, blank=True)
    donors_contacted = models.ManyToManyField(Donor, through='DonorOutreach', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Request #{self.pk} — {self.blood_group_needed} @ {self.hospital.name}"

    class Meta:
        ordering = ['-created_at']


class DonorOutreach(models.Model):
    CALL_STATUS = [
        ('queued', 'Queued'),
        ('initiated', 'Initiated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('no_answer', 'No Answer'),
        ('declined', 'Declined'),
        ('accepted', 'Accepted'),
        ('failed', 'Failed'),
    ]

    emergency_request = models.ForeignKey(EmergencyRequest, on_delete=models.CASCADE, related_name='outreaches')
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name='outreaches')
    ai_rank_score = models.FloatField(default=0.0)
    rank_position = models.IntegerField(default=0)
    distance_km = models.FloatField(default=0.0)
    vapi_call_id = models.CharField(max_length=200, blank=True)
    call_status = models.CharField(max_length=20, choices=CALL_STATUS, default='queued')
    call_duration_seconds = models.IntegerField(null=True, blank=True)
    donor_response = models.TextField(blank=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    ai_ranking_rationale = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outreach to {self.donor} for Request #{self.emergency_request.pk}"

    class Meta:
        ordering = ['rank_position']
