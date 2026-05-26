from django.db import models
from unidecode import unidecode


class Location(models.Model):
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=200, blank=True, null=True)
    country = models.CharField(max_length=200)

    class Meta:
        unique_together = ("city", "state", "country")
        ordering = ["country", "state", "city"]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        parts = [self.city]
        if self.state:
            parts.append(self.state)
        parts.append(self.country)
        return ", ".join(parts)
    
    @property
    def city_ascii(self) -> str:
        """Return ASCII-only version of city name"""
        return unidecode(self.city)
    
    @property
    def state_ascii(self) -> str | None:
        """Return ASCII-only version of state name"""
        return unidecode(self.state) if self.state else None
    
    @property
    def country_ascii(self) -> str:
        """Return ASCII-only version of country name"""
        return unidecode(self.country)
