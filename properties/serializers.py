from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Property, PropertyImage, PropertyType, PropertyStatus

class PropertyImageSerializer(serializers.ModelSerializer):
    """
    Serializer to map individual media attachments to a listing.
    """
    class Meta:
        model = PropertyImage
        fields = ('id', 'property', 'image', 'uploaded_at')

class PropertySerializer(serializers.ModelSerializer):
    """
    Serializer to map property details, showing agent profiles,
    and a listing's image gallery in read representation.
    """
    images = PropertyImageSerializer(many=True, read_only=True)
    agent = UserSerializer(read_only=True)

    class Meta:
        model = Property
        fields = (
            'id',
            'title',
            'description',
            'price',
            'property_type',
            'location',
            'status',
            'agent',
            'images',
            'created_at',
            'updated_at'
        )
        read_only_fields = ('id', 'agent', 'created_at', 'updated_at')

    def create(self, validated_data):
        # Retrieve agent from request session context automatically
        request = self.context.get('request')
        if request and request.user:
            validated_data['agent'] = request.user
        return super().create(validated_data)
