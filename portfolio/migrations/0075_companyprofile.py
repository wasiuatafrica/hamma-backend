# Generated manually for CompanyProfile migration

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0074_datasourcesetting"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("company_name", models.CharField(blank=True, default="", max_length=255)),
                ("sub_sector", models.CharField(blank=True, default="", max_length=100)),
                (
                    "market_classification",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                ("date_of_incorporation", models.DateField(blank=True, null=True)),
                ("website", models.URLField(blank=True, default="", max_length=500)),
                ("nature_of_business", models.TextField(blank=True, default="")),
                ("company_address", models.TextField(blank=True, default="")),
                ("telephone", models.CharField(blank=True, default="", max_length=50)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("board_of_directors", models.TextField(blank=True, default="")),
                (
                    "shares_outstanding",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=20, null=True
                    ),
                ),
                (
                    "prev_close",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                (
                    "dividend",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                (
                    "high_52wk_price",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                (
                    "low_52wk_price",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                ("raw_ngx_data", models.JSONField(blank=True, default=dict)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "stock",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="company_profile",
                        to="portfolio.stock",
                    ),
                ),
            ],
            options={
                "verbose_name": "Company profile",
                "verbose_name_plural": "Company profiles",
            },
        ),
    ]
