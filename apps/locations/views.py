from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Q
from unidecode import unidecode

from .models import Location
from .serializers import LocationSerializer


class LocationListView(generics.ListAPIView):
    """List locations. Supports filtering by `country`, `state`, and `q` for city search."""

    serializer_class = LocationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        qs = Location.objects.all()
        country = self.request.query_params.get("country")
        state = self.request.query_params.get("state")
        q = self.request.query_params.get("q")
        
        if country:
            qs = qs.filter(country__icontains=country)
        if state:
            qs = qs.filter(state__icontains=state)
        if q:
            qs = qs.filter(city__icontains=q)
        
        return qs[:100]  # Limit to 100 results


@api_view(["GET"])
@permission_classes([AllowAny])
def countries(request):
    q = request.query_params.get("q", "")
    limit = int(request.query_params.get("limit", 100))
    
    if q and len(q) >= 2:
        # Normalize query to ASCII for matching
        q_ascii = unidecode(q).lower()
        # Get all countries and filter by ASCII version
        all_countries = Location.objects.values_list("country", flat=True).distinct()
        matching = [c for c in all_countries if q_ascii in unidecode(c).lower()]
        countries_ascii = sorted(set(unidecode(c) for c in matching))[:limit]
    else:
        # Return all countries converted to ASCII
        countries_list = Location.objects.values_list("country", flat=True).distinct().order_by("country")[:limit]
        countries_ascii = sorted(set(unidecode(c) for c in countries_list))
    
    return Response(countries_ascii)


@api_view(["GET"])
@permission_classes([AllowAny])
def states(request):
    country = request.query_params.get("country")
    q = request.query_params.get("q", "")
    full = request.query_params.get("full", "").lower() == "true"
    limit = int(request.query_params.get("limit", 100))
    
    qs = Location.objects.all()
    
    # Filter by country if provided
    if country:
        country_ascii = unidecode(country).lower()
        all_locations = qs.all()
        qs = Location.objects.filter(
            id__in=[loc.id for loc in all_locations if unidecode(loc.country).lower() == country_ascii]
        )
    
    if q and len(q) >= 2:
        # Normalize query to ASCII for matching
        q_ascii = unidecode(q).lower()
        all_locations = qs.all()
        matching_ids = [loc.id for loc in all_locations if loc.state and q_ascii in unidecode(loc.state).lower()]
        qs = Location.objects.filter(id__in=matching_ids)
    
    # If full=true, return state objects with country
    if full:
        locations = qs.filter(state__isnull=False).distinct()
        result = []
        seen = set()
        for loc in locations:
            state_ascii = unidecode(loc.state) if loc.state else None
            # Deduplicate by ASCII state name
            if state_ascii and state_ascii not in seen:
                seen.add(state_ascii)
                result.append({
                    "state": state_ascii,
                    "country": unidecode(loc.country)
                })
        return Response(sorted(result, key=lambda x: x["state"])[:limit])
    
    # Otherwise return just state names
    all_states = qs.values_list("state", flat=True).distinct()
    states_ascii = sorted(set(unidecode(s) for s in all_states if s))[:limit]
    return Response(states_ascii)


@api_view(["GET"])
@permission_classes([AllowAny])
def cities(request):
    country = request.query_params.get("country")
    state = request.query_params.get("state")
    q = request.query_params.get("q", "")
    limit = int(request.query_params.get("limit", 50))
    
    qs = Location.objects.all()
    
    # Filter by country if provided
    if country:
        country_ascii = unidecode(country).lower()
        all_locations = qs.all()
        qs = Location.objects.filter(
            id__in=[loc.id for loc in all_locations if unidecode(loc.country).lower() == country_ascii]
        )
    
    # Filter by state if provided
    if state:
        state_ascii = unidecode(state).lower()
        all_locations = qs.all()
        qs = Location.objects.filter(
            id__in=[loc.id for loc in all_locations if loc.state and unidecode(loc.state).lower() == state_ascii]
        )
    
    if q and len(q) >= 2:
        # Normalize query to ASCII for matching
        q_ascii = unidecode(q).lower()
        all_locations = qs.all()
        matching_ids = [loc.id for loc in all_locations if q_ascii in unidecode(loc.city).lower()]
        qs = Location.objects.filter(id__in=matching_ids)
    
    # Return formatted "City, State, Country" strings
    locations = qs[:limit]
    formatted_cities = []
    seen = set()
    
    for loc in locations:
        city_ascii = unidecode(loc.city)
        state_ascii = unidecode(loc.state) if loc.state else None
        country_ascii = unidecode(loc.country)
        
        # Format: "City, State, Country" or "City, Country" if no state
        if state_ascii:
            formatted = f"{city_ascii}, {state_ascii}, {country_ascii}"
        else:
            formatted = f"{city_ascii}, {country_ascii}"
        
        # Deduplicate
        if formatted not in seen:
            seen.add(formatted)
            formatted_cities.append(formatted)
    
    return Response(sorted(formatted_cities))
