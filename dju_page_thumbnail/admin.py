# -*- coding: utf-8 -*-
from django.contrib import admin
from cms.extensions import PageExtensionAdmin

from .models import DjuPageThumbnail


class DjuPageThumbnailAdmin(PageExtensionAdmin):
    pass

admin.site.register(DjuPageThumbnail, DjuPageThumbnailAdmin)
