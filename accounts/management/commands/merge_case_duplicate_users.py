from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRel
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Count, UniqueConstraint
from django.db.models.functions import Lower

from allauth.account.models import EmailAddress

BLANK_VALUES = (None, "")
SKIP_FILL_FIELDS = {"email", "password"}


class Command(BaseCommand):
    help = (
        "Find users whose emails differ only by case and merge each duplicate "
        "into the account that already uses the lowercase email."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the merges. Without this flag the command only prints the plan.",
        )
        parser.add_argument(
            "--email",
            help="Only merge this address (case-insensitive). Example: user@gmail.com",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        apply = options["apply"]
        groups = self._duplicate_groups(user_model, options.get("email"))
        if not groups:
            self.stdout.write("No case-duplicate emails.")
            return

        if not apply:
            self.stdout.write(
                "Dry run. Pass --apply to merge these accounts into the lowercase email."
            )

        merged = 0
        failed = 0
        for email_key, users in groups:
            canonical = self._choose_canonical(users)
            duplicates = [user for user in users if user.pk != canonical.pk]
            self._print_group(email_key, canonical, duplicates, user_model)
            if not apply:
                continue
            try:
                with transaction.atomic():
                    self._merge_group(canonical, duplicates)
                merged += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"Failed to merge {email_key}: {exc}")
                )

        if not apply:
            self.stdout.write(f"{len(groups)} email group(s) would be merged.")
            return

        remaining = self._duplicate_groups(user_model, options.get("email"))
        self.stdout.write(
            self.style.SUCCESS(f"Merged {merged} email group(s). Failed {failed}.")
        )
        if remaining:
            raise CommandError(
                f"{len(remaining)} case-duplicate group(s) are still present."
            )

    def _duplicate_groups(self, user_model, email):
        grouped = user_model.objects.exclude(email="").annotate(email_key=Lower("email"))
        if email:
            grouped = grouped.filter(email_key=email.strip().lower())
        keys = (
            grouped.values("email_key")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("email_key")
        )
        groups = []
        for row in keys:
            users = list(
                user_model.objects.annotate(email_key=Lower("email"))
                .filter(email_key=row["email_key"])
                .order_by("date_joined", "id")
            )
            groups.append((row["email_key"], users))
        return groups

    def _choose_canonical(self, users):
        exact = [user for user in users if user.email == user.email.lower()]
        pool = exact or users
        return min(pool, key=lambda user: (user.date_joined, user.pk))

    def _print_group(self, email_key, canonical, duplicates, user_model):
        exact = canonical.email == canonical.email.lower()
        keeper = "lowercase account" if exact else "oldest account (none is lowercase yet)"
        self.stdout.write("")
        self.stdout.write(f"{email_key} — keep {keeper}")
        self._print_user("keep", canonical)
        for duplicate in duplicates:
            self._print_user("merge", duplicate)
            if canonical.is_active is False and duplicate.is_active:
                self.stdout.write(
                    self.style.WARNING(
                        "  warning: kept account is inactive and the merged account is active"
                    )
                )
            for label, count in self._relation_counts(duplicate, user_model):
                if count:
                    self.stdout.write(f"    {label}: {count}")

    def _print_user(self, role, user):
        self.stdout.write(
            f"  {role} id={user.pk} email={user.email} "
            f"active={user.is_active} joined={user.date_joined} "
            f"last_login={user.last_login}"
        )

    def _relation_counts(self, user, user_model):
        counts = []
        for rel in reverse_relations(user_model):
            if isinstance(rel, GenericRel):
                count = generic_queryset(rel, user).count()
                label = f"{rel.related_model._meta.label}.{rel.object_id_field_name}"
            elif rel.many_to_many:
                field_name = rel.field.m2m_reverse_field_name()
                through = rel.field.remote_field.through
                count = through._base_manager.filter(
                    **{through._meta.get_field(field_name).attname: user.pk}
                ).count()
                label = f"{through._meta.label}.{field_name}"
            else:
                count = rel.related_model._base_manager.filter(
                    **{rel.field.attname: user.pk}
                ).count()
                label = f"{rel.related_model._meta.label}.{rel.field.name}"
            counts.append((label, count))
        for field in user_model._meta.many_to_many:
            field_name = field.m2m_field_name()
            through = field.remote_field.through
            count = through._base_manager.filter(
                **{through._meta.get_field(field_name).attname: user.pk}
            ).count()
            counts.append((f"{through._meta.label}.{field_name}", count))
        return counts

    def _merge_group(self, canonical, duplicates):
        for duplicate in duplicates:
            fill_blanks(duplicate, canonical)
            reassign_relations(duplicate, canonical, set())
            duplicate.delete()
        lowered = canonical.email.lower()
        if canonical.email != lowered:
            canonical.email = lowered
            canonical.save(update_fields=["email"])
        normalize_email_addresses(canonical)


