from django.contrib import admin
from .models import Property, PropertyImage

class PropertyImageInline(admin.TabularInline):
    """
    Inline model admin to allow managing media images directly
    inside the Property details edit page.
    """
    model = PropertyImage
    extra = 1

class PropertyAdmin(admin.ModelAdmin):
    """
    ModelAdmin configuration to handle search indexing, filters,
    and metadata listing display for properties.
    """
    list_display = ('title', 'property_type', 'price', 'location', 'status', 'agent', 'created_at')
    list_filter = ('property_type', 'status', 'created_at', 'location')
    search_fields = ('title', 'description', 'location', 'agent__email', 'agent__phone_number')
    inlines = [PropertyImageInline]
    raw_id_fields = ('agent',) # Use lookup field instead of loading all agents dropdown for performance

admin.site.register(Property, PropertyAdmin)
admin.site.register(PropertyImage)
