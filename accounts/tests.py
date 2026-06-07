from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from rest_framework import status
from rest_framework.test import APITestCase

from .models import UserRole, SubscriptionStatus

User = get_user_model()

class CustomUserModelTests(APITestCase):
    """
    Tests for the custom User model creation and management.
    """
    def test_create_user_with_email_successful(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='Password123!',
            role=UserRole.PUBLIC_USER,
            phone_number='+1234567890'
        )
        self.assertEqual(user.email, 'user@example.com')
        self.assertTrue(user.check_password('Password123!'))
        self.assertEqual(user.role, UserRole.PUBLIC_USER)
        self.assertEqual(user.phone_number, '+1234567890')
        self.assertEqual(user.subscription_status, SubscriptionStatus.TRIAL)
        self.assertFalse(user.is_verified)
        self.assertIsNone(user.username)  # Username field should be removed/None

    def test_create_user_raises_value_error_if_no_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='Password123!')

    def test_create_superuser_defaults(self):
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!'
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)
        self.assertEqual(admin_user.role, UserRole.ADMIN)


class AuthAPIEndpointsTests(APITestCase):
    """
    Tests for DRF JWT authentication, registration, and password reset endpoints.
    """
    def setUp(self):
        # Create a default user for login and password reset tests
        self.user_password = 'SecurePassword123!'
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password=self.user_password,
            role=UserRole.AGENT,
            phone_number='+1987654321',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_verified=True
        )
        
        self.register_url = reverse('auth_register')
        self.login_url = reverse('auth_login')
        self.profile_url = reverse('user_profile')
        self.reset_request_url = reverse('password_reset_request')
        self.reset_confirm_url = reverse('password_reset_confirm')

    def test_register_user_successful(self):
        data = {
            'email': 'newuser@example.com',
            'password': 'ComplexPassword456!',
            'role': UserRole.PUBLIC_USER,
            'phone_number': '+15555555555'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response structure
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        
        # Verify user attributes
        user_data = response.data['user']
        self.assertEqual(user_data['email'], 'newuser@example.com')
        self.assertEqual(user_data['role'], UserRole.PUBLIC_USER)
        self.assertEqual(user_data['phone_number'], '+15555555555')
        self.assertEqual(user_data['subscription_status'], SubscriptionStatus.TRIAL)
        self.assertFalse(user_data['is_verified'])
        
        # Verify trial_end_date is set in future (around 7 days from now)
        created_user = User.objects.get(email='newuser@example.com')
        self.assertIsNotNone(created_user.trial_end_date)
        delta = created_user.trial_end_date - timezone.now()
        self.assertTrue(6 <= delta.days <= 8)

    def test_register_duplicate_email_fails(self):
        data = {
            'email': 'testuser@example.com', # already exists in setUp
            'password': 'SomePassword123!',
            'role': UserRole.PUBLIC_USER
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_login_successful_returns_jwt_and_profile(self):
        data = {
            'email': 'testuser@example.com',
            'password': self.user_password
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        
        # Verify user profile data
        user_data = response.data['user']
        self.assertEqual(user_data['email'], 'testuser@example.com')
        self.assertEqual(user_data['role'], UserRole.AGENT)
        self.assertTrue(user_data['is_verified'])
        self.assertEqual(user_data['subscription_status'], SubscriptionStatus.ACTIVE)

    def test_login_invalid_credentials_fails(self):
        data = {
            'email': 'testuser@example.com',
            'password': 'WrongPassword!'
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_profile_endpoint_authenticated(self):
        # Authenticate using client credentials
        login_data = {
            'email': 'testuser@example.com',
            'password': self.user_password
        }
        login_res = self.client.post(self.login_url, login_data, format='json')
        token = login_res.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'testuser@example.com')

    def test_access_profile_endpoint_unauthenticated_fails(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_flow_successful(self):
        # 1. Request Password Reset
        reset_request_data = {'email': 'testuser@example.com'}
        response = self.client.post(self.reset_request_url, reset_request_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['detail'],
            "If a matching account exists, a password reset email has been dispatched."
        )
        
        # Verify email was dispatched
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['testuser@example.com'])
        
        # 2. Extract Token and UID
        # Standard implementation of default_token_generator & urlsafe_base64_encode
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        
        # 3. Confirm Password Reset with valid token
        new_password = 'NewSuperSecurePassword999!'
        reset_confirm_data = {
            'uidb64': uidb64,
            'token': token,
            'new_password': new_password
        }
        response = self.client.post(self.reset_confirm_url, reset_confirm_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Password has been successfully updated.")
        
        # 4. Verify user can log in with new password
        login_data = {
            'email': 'testuser@example.com',
            'password': new_password
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)

    def test_password_reset_confirm_invalid_token_fails(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = 'invalid-token-12345'
        
        reset_confirm_data = {
            'uidb64': uidb64,
            'token': invalid_token,
            'new_password': 'NewPassword123!'
        }
        response = self.client.post(self.reset_confirm_url, reset_confirm_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', response.data)


import hmac
import hashlib
from django.conf import settings
import json

class PaystackWebhookTests(APITestCase):
    """
    Tests for Paystack Webhook authentication and payload processing.
    """
    def setUp(self):
        self.webhook_url = reverse('paystack_webhook')
        self.user = User.objects.create_user(
            email='subscriber@example.com',
            password='Password123!',
            role=UserRole.AGENT,
            subscription_status=SubscriptionStatus.TRIAL
        )

    def test_webhook_invalid_signature_blocks_request(self):
        data = {
            "event": "charge.success",
            "data": {
                "customer": {"email": "subscriber@example.com"}
            }
        }
        headers = {'HTTP_X_PAYSTACK_SIGNATURE': 'invalid_signature_value'}
        response = self.client.post(self.webhook_url, data, format='json', **headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify status is unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_status, SubscriptionStatus.TRIAL)

    def test_webhook_missing_signature_header_blocks_request(self):
        data = {"event": "charge.success"}
        response = self.client.post(self.webhook_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_webhook_successful_payment_event_updates_user_subscription(self):
        payload = {
            "event": "charge.success",
            "data": {
                "customer": {
                    "email": "subscriber@example.com"
                },
                "metadata": {
                    "user_email": "subscriber@example.com"
                }
            }
        }
        
        # Serialize payload to compute signature (matching how test client sends it)
        payload_bytes = json.dumps(payload).encode('utf-8')
        
        signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()
        
        # Send raw post request content to ensure signature matches payload bytes exactly
        response = self.client.post(
            self.webhook_url,
            data=payload_bytes,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user state is updated to active
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_status, SubscriptionStatus.ACTIVE)
        self.assertIsNotNone(self.user.subscription_end_date)
        
        # Verify subscription is set to end in around 30 days
        delta = self.user.subscription_end_date - timezone.now()
        self.assertTrue(29 <= delta.days <= 31)
