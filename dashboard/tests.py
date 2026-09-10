from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from datetime import date
from decimal import Decimal
from .models import PlantationPlan, ProductSubFamily, PlantationCrop, Harvest

class ProducerDeletePlantationTests(TestCase):
    def setUp(self):
        self.producer_group = Group.objects.create(name='Producer')
        self.retailer_group = Group.objects.create(name='Retailer')

        # Owner producer
        self.producer1 = User.objects.create_user(username='prod1', password='password123')
        self.producer1.groups.add(self.producer_group)

        # Other producer
        self.producer2 = User.objects.create_user(username='prod2', password='password123')
        self.producer2.groups.add(self.producer_group)

        # Non-producer user
        self.retailer = User.objects.create_user(username='ret1', password='password123')
        self.retailer.groups.add(self.retailer_group)

        # Subfamily for crop
        self.subfamily = ProductSubFamily.objects.create(name='Gala Apple', fruit_type='Apple')

        # Create plantation belonging to producer1
        self.plantation = PlantationPlan.objects.create(
            producer=self.producer1,
            plantation_name='Test Orchard 1',
            quantity_of_trees=50,
            production_type='conventional',
            chemical_use='No',
            area=Decimal('1000.00'),
            location='Braga',
            plantation_date=date(2025, 5, 10)
        )

        # Add associated crop
        self.crop = PlantationCrop.objects.create(
            plantation=self.plantation,
            subfamily=self.subfamily,
            avg_plant_age_years=3
        )

        self.client = Client()

    def test_owner_can_delete_plantation(self):
        self.client.login(username='prod1', password='password123')
        url = reverse('producer_delete_plantation')
        response = self.client.post(url, {'plantation_id': self.plantation.plantation_id})

        self.assertRedirects(response, reverse('producer_dashboard'))
        self.assertFalse(PlantationPlan.objects.filter(pk=self.plantation.plantation_id).exists())
        # Associated crop should be cascade-deleted
        self.assertFalse(PlantationCrop.objects.filter(pk=self.crop.pk).exists())

    def test_cannot_delete_other_producers_plantation(self):
        self.client.login(username='prod2', password='password123')
        url = reverse('producer_delete_plantation')
        response = self.client.post(url, {'plantation_id': self.plantation.plantation_id})

        self.assertRedirects(response, reverse('producer_dashboard'))
        # Plantation must still exist
        self.assertTrue(PlantationPlan.objects.filter(pk=self.plantation.plantation_id).exists())

    def test_harvest_survives_with_null_plantation(self):
        # Create a harvest linked to the plantation
        harvest = Harvest.objects.create(
            producer=self.producer1,
            plantation=self.plantation,
            subfamily=self.subfamily,
            harvest_date=date(2025, 9, 1),
            harvest_quantity_kg=Decimal('500.00'),
            utilized_quantity_kg=Decimal('0.00'),
            avg_quality_score=8
        )

        self.client.login(username='prod1', password='password123')
        url = reverse('producer_delete_plantation')
        response = self.client.post(url, {'plantation_id': self.plantation.plantation_id})

        self.assertRedirects(response, reverse('producer_dashboard'))
        self.assertFalse(PlantationPlan.objects.filter(pk=self.plantation.plantation_id).exists())

        # Harvest must still exist with plantation set to None
        harvest.refresh_from_db()
        self.assertIsNone(harvest.plantation)
        self.assertEqual(harvest.harvest_quantity_kg, Decimal('500.00'))

    def test_non_producer_blocked(self):
        self.client.login(username='ret1', password='password123')
        url = reverse('producer_delete_plantation')
        response = self.client.post(url, {'plantation_id': self.plantation.plantation_id})

        # role_required redirects to login_url '/'
        self.assertRedirects(response, '/?next=' + url)
        self.assertTrue(PlantationPlan.objects.filter(pk=self.plantation.plantation_id).exists())

    def test_unauthenticated_user_blocked(self):
        url = reverse('producer_delete_plantation')
        response = self.client.post(url, {'plantation_id': self.plantation.plantation_id})

        # login_required redirects to login URL
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlantationPlan.objects.filter(pk=self.plantation.plantation_id).exists())
