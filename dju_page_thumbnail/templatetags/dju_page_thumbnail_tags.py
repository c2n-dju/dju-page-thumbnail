# -*- coding: utf-8 -*-

from __future__ import with_statement
from classytags.arguments import IntegerArgument, Argument, StringArgument
from classytags.core import Options
from classytags.helpers import InclusionTag
from datetime import datetime
#from cms.utils.i18n import force_language, get_language_objects
from django import template
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils.encoding import force_text
from django.utils.six.moves.urllib.parse import unquote
from django.utils.translation import get_language, ugettext

#from menus.menu_pool import menu_pool
#from menus.utils import DefaultLanguageChanger
from django.utils.translation import get_language

from django.conf import settings


register = template.Library()


class ShowPagesAroundPage(InclusionTag):
    """
    give the one level deep neighbour of a page
    """
    name='dju_show_pages_around_page'
    template = 'dju_show_pages_around_page.html'
    
    options = Options(
        StringArgument('template', default='dju_show_pages_around_page.html', required=False),
    )
    
    def get_context(self,context,template):
        try:
            # If there's an exception (500), default context_processors may not be called.
            request = context['request']
        except KeyError:
            return {'template': 'menu/empty.html'}
        
        currentPage=request.current_page
        
        def get_info(page):
            try:
                imageurl=page.djupagethumbnail.image.url
            except:
                imageurl=''
            return page.get_absolute_url(),page.get_title(),imageurl
            
        scanval=[('parent', [currentPage.get_parent()]),
                 ('siblings', currentPage.get_siblings()),
                 ('descendants', currentPage.get_descendants())]
        data={}
        for datatype,objectslist in scanval:
            datalist=[]
            for p in objectslist:
                abs_url,title,imageurl = get_info(p)
                datalist.append({'abs_url':abs_url,
                                 'title':title,
                                 'imageurl':imageurl})
            data[datatype]=datalist
        try:
            context.update({'data': data,
                            'template': template})
        except:
            context = {'template': template}
        return context


register.tag(ShowPagesAroundPage)
