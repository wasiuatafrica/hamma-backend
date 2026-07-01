from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0076_alter_companyprofile_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companyprofile",
            name="telephone",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="companyprofile",
            name="email",
            field=models.CharField(blank=True, default="", max_length=254),
        ),
    ]
