from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, PropertyImageViewSet

router = DefaultRouter()
router.register('properties', PropertyViewSet, basename='property')
router.register('properties-images', PropertyImageViewSet, basename='property-image')

urlpatterns = [
    path('', include(router.urls)),
]
