from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class PropertyType(models.TextChoices):
    SELF_CONTAIN = 'SELF_CONTAIN', _('Self-Contain')
    FLAT = 'FLAT', _('Flat')
    SHARED = 'SHARED', _('Shared')
    HOUSE = 'HOUSE', _('House')
    APARTMENT = 'APARTMENT', _('Apartment')

class PropertyStatus(models.TextChoices):
    AVAILABLE = 'AVAILABLE', _('Available')
    RENTED = 'RENTED', _('Rented')

class Property(models.Model):
    """
    Property listing model.
    Contains listing detail info, location, status, and agent ownership.
    """
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    property_type = models.CharField(
        max_length=30,
        choices=PropertyType.choices,
        default=PropertyType.FLAT
    )
    location = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=PropertyStatus.choices,
        default=PropertyStatus.AVAILABLE
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Property")
        verbose_name_plural = _("Properties")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.location}) - {self.price}"

def property_image_upload_path(instance, filename):
    """
    Helper to structure property image uploads in folders segregated by listing ID.
    """
    return f"properties/{instance.property.id}/{filename}"

class PropertyImage(models.Model):
    """
    Media images associated with a single property listing.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to=property_image_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Property Image")
        verbose_name_plural = _("Property Images")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Image #{self.id} for property: {self.property.title}"
