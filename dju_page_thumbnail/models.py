# -*- coding: utf-8 -*-
from django.db import models
from cms.extensions import PageExtension
from cms.extensions.extension_pool import extension_pool


class DjuPageThumbnail(PageExtension):
    image = models.ImageField(upload_to='pageimages', blank=True)


extension_pool.register(DjuPageThumbnail)
