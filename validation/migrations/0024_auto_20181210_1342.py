# Generated by Django 2.1.3 on 2018-12-10 20:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('validation', '0023_auto_20181101_1828'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='phrase',
            index=models.Index(fields=['transcription'], name='transcription_idx'),
        ),
    ]