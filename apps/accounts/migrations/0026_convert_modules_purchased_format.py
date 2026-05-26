"""
Data migration: convert modules_purchased from flat string list
(e.g. ["a", "a", "b"]) to [{module, quantity}] format
(e.g. [{"module": "a", "quantity": 2}, {"module": "b", "quantity": 1}]).
"""

from django.db import migrations


def _deduplicate(entries):
    """Aggregate a list of entries (old string format or new dict format with dupes) into deduplicated dicts."""
    counts: dict[str, int] = {}
    for entry in entries:
        if isinstance(entry, str):
            counts[entry] = counts.get(entry, 0) + 1
        elif isinstance(entry, dict):
            m = entry.get("module", "")
            q = entry.get("quantity", 1)
            counts[m] = counts.get(m, 0) + q
    return [{"module": m, "quantity": q} for m, q in counts.items()]


def _needs_migration(entries):
    """Check if the list needs migration (old string format or duplicate dict entries)."""
    if not entries or not isinstance(entries, list):
        return False
    # Old string format
    if isinstance(entries[0], str):
        return True
    # New dict format but with duplicate module keys
    if isinstance(entries[0], dict):
        modules = [e.get("module") for e in entries if isinstance(e, dict)]
        return len(modules) != len(set(modules))
    return False


def convert_forward(apps, schema_editor):
    UserPayment = apps.get_model("accounts", "UserPayment")
    SchoolPayment = apps.get_model("accounts", "SchoolPayment")

    for payment in UserPayment.objects.all():
        old = payment.modules_purchased
        if not _needs_migration(old):
            continue
        payment.modules_purchased = _deduplicate(old)
        payment.save(update_fields=["modules_purchased"])

    for payment in SchoolPayment.objects.all():
        old = payment.modules_purchased
        if not _needs_migration(old):
            continue
        result = _deduplicate(old)
        # Prefer quantities from metadata if converting from old string format
        if isinstance(old[0], str):
            meta_qty = (
                payment.metadata.get("module_quantities", {})
                if isinstance(payment.metadata, dict)
                else {}
            )
            if meta_qty:
                result = [
                    {"module": e["module"], "quantity": meta_qty.get(e["module"], e["quantity"])}
                    for e in result
                ]
        payment.modules_purchased = result
        payment.save(update_fields=["modules_purchased"])


def convert_backward(apps, schema_editor):
    UserPayment = apps.get_model("accounts", "UserPayment")
    SchoolPayment = apps.get_model("accounts", "SchoolPayment")

    for payment in UserPayment.objects.all():
        old = payment.modules_purchased
        if not old or not isinstance(old, list):
            continue
        if old and isinstance(old[0], str):
            continue
        flat = []
        for entry in old:
            flat.extend([entry["module"]] * entry.get("quantity", 1))
        payment.modules_purchased = flat
        payment.save(update_fields=["modules_purchased"])

    for payment in SchoolPayment.objects.all():
        old = payment.modules_purchased
        if not old or not isinstance(old, list):
            continue
        if old and isinstance(old[0], str):
            continue
        flat = []
        for entry in old:
            flat.extend([entry["module"]] * entry.get("quantity", 1))
        payment.modules_purchased = flat
        payment.save(update_fields=["modules_purchased"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_merge_20260422_1759"),
    ]

    operations = [
        migrations.RunPython(convert_forward, convert_backward),
    ]
