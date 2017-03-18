# -*- coding: utf-8 -*-
from django.contrib import admin
from cms.extensions import PageExtensionAdmin

from .models import djuPageExtension


class djuPageExtensionAdmin(PageExtensionAdmin):
    pass

admin.site.register(djuPageExtension, djuPageExtensionAdmin)
