# -*- coding: utf-8 -*-
from __future__ import with_statement

from classytags.arguments import IntegerArgument, Argument, StringArgument
from classytags.core import Options
from classytags.helpers import InclusionTag,AsTag
from cms.utils.i18n import force_language, get_language_objects
from django import template
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils.encoding import force_text
from django.utils.six.moves.urllib.parse import unquote
from django.utils.translation import get_language, ugettext
from menus.menu_pool import menu_pool
from menus.utils import DefaultLanguageChanger

# pour recupere le soft_root

from cms.models import Page, Placeholder as PlaceholderModel, CMSPlugin, StaticPlaceholder
from cms.utils import get_language_from_request, get_site_id
from cms.utils.conf import get_cms_setting
import re
from django.utils.six import string_types
from django.utils import six
from cms.utils.page_resolver import get_page_queryset
from django.utils.translation import ugettext_lazy as _, get_language
from django.conf import settings

CLEAN_KEY_PATTERN = re.compile(r'[^a-zA-Z0-9_-]')


def _clean_key(key):
    return CLEAN_KEY_PATTERN.sub('-', key)


def _get_cache_key(name, page_lookup, lang, site_id):
    if isinstance(page_lookup, Page):
        page_key = str(page_lookup.pk)
    else:
        page_key = str(page_lookup)
    page_key = _clean_key(page_key)
    return get_cms_setting('CACHE_PREFIX') + name + '__page_lookup:' + page_key + '_site:' + str(site_id) + '_lang:' + str(lang)


def _get_page_by_untyped_arg(page_lookup, request, site_id):
    """
    The `page_lookup` argument can be of any of the following types:
    - Integer: interpreted as `pk` of the desired page
    - String: interpreted as `reverse_id` of the desired page
    - `dict`: a dictionary containing keyword arguments to find the desired page
    (for instance: `{'pk': 1}`)
    - `Page`: you can also pass a Page object directly, in which case there will be no database lookup.
    - `None`: the current page will be used
    """
    if page_lookup is None:
        return request.current_page
    if isinstance(page_lookup, Page):
        if request.current_page and request.current_page.pk == page_lookup.pk:
            return request.current_page
        return page_lookup
    if isinstance(page_lookup, six.string_types):
        page_lookup = {'reverse_id': page_lookup}
    elif isinstance(page_lookup, six.integer_types):
        page_lookup = {'pk': page_lookup}
    elif not isinstance(page_lookup, dict):
        raise TypeError('The page_lookup argument can be either a Dictionary, Integer, Page, or String.')
    page_lookup.update({'site': site_id})
    try:
        if 'pk' in page_lookup:
            page = Page.objects.all().get(**page_lookup)
            if request and use_draft(request):
                if page.publisher_is_draft:
                    return page
                else:
                    return page.publisher_draft
            else:
                if page.publisher_is_draft:
                    return page.publisher_public
                else:
                    return page
        else:
            return get_page_queryset(request).get(**page_lookup)
    except Page.DoesNotExist:
        site = Site.objects.get_current()
        subject = _('Page not found on %(domain)s') % {'domain': site.domain}
        body = _("A template tag couldn't find the page with lookup arguments `%(page_lookup)s\n`. "
                 "The URL of the request was: http://%(host)s%(path)s") \
               % {'page_lookup': repr(page_lookup), 'host': site.domain, 'path': request.path_info}
        if settings.DEBUG:
            raise Page.DoesNotExist(body)
        else:
            if settings.SEND_BROKEN_LINK_EMAILS:
                mail_managers(subject, body, fail_silently=True)
            return None

register = template.Library()


class NOT_PROVIDED: pass


def cut_after(node, levels, removed):
    """
    given a tree of nodes cuts after N levels
    """
    if levels == 0:
        removed.extend(node.children)
        node.children = []
    else:
        removed_local = []
        for child in node.children:
            if child.visible:
                cut_after(child, levels - 1, removed)
            else:
                removed_local.append(child)
        for removed_child in removed_local:
            node.children.remove(removed_child)
        removed.extend(removed_local)


def remove(node, removed):
    removed.append(node)
    if node.parent:
        if node in node.parent.children:
            node.parent.children.remove(node)


