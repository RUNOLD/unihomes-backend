from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .models import Property, PropertyImage
from .serializers import PropertySerializer, PropertyImageSerializer
from .permissions import IsAgentOwnerOrReadOnly, HasActiveSubscriptionOrTrial

class PropertyViewSet(viewsets.ModelViewSet):
    """
    ViewSet to manage CRUD operations for Properties listings.
    GET requests are public. Write actions are restricted to agents/admins.
    Also supports URL query parameter filtering (location, property_type, status).
    """
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    permission_classes = [IsAgentOwnerOrReadOnly, HasActiveSubscriptionOrTrial]

    def get_queryset(self):
        queryset = Property.objects.prefetch_related('images').select_related('agent').all()
        
        # Apply query parameter filters
        location = self.request.query_params.get('location')
        property_type = self.request.query_params.get('property_type')
        status_param = self.request.query_params.get('status')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')

        if location:
            queryset = queryset.filter(location__icontains=location)
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
            
        return queryset


class IsPropertyImageOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission class ensuring only the property owner agent (or admin)
    can manage image resources.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role in ('AGENT', 'ADMIN')

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.role == 'ADMIN':
            return True
        return obj.property.agent == request.user


class PropertyImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet to manage property media uploads and attachment.
    Enforces listing ownership validation during post creation.
    """
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer
    permission_classes = [IsPropertyImageOwnerOrReadOnly]

    def perform_create(self, serializer):
        property_obj = serializer.validated_data['property']
        
        # Enforce that agents can only upload images to their own property listings
        if self.request.user.role != 'ADMIN' and property_obj.agent != self.request.user:
            raise PermissionDenied(
                "Access Denied: You do not own the property you are attempting to upload images to."
            )
        serializer.save()
