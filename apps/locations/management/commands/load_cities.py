import csv
import os
from typing import Iterable, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.locations.models import Location


class Command(BaseCommand):
    help = "Load city/state/country data from cities.csv into the Location table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            dest="path",
            help="Path to cities.csv (defaults to project BASE_DIR/cities.csv)",
            default=None,
        )
        parser.add_argument(
            "--batch-size",
            dest="batch_size",
            help="Number of unique rows to process per DB batch (default: 1000)",
            type=int,
            default=1000,
        )

    def handle(self, *args, **options):
        path = options.get("path") or os.path.join(settings.BASE_DIR, "cities.csv")
        if not os.path.exists(path):
            self.stderr.write(f"cities.csv not found at: {path}")
            return

        batch_size = int(options.get("batch_size") or 1000)

        created = 0
        updated = 0

        def process_batch(keys: Iterable[Tuple[str, str, str]]):
            nonlocal created, updated
            keys = list(keys)
            if not keys:
                return

            # Build a single Q object matching any of the triples in this batch
            q = None
            for city, state, country in keys:
                cond = Q(city=city, state=state, country=country)
                q = cond if q is None else q | cond

            existing = set()
            if q is not None:
                existing_qs = Location.objects.filter(q).values_list(
                    "city", "state", "country"
                )
                existing = set(existing_qs)

            to_create = []
            for city, state, country in keys:
                if (city, state, country) not in existing:
                    to_create.append(Location(city=city, state=state, country=country))

            if to_create:
                Location.objects.bulk_create(to_create)
                created += len(to_create)

            updated += len(existing)

        batch_keys = set()
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                city = (row.get("city_ascii") or row.get("city") or "").strip()
                country = (row.get("country") or "").strip()
                state = (row.get("admin_name") or "").strip()
                if not city or not country:
                    continue

                key = (city, state or None, country)
                batch_keys.add(key)

                if len(batch_keys) >= batch_size:
                    process_batch(batch_keys)
                    batch_keys.clear()

        # Process any remaining keys
        if batch_keys:
            process_batch(batch_keys)

        self.stdout.write(f"Imported: {created} new, {updated} existing")