def cut_levels(nodes, from_level, to_level, extra_inactive, extra_active):
    """
    cutting nodes away from menus
    """
    final = []
    removed = []
    selected = None
    for node in nodes:
        if not hasattr(node, 'level'):
            # remove and ignore nodes that don't have level information
            remove(node, removed)
            continue
        if node.level == from_level:
            # turn nodes that are on from_level into root nodes
            final.append(node)
            node.parent = None
        if not node.ancestor and not node.selected and not node.descendant:
            # cut inactive nodes to extra_inactive, but not of descendants of
            # the selected node
            cut_after(node, extra_inactive, removed)
        if node.level > to_level and node.parent:
            # remove nodes that are too deep, but not nodes that are on
            # from_level (local root nodes)
            remove(node, removed)
        if node.selected:
            selected = node
        if not node.visible:
            remove(node, removed)
    if selected:
        cut_after(selected, extra_active, removed)
    if removed:
        for node in removed:
            if node in final:
                final.remove(node)
    return final


def flatten(nodes):
    flat = []
    for node in nodes:
        flat.append(node)
        flat.extend(flatten(node.children))
    return flat

class dju_SoftRoot(AsTag):
    
    name = 'dju_soft_root'

    options = Options(
        Argument('type', required=False, default="title"),
        'as',
        Argument('varname', required=False, resolve=False),
    )

    def get_value_for_context(self, context, **kwargs):
        #
        # A design decision with several active members of the django-cms
        # community that using this tag with the 'as' breakpoint should never
        # return Exceptions regardless of the setting of settings.DEBUG.
        #
        # We wish to maintain backwards functionality where the non-as-variant
        # of using this tag will raise DNE exceptions only when
        # settings.DEBUG=False.
        #
        try:
            return super(dju_SoftRootPage, self).get_value_for_context(context, **kwargs)
        except Page.DoesNotExist:
            return ''

    def get_value(self, context, type):

        request = context['request']

        namespace = None
        root_id = None

        if type == "title":

            return menu_pool.get_nodes(request, namespace, root_id)[0].get_menu_title()
        elif type == "url":
            return menu_pool.get_nodes(request, namespace, root_id)[0].get_absolute_url()
        else: 
            return "UNKNOWN"

register.tag(dju_SoftRoot)


class dju_SoftRootPage(AsTag):
    name = 'dju_soft_root_page'

    options = Options(
        Argument('page_lookup'),
        Argument('lang', required=False, default=None),
        Argument('site', required=False, default=None),
        'as',
        Argument('varname', required=False, resolve=False),
    )

    def get_value_for_context(self, context, **kwargs):
        #
        # A design decision with several active members of the django-cms
        # community that using this tag with the 'as' breakpoint should never
        # return Exceptions regardless of the setting of settings.DEBUG.
        #
        # We wish to maintain backwards functionality where the non-as-variant
        # of using this tag will raise DNE exceptions only when
        # settings.DEBUG=False.
        #
        try:
            return super(dju_SoftRootPage, self).get_value_for_context(context, **kwargs)
        except Page.DoesNotExist:
            return ''

    def get_value(self, context, page_lookup, lang, site):
        from django.core.cache import cache


        site_id = get_site_id(site)
        request = context.get('request', False)
        #print "request",dir(request.current_page)
        #print "request 2",request.current_page.get_first_root_node()

        if not request:
            return ''

        if lang is None:
            lang = get_language_from_request(request)

        cache_key = _get_cache_key('page_url', page_lookup, lang, site_id) + \
            '_type:absolute_url'

        url = cache.get(cache_key)

        if not url:
            page = _get_page_by_untyped_arg(page_lookup, request, site_id)
            if page:
                url = page.get_absolute_url(language=lang)
                cache.set(cache_key, url,
                          get_cms_setting('CACHE_DURATIONS')['content'])
        if url:
            return url
        return ''


register.tag(dju_SoftRootPage)


