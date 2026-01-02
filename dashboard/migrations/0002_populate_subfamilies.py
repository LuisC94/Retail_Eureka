from django.db import migrations

def populate_subfamilies(apps, schema_editor):
    ProductSubFamily = apps.get_model('dashboard', 'ProductSubFamily')
    
    subfamilies = [
        # Kiwis
        {'name': 'Hayward', 'fruit_type': 'Kiwi'},
        {'name': 'Green', 'fruit_type': 'Kiwi'},
        {'name': 'Gold', 'fruit_type': 'Kiwi'},
        {'name': 'Red', 'fruit_type': 'Kiwi'},
        # Apples
        {'name': 'Gala', 'fruit_type': 'Apple'},
        {'name': 'Fuji', 'fruit_type': 'Apple'},
        {'name': 'Golden Delicious', 'fruit_type': 'Apple'},
        {'name': 'Granny Smith', 'fruit_type': 'Apple'},
        {'name': 'Reineta', 'fruit_type': 'Apple'},
    ]
    
    for item in subfamilies:
        ProductSubFamily.objects.create(**item)

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_subfamilies),
    ]
