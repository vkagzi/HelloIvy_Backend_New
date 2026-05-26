from django.db import models


class UserProfile(models.Model):
    user_id = models.IntegerField(unique=True)
    profile_json = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"UserProfile({self.user_id})"
