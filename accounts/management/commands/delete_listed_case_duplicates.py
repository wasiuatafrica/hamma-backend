from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import InterfaceError, OperationalError, connection, transaction

from accounts.management.commands.merge_case_duplicate_users import (
    fill_blanks,
    normalize_email_addresses,
    reassign_relations,
)

# (lowercase email, keep_id, drop_id). The kept row is renamed to the
# lowercase email after the other account is deleted.
LISTED_DUPLICATES = (
    ("ballahmuhd@gmail.com", 691, 704),
    ("bonmichaeludeh@gmail.com", 11, 961),
    ("extremeworkbench@gmail.com", 303, 3243),
    ("godfredwisdom4@gmail.com", 283, 284),
    ("ibrahimrafiu397@gmail.com", 769, 771),
    ("kelvinebe7@gmail.com", 2649, 2616),
    ("mightysniperforex@gmail.com", 112, 111),
    ("ogooluwanick@gmail.com", 1197, 3277),
    ("olawalehabyb@gmail.com", 326, 4398),
    ("peteregwuatu@gmail.com", 56, 58),
    ("salmanushehu09@gmail.com", 408, 599),
    ("solomonigbigbi07@gmail.com", 5048, 5047),
    ("uwaenyashi@gmail.com", 664, 5058),
)


class Command(BaseCommand):
    help = (
        "Move rows off each listed duplicate onto the account to keep, "
        "delete the other account, then store the kept email in lowercase."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete the listed mixed-case accounts. Without this flag, only print the plan.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        apply = options["apply"]
        if not apply:
            self.stdout.write("Dry run. Pass --apply to delete the mixed-case accounts.")

        deleted = 0
        skipped = 0
        failed = []
        for email, keep_id, drop_id in LISTED_DUPLICATES:
            try:
                keep, drop = self._load_pair(user_model, email, keep_id, drop_id)
            except (OperationalError, InterfaceError) as exc:
                connection.close()
                failed.append(email)
                self.stderr.write(self.style.ERROR(f"{email}: database connection dropped ({exc})"))
                continue
            if drop is None:
                skipped += 1
                self.stdout.write(f"{email}: id={drop_id} is already deleted, skipping.")
                continue
            self._check_pair(email, keep, drop)
            self.stdout.write(
                f"{email}: keep id={keep.pk} ({keep.email}, active={keep.is_active}); "
                f"delete id={drop.pk} ({drop.email}, active={drop.is_active})"
            )
            if keep.is_active is False and drop.is_active:
                self.stdout.write(
                    self.style.WARNING(
                        "  warning: the kept account is inactive and the deleted account is active"
                    )
                )
            if not apply:
                continue
            if self._delete_pair(email, keep, drop):
                deleted += 1
                self.stdout.write(self.style.SUCCESS(f"  deleted id={drop_id}"))
            else:
                failed.append(email)

        if not apply:
            self.stdout.write(
                f"{len(LISTED_DUPLICATES) - skipped} accounts would be deleted. {skipped} already deleted."
            )
            return
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted}. Skipped {skipped}. Failed {len(failed)}.")
        )
        if failed:
            raise CommandError("Still need another run: " + ", ".join(failed))

    def _load_pair(self, user_model, email, keep_id, drop_id):
        try:
            keep = user_model.objects.get(pk=keep_id)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Kept account id={keep_id} for {email} does not exist.") from exc
        try:
            drop = user_model.objects.get(pk=drop_id)
        except user_model.DoesNotExist:
            return keep, None
        return keep, drop

    def _delete_pair(self, email, keep, drop):
        for attempt in (1, 2):
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = 0")
                    fill_blanks(drop, keep)
                    reassign_relations(drop, keep, set())
                    drop.delete()
                    if keep.email != email:
                        keep.email = email
                        keep.save(update_fields=["email"])
                    normalize_email_addresses(keep)
                return True
            except (OperationalError, InterfaceError) as exc:
                connection.close()
                drop_model = drop.__class__
                try:
                    drop.refresh_from_db()
                except drop_model.DoesNotExist:
                    return True
                if attempt == 1:
                    self.stdout.write(f"  connection dropped, retrying id={drop.pk} ({exc})")
                    keep.refresh_from_db()
                    continue
                self.stderr.write(self.style.ERROR(f"  failed id={drop.pk}: {exc}"))
                return False
        return False

    def _check_pair(self, email, keep, drop):
        if keep.email.lower() != email or drop.email.lower() != email:
            raise CommandError(
                f"id={keep.pk} ({keep.email}) and id={drop.pk} ({drop.email}) "
                f"are not both {email}."
            )
        if keep.email == drop.email or drop.pk == keep.pk:
            raise CommandError(f"Refusing to delete the kept account for {email}.")
