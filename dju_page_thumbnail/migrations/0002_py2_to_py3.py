# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-09 15:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dju_page_thumbnail', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='djupagethumbnail',
            name='image',
            field=models.ImageField(blank=True, upload_to='pageimages'),
        ),
    ]
