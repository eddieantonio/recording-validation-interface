# Generated by Django 2.1.2 on 2018-11-02 00:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('validation', '0022_auto_20181101_1459'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalrecording',
            name='timestamp',
            field=models.IntegerField(help_text='The offset (in milliseconds) when the phrase starts in the master file'),
        ),
        migrations.AlterField(
            model_name='recording',
            name='timestamp',
            field=models.IntegerField(help_text='The offset (in milliseconds) when the phrase starts in the master file'),
        ),
    ]