class ShowMenu(InclusionTag):
    """
    render a nested list of all children of the pages
    - from_level: starting level
    - to_level: max level
    - extra_inactive: how many levels should be rendered of the not active tree?
    - extra_active: how deep should the children of the active node be rendered?
    - namespace: the namespace of the menu. if empty will use all namespaces
    - root_id: the id of the root node
    - template: template used to render the menu
    """
    name = 'dju_show_menu'
    template = 'dju_page_thumbnail/F_DEBUG_menu_arround.html'

    options = Options(
        IntegerArgument('from_level', default=0, required=False),
        IntegerArgument('to_level', default=100, required=False),
        IntegerArgument('extra_inactive', default=0, required=False),
        IntegerArgument('extra_active', default=1000, required=False),
        StringArgument('template', default='menu/menu.html', required=False),
        StringArgument('namespace', default=None, required=False),
        StringArgument('root_id', default=None, required=False),
        Argument('next_page', default=None, required=False),
    )

    def get_context(self, context, from_level, to_level, extra_inactive,
                    extra_active, template, namespace, root_id, next_page):
        try:
            # If there's an exception (500), default context_processors may not be called.
            request = context['request']
        except KeyError:
            return {'template': 'menu/empty.html'}

        activeul=''
        activehref=''

        if next_page:
            children = next_page.children
        
        else:
            # new menu... get all the data so we can save a lot of queries
            nodes = menu_pool.get_nodes(request, namespace, root_id)
            if root_id: # find the root id and cut the nodes
                id_nodes = menu_pool.get_nodes_by_attribute(nodes, "reverse_id", root_id)
                if id_nodes:
                    node = id_nodes[0]
                    nodes = node.children
                    for remove_parent in nodes:
                        remove_parent.parent = None
                    from_level += node.level + 1
                    to_level += node.level + 1
                    nodes = flatten(nodes)
                else:
                    nodes = []

        nodes = menu_pool.get_nodes(request, namespace, root_id)

        isleafnode=False
        for n in nodes:
            if  n.selected:
                if n.is_leaf_node:
                    isleafnode = True
                    ancestor = "/".join(n.get_absolute_url().split('/')[0:-3])+'/'
                    directancestor = "/".join(n.get_absolute_url().split('/')[0:-2])+'/'
                    from_level=n.level-2
                else:
                    ancestor =  "/".join(n.get_absolute_url().split('/')[0:-2])+'/'
                    directancestor = "/".join(n.get_absolute_url().split('/')[0:-1])+'/'
                    from_level=n.level-1
                activehref = n
     #           print "ancestor",n.get_absolute_url(),ancestor,directancestor,from_level
                continue

        for n in nodes:
    #        print n.get_absolute_url() ==  directancestor,n.get_absolute_url(),directancestor
            if n.get_absolute_url() ==  directancestor:
                activeul = n
                continue

        to_level = from_level+2
        if  next_page:
            to_level = 100
            children = next_page.children
        else:

            children = cut_levels(nodes, from_level, to_level, extra_inactive, extra_active)
            children = menu_pool.apply_modifiers(children, request, namespace, root_id, post_cut=True)
            



        #print "activeul",activeul.get_absolute_url()
        #print "activehref",activehref.get_absolute_url()
        #print "ancestor",ancestor
        #print "directancestor",directancestor
        #print "BEFORE children",children

        newChildren = []
        for i in children:
            #print i.level,i.get_absolute_url(),
            if i.get_absolute_url().startswith(ancestor[:-1]):
                #print "kept",
                newChildren.append(i)
            #print ""

        try:
            #print "AFTER children",newChildren
            context.update({'children': newChildren,
                            'activehref':activehref,
                            'activeul':activeul,
                            'ancestor':ancestor,
                'template': template,
                'from_level': from_level,
                'to_level': to_level,
                'extra_inactive': extra_inactive,
                'extra_active': extra_active,
                'namespace': namespace})
        except:
            context = {"template": template}
        return context


register.tag(ShowMenu)

