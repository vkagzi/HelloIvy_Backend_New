from rest_framework import serializers
from unidecode import unidecode

from .models import Location


class LocationSerializer(serializers.ModelSerializer):
    city_ascii = serializers.SerializerMethodField()
    state_ascii = serializers.SerializerMethodField()
    country_ascii = serializers.SerializerMethodField()
    
    class Meta:
        model = Location
        fields = ("id", "city", "state", "country", "city_ascii", "state_ascii", "country_ascii")
    
    def get_city_ascii(self, obj):
        return unidecode(obj.city)
    
    def get_state_ascii(self, obj):
        return unidecode(obj.state) if obj.state else None
    
    def get_country_ascii(self, obj):
        return unidecode(obj.country)
