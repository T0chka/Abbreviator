from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('abb_app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='abbreviationentry',
            name='highlighted',
        ),
    ]
