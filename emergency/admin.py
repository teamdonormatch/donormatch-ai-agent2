from django.contrib import admin
from emergency.models import Hospital, EmergencyRequest, DonorOutreach

@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'contact_phone', 'is_active')
    search_fields = ('name', 'city')

class DonorOutreachInline(admin.TabularInline):
    model = DonorOutreach
    extra = 0
    readonly_fields = ('ai_rank_score', 'rank_position', 'distance_km', 'vapi_call_id', 'call_status')

@admin.register(EmergencyRequest)
class EmergencyRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'hospital', 'blood_group_needed', 'urgency_level', 'status', 'created_at')
    list_filter = ('status', 'urgency_level', 'blood_group_needed')
    inlines = [DonorOutreachInline]
    readonly_fields = ('n8n_execution_id', 'created_at', 'updated_at')

@admin.register(DonorOutreach)
class DonorOutreachAdmin(admin.ModelAdmin):
    list_display = ('donor', 'emergency_request', 'rank_position', 'ai_rank_score', 'distance_km', 'call_status')
    list_filter = ('call_status',)
