from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    CustomTokenObtainPairSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

class RegisterView(generics.GenericAPIView):
    """
    Endpoint for new user registration.
    Returns both the user profile details and the JWT access/refresh tokens.
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Issue JWT tokens immediately upon successful registration
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user, context=self.get_serializer_context()).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Enriched simplejwt TokenObtainPairView that returns both JWT tokens
    and basic user details in the authentication response payload.
    """
    serializer_class = CustomTokenObtainPairSerializer

class PasswordResetRequestView(generics.GenericAPIView):
    """
    Triggers a secure password reset request.
    Generates tokens and notifies user via console-logged email backend.
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Silent response to mitigate user enumeration vectors
        return Response({
            "detail": "If a matching account exists, a password reset email has been dispatched."
        }, status=status.HTTP_200_OK)

class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Confirm password reset view. Takes cryptographically signed uid,
    token, and new password. Validates and executes password update.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "detail": "Password has been successfully updated."
        }, status=status.HTTP_200_OK)

class UserProfileView(generics.RetrieveAPIView):
    """
    Secured endpoint allowing authenticated clients to fetch their User info profile.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


import hmac
import hashlib
from django.conf import settings
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import SubscriptionStatus

User = get_user_model()

class PaystackWebhookView(APIView):
    """
    Webhook receiver for Paystack payments.
    Verifies event signatures and sets user subscription to active for 30 days.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        paystack_signature = request.headers.get('x-paystack-signature')
        if not paystack_signature:
            return Response({"detail": "Missing signature header."}, status=status.HTTP_401_UNAUTHORIZED)

        secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', None)
        if not secret_key:
            return Response({"detail": "Webhook key not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        computed_signature = hmac.new(
            secret_key.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, paystack_signature):
            return Response({"detail": "Invalid verification signature."}, status=status.HTTP_400_BAD_REQUEST)

        event_data = request.data
        event_type = event_data.get('event')

        if event_type == 'charge.success':
            data = event_data.get('data', {})
            metadata = data.get('metadata', {})
            
            # Lookup user by custom metadata or fallback to customer email
            email = metadata.get('user_email') or data.get('customer', {}).get('email')
            
            if email:
                try:
                    user = User.objects.get(email=email)
                    user.subscription_status = SubscriptionStatus.ACTIVE
                    user.subscription_end_date = timezone.now() + timezone.timedelta(days=30)
                    user.save()
                    return Response({"detail": "Subscription successfully provisioned."}, status=status.HTTP_200_OK)
                except User.DoesNotExist:
                    return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({"detail": "No email identified in payment details."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": f"Event type '{event_type}' received but not processed."}, status=status.HTTP_200_OK)
