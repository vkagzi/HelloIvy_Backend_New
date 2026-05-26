"""
Data migration: populate User.first_name / last_name from UserProfile.profile_json.

The profile JSON stores names at:
  profile_json -> "profile" -> "personalDetails" -> "firstName" / "lastName"
"""

from django.db import migrations


def populate_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserProfile = apps.get_model("profiles", "UserProfile")

    profiles = UserProfile.objects.exclude(profile_json={})
    updated = 0

    for profile in profiles.iterator():
        blob = profile.profile_json
        if not isinstance(blob, dict):
            continue

        inner = blob.get("profile", blob)
        if not isinstance(inner, dict):
            continue

        personal = inner.get("personalDetails", {})
        if not isinstance(personal, dict):
            continue

        first_name = (personal.get("firstName") or "").strip()
        last_name = (personal.get("lastName") or "").strip()

        if not first_name and not last_name:
            continue

        try:
            user = User.objects.get(id=profile.user_id)
        except User.DoesNotExist:
            continue

        # Only fill in if the User model fields are still empty
        changed = False
        if first_name and not user.first_name:
            user.first_name = first_name
            changed = True
        if last_name and not user.last_name:
            user.last_name = last_name
            changed = True

        if changed:
            user.save(update_fields=["first_name", "last_name"])
            updated += 1

    print(f"\n  Populated first_name/last_name for {updated} user(s).")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_user_first_name_last_name"),
        ("profiles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(populate_names, migrations.RunPython.noop),
    ]
