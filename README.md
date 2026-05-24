# BloodCoord — AI-Powered Emergency Blood Donor Coordination

## Quick Start

```bash
# Install dependencies
pip install django djangorestframework

# Configure environment variables
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your_supabase_key
export VAPI_API_KEY=your_vapi_key
export VAPI_PHONE_NUMBER_ID=your_phone_number_id
export OPENAI_API_KEY=your_openai_key
export N8N_WEBHOOK_URL=http://localhost:5678/webhook

# Apply migrations
python manage.py migrate

# Seed test data (Lagos donors & hospitals)
python manage.py seed_data

# Create admin user
python manage.py createsuperuser

# Run server
python manage.py runserver
```

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/emergency/` | Submit emergency blood request |
| GET | `/api/emergency/<id>/` | Check request status |
| GET | `/api/donors/` | List all active donors |
| POST | `/api/donors/` | Register a new donor |
| PATCH | `/api/donors/<id>/` | Update donor status |
| POST | `/webhooks/vapi/` | VAPI call status callback |
| POST | `/webhooks/n8n/` | n8n workflow callback |

## Example: Submit Emergency Request

```bash
curl -X POST http://localhost:8000/api/emergency/ \
  -H "Content-Type: application/json" \
  -d '{
    "hospital_id": 1,
    "blood_group_needed": "O+",
    "units_needed": 2,
    "urgency_level": "critical",
    "patient_condition": "Trauma surgery — immediate transfusion required"
  }'
```

## Project Structure

```
bloodcoord/
├── donors/             # Donor registry, geo-services, AI ranking
│   ├── models.py       # Donor model
│   ├── services.py     # Haversine distance, compatibility, GPT ranking
│   ├── views.py        # Donor REST API
│   └── management/commands/seed_data.py
├── emergency/          # Emergency coordination engine
│   ├── models.py       # EmergencyRequest, Hospital, DonorOutreach
│   ├── coordinator.py  # Main pipeline orchestrator
│   ├── services.py     # VAPI, n8n, Supabase integrations
│   └── views.py        # Emergency API + VAPI/n8n webhooks
└── bloodcoord/         # Django project settings and URLs
```
