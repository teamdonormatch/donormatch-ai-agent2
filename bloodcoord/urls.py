from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from donors.views import DonorListView, DonorDetailView
from emergency.views import (
    EmergencyRequestCreateView, EmergencyRequestDetailView,
    vapi_webhook, n8n_webhook,
)

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('admin/', admin.site.urls),
    path('api/donors/', DonorListView.as_view()),
    path('api/donors/<int:pk>/', DonorDetailView.as_view()),
    path('api/emergency/', EmergencyRequestCreateView.as_view()),
    path('api/emergency/<int:pk>/', EmergencyRequestDetailView.as_view()),
    path('webhooks/vapi/', vapi_webhook),
    path('webhooks/n8n/', n8n_webhook),
]
