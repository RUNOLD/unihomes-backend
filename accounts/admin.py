from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

class CustomUserAdmin(UserAdmin):
    """
    Define custom UserAdmin class to customize display, search,
    and fieldsets of our custom User model in Django Admin.
    """
    model = User
    list_display = ('email', 'role', 'subscription_status', 'is_verified', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('role', 'subscription_status', 'is_verified', 'is_staff', 'is_superuser', 'is_active')
    
    # Configure edit form fieldsets
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Application Specific'), {
            'fields': ('role', 'is_verified', 'subscription_status', 'trial_end_date'),
        }),
    )
    
    # Configure add form fieldsets (used when creating a user via admin)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 
                'password', 
                'role', 
                'phone_number', 
                'is_verified', 
                'subscription_status', 
                'trial_end_date',
                'is_staff',
                'is_superuser',
                'is_active'
            ),
        }),
    )
    
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)

admin.site.register(User, CustomUserAdmin)
