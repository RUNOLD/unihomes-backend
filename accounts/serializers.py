from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserRole, SubscriptionStatus

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer to represent a User profile in standard responses.
    """
    class Meta:
        model = User
        fields = (
            'id', 
            'email', 
            'role', 
            'phone_number', 
            'is_verified', 
            'subscription_status', 
            'trial_end_date', 
            'subscription_end_date',
            'date_joined'
        )
        read_only_fields = ('id', 'is_verified', 'subscription_status', 'trial_end_date', 'subscription_end_date', 'date_joined')

class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer to handle registration of new users.
    Enforces password complexity checks, handles role provisioning,
    and initializes trial subscriptions.
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.PUBLIC_USER)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'role', 'phone_number')
        extra_kwargs = {
            'phone_number': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("A user with this email already exists."))
        return value

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        role = validated_data.get('role', UserRole.PUBLIC_USER)
        phone_number = validated_data.get('phone_number', '')
        
        # Enforce subscription setup (7 days trial by default)
        trial_end_date = timezone.now() + timezone.timedelta(days=7)
        
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
            phone_number=phone_number,
            subscription_status=SubscriptionStatus.TRIAL,
            trial_end_date=trial_end_date
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes simplejwt TokenObtainPairSerializer to inject user details
    in the auth payload returned back to the user on login.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims to JWT token payload
        token['role'] = user.role
        token['subscription_status'] = user.subscription_status
        token['is_verified'] = user.is_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include serialized User object in final response
        data['user'] = UserSerializer(self.user).data
        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Validates user email for password reset and dispatches reset token link.
    """
    email = serializers.EmailField(required=True)

    def save(self):
        email = self.validated_data['email']
        try:
            user = User.objects.get(email=email)
            # Create cryptographic token and base64 encoded user id
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            # Construct reset URL link
            reset_url = f"http://localhost:8000/api/auth/password-reset/confirm/?uid={uid}&token={token}"
            
            subject = "Password Reset Request"
            message = (
                f"Hello,\n\n"
                f"You requested a password reset for your APMS UniHomes account.\n"
                f"Please use the details below to complete your password reset:\n\n"
                f"UID: {uid}\n"
                f"Token: {token}\n\n"
                f"Or visit the URL link below to reset:\n"
                f"{reset_url}\n\n"
                f"If you did not make this request, you can safely ignore this email."
            )
            
            # Send the email. Dev environment logs this in terminal console.
            send_mail(
                subject,
                message,
                'noreply@apmsunihomes.com',
                [user.email],
                fail_silently=False,
            )
            
            # Cache the token & uid locally in context for testing assertions
            self.context['uid'] = uid
            self.context['token'] = token
        except User.DoesNotExist:
            # Silent fallback to mitigate user enumeration attacks (best security practice)
            pass

class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Decodes the cryptographically signed uid and token and resets password if validated.
    """
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )

    def validate(self, attrs):
        uidb64 = attrs.get('uidb64')
        token = attrs.get('token')
        
        try:
            # Decode user primary key from base64
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": _("Invalid user identifier.")})
            
        # Verify token validity against the user instance
        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError({"token": _("Invalid or expired password reset token.")})
            
        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save()
        return user
