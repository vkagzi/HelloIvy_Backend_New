from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("locations/", views.LocationListView.as_view(), name="locations-list"),
    path("countries/", views.countries, name="countries-list"),
    path("states/", views.states, name="states-list"),
    path("cities/", views.cities, name="cities-list"),
]