class ShowMenuArround(InclusionTag):
    """
    render a nested list of all children of the pages
    - from_level: starting level
    - to_level: max level
    - extra_inactive: how many levels should be rendered of the not active tree?
    - extra_active: how deep should the children of the active node be rendered?
    - namespace: the namespace of the menu. if empty will use all namespaces
    - root_id: the id of the root node
    - template: template used to render the menu
    """
    name = 'dju_show_menu_arround'
    template = 'dju_page_thumbnail/F_DEBUG_menu_arround.html'

    options = Options(
        IntegerArgument('from_level', default=0, required=False),
        IntegerArgument('to_level', default=100, required=False),
        IntegerArgument('extra_inactive', default=0, required=False),
        IntegerArgument('extra_active', default=1000, required=False),
        StringArgument('template', default='menu/menu.html', required=False),
        StringArgument('namespace', default=None, required=False),
        StringArgument('root_id', default=None, required=False),
        Argument('next_page', default=None, required=False),
    )

    def get_context(self, context, from_level, to_level, extra_inactive,
                    extra_active, template, namespace, root_id, next_page):
        try:
            # If there's an exception (500), default context_processors may not be called.
            request = context['request']
        except KeyError:
            return {'template': 'menu/empty.html'}

        if next_page: 
            # getting the nodel level
            nodes = menu_pool.get_nodes(request, namespace, root_id)
            for n in nodes:
                if  n.selected:
                    level=n.level
                    
            # getting the children 
            children = []
            for n in next_page.children:

                # in fact these are mutually exclusive  either we are a descendant either a sibling
                if n.descendant and n.level < level+2:
                    children.append(n)

                if n.sibling or n.selected:
                    children.append(n)
                      
        else:
            nodes = menu_pool.get_nodes(request, namespace, root_id)
            # we find the closest ancestor (that is the one with the highest level but in fact 
            # it looks like the nodes are scanned from the top to bottom that is the lowest to the highest.
            for n in nodes:
                if  n.ancestor:
                    children = [n]
                    

        
        try:
            context.update({'children': children,
                            'template': template,
                            'from_level': from_level,
                            'to_level': to_level,
                            'extra_inactive': extra_inactive,
                            'extra_active': extra_active,
                            'namespace': namespace})
        except:
            context = {"template": template}
        return context


register.tag(ShowMenuArround)




def _raw_language_marker(language, lang_code):
    return language


def _native_language_marker(language, lang_code):
    with force_language(lang_code):
        return force_text(ugettext(language))


def _current_language_marker(language, lang_code):
    return force_text(ugettext(language))


def _short_language_marker(language, lang_code):
    return lang_code


MARKERS = {
    'raw': _raw_language_marker,
    'native': _native_language_marker,
    'current': _current_language_marker,
    'short': _short_language_marker,
}


class LanguageChooser(InclusionTag):
    """
    Displays a language chooser
    - template: template used to render the language chooser
    """
    name = 'dju_language_chooser'
    template = 'menu/dummy.html'

    options = Options(
        Argument('template', default=NOT_PROVIDED, required=False),
        Argument('i18n_mode', default='raw', required=False),
    )

    def get_context(self, context, template, i18n_mode):
        if template in MARKERS:
            _tmp = template
            if i18n_mode not in MARKERS:
                template = i18n_mode
            else:
                template = NOT_PROVIDED
            i18n_mode = _tmp
        if template is NOT_PROVIDED:
            template = "menu/language_chooser.html"
        if not i18n_mode in MARKERS:
            i18n_mode = 'raw'
        if 'request' not in context:
            # If there's an exception (500), default context_processors may not be called.
            return {'template': 'cms/content.html'}
        marker = MARKERS[i18n_mode]
        current_lang = get_language()
        site = Site.objects.get_current()
        languages = []
        for lang in get_language_objects(site.pk):
            if lang.get('public', True):
                languages.append((lang['code'], marker(lang['name'], lang['code'])))
        context.update({
            'languages': languages,
            'current_language': current_lang,
            'template': template,
        })
        return context


register.tag(LanguageChooser)


class PageLanguageUrl(InclusionTag):
    """
    Displays the url of the current page in the defined language.
    You can set a language_changer function with the set_language_changer function in the utils.py if there is no page.
    This is needed if you have slugs in more than one language.
    """
    name = 'dju_page_language_url'
    template = 'cms/content.html'

    options = Options(
        Argument('lang'),
    )

    def get_context(self, context, lang):
        try:
            # If there's an exception (500), default context_processors may not be called.
            request = context['request']
        except KeyError:
            return {'template': 'cms/content.html'}
        if hasattr(request, "_language_changer"):
            try:
                url = request._language_changer(lang)
            except NoReverseMatch:
                url = DefaultLanguageChanger(request)(lang)
        else:
            # use the default language changer
            url = DefaultLanguageChanger(request)(lang)
        return {'content': url}


register.tag(PageLanguageUrl)
