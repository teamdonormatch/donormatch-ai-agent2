from django.contrib import admin
from donors.models import Donor

@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'blood_group', 'city', 'status', 'total_donations', 'response_rate', 'is_active')
    list_filter = ('blood_group', 'status', 'is_active', 'city')
    search_fields = ('first_name', 'last_name', 'phone', 'email')
    list_editable = ('status', 'is_active')