def reverse_relations(model):
    seen = set()
    for rel in model._meta.get_fields(include_hidden=True):
        if isinstance(rel, GenericRel):
            key = ("gfk", rel.related_model._meta.label, rel.object_id_field_name)
        elif getattr(rel, "auto_created", False) and rel.many_to_many:
            key = (
                "m2m",
                rel.field.remote_field.through._meta.label,
                rel.field.m2m_reverse_field_name(),
            )
        elif getattr(rel, "auto_created", False) and (rel.one_to_many or rel.one_to_one):
            if getattr(rel.field, "parent_link", False):
                continue
            key = ("fk", rel.field.model._meta.label, rel.field.attname)
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        yield rel


def generic_queryset(rel, instance):
    content_type = ContentType.objects.get_for_model(instance.__class__)
    return rel.related_model._base_manager.filter(
        **{
            rel.content_type_field_name: content_type,
            rel.object_id_field_name: instance.pk,
        }
    )


def fill_blanks(source, target):
    target.refresh_from_db()
    update_fields = []
    for field in target._meta.concrete_fields:
        if (
            field.primary_key
            or field.is_relation
            or field.name in SKIP_FILL_FIELDS
            or getattr(field, "auto_now", False)
            or getattr(field, "auto_now_add", False)
        ):
            continue
        current = getattr(target, field.attname)
        incoming = getattr(source, field.attname)
        if current in BLANK_VALUES and incoming not in BLANK_VALUES:
            setattr(target, field.attname, incoming)
            update_fields.append(field.attname)
    if update_fields:
        target.save(update_fields=update_fields)


def reassign_relations(source, target, seen):
    key = (source._meta.label, source.pk, target._meta.label, target.pk)
    if key in seen:
        return
    seen.add(key)
    for rel in reverse_relations(type(source)):
        if isinstance(rel, GenericRel):
            generic_queryset(rel, source).update(
                **{rel.object_id_field_name: target.pk}
            )
            continue
        if rel.many_to_many:
            move_m2m(rel.field, rel.field.m2m_reverse_field_name(), source, target, seen)
            continue
        move_fk_rows(rel.related_model, rel.field, source.pk, target, seen)
    for field in type(source)._meta.many_to_many:
        move_m2m(field, field.m2m_field_name(), source, target, seen)


def move_m2m(m2m_field, source_field_name, source, target, seen):
    through = m2m_field.remote_field.through
    field = through._meta.get_field(source_field_name)
    move_fk_rows(through, field, source.pk, target, seen)


def move_fk_rows(model, field, source_pk, target, seen):
    rows = model._base_manager.filter(**{field.attname: source_pk})
    if not field_is_unique_with(field, model):
        rows.update(**{field.attname: target.pk})
        return
    for pk in list(rows.values_list("pk", flat=True)):
        try:
            obj = model._base_manager.get(pk=pk)
        except model.DoesNotExist:
            continue
        move_or_fold(obj, field, target, seen)


def move_or_fold(obj, field, target, seen):
    conflict = find_conflict(obj, field, target)
    if conflict is not None:
        if not obj._meta.auto_created:
            fill_blanks(obj, conflict)
            reassign_relations(obj, conflict, seen)
        obj.delete()
        return
    setattr(obj, field.attname, target.pk)
    try:
        with transaction.atomic():
            obj.save(update_fields=[field.name])
    except IntegrityError:
        if getattr(obj, "primary", None) is True:
            obj.primary = False
            try:
                with transaction.atomic():
                    obj.save(update_fields=[field.name, "primary"])
                return
            except IntegrityError:
                pass
        if obj._meta.auto_created:
            obj.delete()
            return
        raise


def field_is_unique_with(field, model):
    if field.unique or field.one_to_one:
        return True
    if any(field.name in names for names in model._meta.unique_together):
        return True
    return any(
        isinstance(constraint, UniqueConstraint) and field.name in constraint.fields
        for constraint in model._meta.constraints
    )


def find_conflict(obj, field, target):
    model = obj.__class__
    base = model._base_manager.exclude(pk=obj.pk)
    if field.unique or field.one_to_one:
        return base.filter(**{field.attname: target.pk}).first()
    for lookup in unique_lookups(obj, field, target.pk):
        found = base.filter(**lookup).first()
        if found is not None:
            return found
    return None


def unique_lookups(obj, field, target_pk):
    model = obj.__class__
    lookups = []
    groups = [names for names in model._meta.unique_together if field.name in names]
    for constraint in model._meta.constraints:
        if (
            isinstance(constraint, UniqueConstraint)
            and constraint.condition is None
            and field.name in constraint.fields
        ):
            groups.append(constraint.fields)
    for names in groups:
        lookup = {field.attname: target_pk}
        for name in names:
            if name == field.name:
                continue
            other = model._meta.get_field(name)
            lookup[other.attname] = getattr(obj, other.attname)
        lookups.append(lookup)
    return lookups


def normalize_email_addresses(user):
    rows = list(EmailAddress.objects.filter(user=user).order_by("-primary", "id"))
    keepers = {}
    for row in rows:
        lowered = (row.email or "").strip().lower()
        if not lowered or lowered in keepers:
            row.delete()
            continue
        keepers[lowered] = row
    for lowered, row in keepers.items():
        if row.email != lowered:
            row.email = lowered
            row.save(update_fields=["email"])
