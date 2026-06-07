from django.utils import timezone
from rest_framework import permissions

class IsAgentOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to enforce:
    - Safe methods (GET, HEAD, OPTIONS) are allowed for anyone.
    - Write actions (POST) are limited to users with role AGENT or ADMIN.
    - Modification/Deletion (PUT, PATCH, DELETE) are limited to the owner agent or an ADMIN.
    """

    def has_permission(self, request, view):
        # Read-only operations are open to any client
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Write operations require authentication and AGENT/ADMIN role
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ('AGENT', 'ADMIN')
        )

    def has_object_permission(self, request, view, obj):
        # Read operations allowed on individual listing objects
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write operations are only allowed for ADMINs or the specific agent who owns the listing
        if request.user.role == 'ADMIN':
            return True

        return obj.agent == request.user


class HasActiveSubscriptionOrTrial(permissions.BasePermission):
    """
    Custom permission class verifying if an Agent's trial has expired or
    if they have an active paid subscription before allowing listing creations.
    """
    message = "Subscription required to list properties."

    def has_permission(self, request, view):
        # Only enforce subscription validation checks on listing creation attempts (POST)
        if request.method != 'POST':
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Admins are exempt from listing subscription limits
        if user.role == 'ADMIN':
            return True

        if user.role == 'AGENT':
            now = timezone.now()

            # 1. Validate active subscription term
            if user.subscription_status == 'active':
                if user.subscription_end_date and now <= user.subscription_end_date:
                    return True
                # Automatically transition status to expired
                user.subscription_status = 'expired'
                user.save(update_fields=['subscription_status'])

            # 2. Validate trial boundary term
            elif user.subscription_status == 'trial':
                if user.trial_end_date and now <= user.trial_end_date:
                    return True
                # Automatically transition status to expired
                user.subscription_status = 'expired'
                user.save(update_fields=['subscription_status'])

        return False

