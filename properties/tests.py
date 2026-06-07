from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserRole, SubscriptionStatus
from .models import Property, PropertyImage, PropertyType, PropertyStatus

User = get_user_model()

class PropertyAPITests(APITestCase):
    """
    Tests for the Property & PropertyImage API endpoints, enforcing
    role-based access controls and listing ownership checks.
    """
    def setUp(self):
        # Create user accounts with different roles
        self.agent_1 = User.objects.create_user(
            email='agent1@example.com',
            password='AgentPassword123!',
            role=UserRole.AGENT,
            trial_end_date=timezone.now() + timezone.timedelta(days=7)
        )
        self.agent_2 = User.objects.create_user(
            email='agent2@example.com',
            password='AgentPassword123!',
            role=UserRole.AGENT,
            trial_end_date=timezone.now() + timezone.timedelta(days=7)
        )
        self.public_user = User.objects.create_user(
            email='public@example.com',
            password='UserPassword123!',
            role=UserRole.PUBLIC_USER
        )
        
        # Create a listing owned by agent_1
        self.property = Property.objects.create(
            title='Cosy Flat in City Center',
            description='A beautiful 2-bedroom flat.',
            price=1200.00,
            property_type=PropertyType.FLAT,
            location='London',
            status=PropertyStatus.AVAILABLE,
            agent=self.agent_1
        )
        
        self.list_url = reverse('property-list')
        self.detail_url = reverse('property-detail', kwargs={'pk': self.property.pk})
        self.image_list_url = reverse('property-image-list')

    def test_get_properties_list_anonymous_success(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Cosy Flat in City Center')

    def test_get_property_detail_anonymous_success(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Cosy Flat in City Center')

    def test_create_property_by_agent_success(self):
        # Authenticate as agent_1
        self.client.force_authenticate(user=self.agent_1)
        
        data = {
            'title': 'Spacious Studio Apartment',
            'description': 'All bills included.',
            'price': 850.00,
            'property_type': PropertyType.SELF_CONTAIN,
            'location': 'Manchester',
            'status': PropertyStatus.AVAILABLE
        }
        
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Spacious Studio Apartment')
        
        # Verify that agent was automatically assigned to request user (agent_1)
        self.assertEqual(response.data['agent']['email'], 'agent1@example.com')

    def test_create_property_by_public_user_forbidden(self):
        # Authenticate as public user
        self.client.force_authenticate(user=self.public_user)
        
        data = {
            'title': 'Nice Room',
            'description': 'Shared toilet.',
            'price': 400.00,
            'property_type': PropertyType.SHARED,
            'location': 'Bristol'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_property_anonymous_unauthorized(self):
        data = {
            'title': 'Nice Room',
            'description': 'Shared toilet.',
            'price': 400.00,
            'property_type': PropertyType.SHARED,
            'location': 'Bristol'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_modify_property_by_owner_agent_success(self):
        self.client.force_authenticate(user=self.agent_1)
        
        data = {
            'title': 'Updated Cosy Flat in City Center',
            'price': 1300.00
        }
        response = self.client.patch(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Cosy Flat in City Center')
        self.assertEqual(float(response.data['price']), 1300.00)

    def test_modify_property_by_non_owner_agent_forbidden(self):
        self.client.force_authenticate(user=self.agent_2)
        
        data = {
            'title': 'Hijacked Title'
        }
        response = self.client.patch(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_property_by_owner_agent_success(self):
        self.client.force_authenticate(user=self.agent_1)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Property.objects.filter(pk=self.property.pk).exists())

    def test_delete_property_by_non_owner_agent_forbidden(self):
        self.client.force_authenticate(user=self.agent_2)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Property.objects.filter(pk=self.property.pk).exists())

    def test_upload_image_to_own_property_success(self):
        self.client.force_authenticate(user=self.agent_1)
        
        # Mock simple file upload
        file = SimpleUploadedFile(
            name='room.jpg',
            content=b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/jpeg'
        )
        
        data = {
            'property': self.property.pk,
            'image': file
        }
        
        response = self.client.post(self.image_list_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PropertyImage.objects.filter(property=self.property).count(), 1)

    def test_upload_image_to_other_agent_property_forbidden(self):
        # Authenticate as agent_2 (not the owner of self.property)
        self.client.force_authenticate(user=self.agent_2)
        
        file = SimpleUploadedFile(
            name='hacked.jpg',
            content=b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/jpeg'
        )
        
        data = {
            'property': self.property.pk,
            'image': file
        }
        
        response = self.client.post(self.image_list_url, data, format='multipart')
        # View validation should raise PermissionDenied -> 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(PropertyImage.objects.filter(property=self.property).count(), 0)

    def test_create_property_with_active_trial_succeeds(self):
        agent_trial = User.objects.create_user(
            email='agent_trial@example.com',
            password='Password123!',
            role=UserRole.AGENT,
            subscription_status=SubscriptionStatus.TRIAL,
            trial_end_date=timezone.now() + timezone.timedelta(days=5)
        )
        self.client.force_authenticate(user=agent_trial)
        
        data = {
            'title': 'Active Trial Listing',
            'description': 'Description',
            'price': 1000.00,
            'property_type': PropertyType.FLAT,
            'location': 'Leeds'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_property_with_expired_trial_fails(self):
        agent_expired_trial = User.objects.create_user(
            email='agent_expired_trial@example.com',
            password='Password123!',
            role=UserRole.AGENT,
            subscription_status=SubscriptionStatus.TRIAL,
            trial_end_date=timezone.now() - timezone.timedelta(days=1)
        )
        self.client.force_authenticate(user=agent_expired_trial)
        
        data = {
            'title': 'Expired Trial Listing',
            'description': 'Description',
            'price': 1000.00,
            'property_type': PropertyType.FLAT,
            'location': 'Leeds'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'Subscription required to list properties.')
        
        # Check status auto-transition
        agent_expired_trial.refresh_from_db()
        self.assertEqual(agent_expired_trial.subscription_status, SubscriptionStatus.EXPIRED)

    def test_create_property_with_active_subscription_succeeds(self):
        agent_active = User.objects.create_user(
            email='agent_active@example.com',
            password='Password123!',
            role=UserRole.AGENT,
            subscription_status=SubscriptionStatus.ACTIVE,
            subscription_end_date=timezone.now() + timezone.timedelta(days=20)
        )
        self.client.force_authenticate(user=agent_active)
        
        data = {
            'title': 'Paid Listing',
            'description': 'Description',
            'price': 1500.00,
            'property_type': PropertyType.FLAT,
            'location': 'Leeds'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_property_with_expired_subscription_fails(self):
        agent_expired = User.objects.create_user(
            email='agent_expired@example.com',
            password='Password123!',
            role=UserRole.AGENT,
            subscription_status=SubscriptionStatus.ACTIVE,
            subscription_end_date=timezone.now() - timezone.timedelta(days=1)
        )
        self.client.force_authenticate(user=agent_expired)
        
        data = {
            'title': 'Expired Listing',
            'description': 'Description',
            'price': 1500.00,
            'property_type': PropertyType.FLAT,
            'location': 'Leeds'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'Subscription required to list properties.')
        
        # Check status auto-transition
        agent_expired.refresh_from_db()
        self.assertEqual(agent_expired.subscription_status, SubscriptionStatus.EXPIRED)
