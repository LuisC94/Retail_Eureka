import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Retail_Eureka.settings')
django.setup()

from dashboard.models import PlantationEvent, User

def check_events():
    print(f"Total PlantationEvents: {PlantationEvent.objects.count()}")
    for event in PlantationEvent.objects.all():
        print(f"Event ID: {event.event_id}, Date: {event.event_date}, Type: {event.event_type}, Producer: {event.plantation.producer.username}")

if __name__ == "__main__":
    check_events()
