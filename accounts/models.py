from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', _('Admin')
    AGENT = 'AGENT', _('Agent')
    PUBLIC_USER = 'PUBLIC_USER', _('Public User')

class SubscriptionStatus(models.TextChoices):
    TRIAL = 'trial', _('Trial')
    ACTIVE = 'active', _('Active')
    EXPIRED = 'expired', _('Expired')

class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', UserRole.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """
    Custom User Model implementing roles (ADMIN, AGENT, PUBLIC_USER),
    subscription tracking, verification state, and email-based authentication.
    """
    username = None
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.PUBLIC_USER
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    subscription_status = models.CharField(
        max_length=15,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL
    )
    trial_end_date = models.DateTimeField(blank=True, null=True)
    subscription_end_date = models.DateTimeField(blank=True, null=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.role})"
