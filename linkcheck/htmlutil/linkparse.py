# -*- coding: iso-8859-1 -*-
# Copyright (C) 2001-2013 Bastian Kleineidam
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Find link tags in HTML text.
"""

import re
from .. import strformat, log, LOG_CHECK, url as urlutil
from . import linkname

MAX_NAMELEN = 256
MAX_TITLELEN = 256

unquote = strformat.unquote

# HTML4/5 link tags
# ripped mainly from HTML::Tagset.pm with HTML5 added
LinkTags = {
    'a':        [u'href'],
    'applet':   [u'archive', u'src'],
    'area':     [u'href'],
    'audio':    [u'src'], # HTML5
    'bgsound':  [u'src'],
    'blockquote': [u'cite'],
    'body':     [u'background'],
    'button':   [u'formaction'], # HTML5
    'del':      [u'cite'],
    'embed':    [u'pluginspage', u'src'],
    'form':     [u'action'],
    'frame':    [u'src', u'longdesc'],
    'head':     [u'profile'],
    'html':     [u'manifest'], # HTML5
    'iframe':   [u'src', u'longdesc'],
    'ilayer':   [u'background'],
    'img':      [u'src', u'lowsrc', u'longdesc', u'usemap'],
    'input':    [u'src', u'usemap', u'formaction'],
    'ins':      [u'cite'],
    'isindex':  [u'action'],
    'layer':    [u'background', u'src'],
    'link':     [u'href'],
    'meta':     [u'content', u'href'],
    'object':   [u'classid', u'data', u'archive', u'usemap', u'codebase'],
    'q':        [u'cite'],
    'script':   [u'src'],
    'source':   [u'src'], # HTML5
    'table':    [u'background'],
    'td':       [u'background'],
    'th':       [u'background'],
    'tr':       [u'background'],
    'track':    [u'src'], # HTML5
    'video':    [u'src'], # HTML5
    'xmp':      [u'href'],
    None:       [u'style'],
}

# HTML anchor tags
AnchorTags = {
    'a': [u'name'],
    None: [u'id'],
}

# WML tags
WmlTags = {
    'a':   [u'href'],
    'go':  [u'href'],
    'img': [u'src'],
}


# matcher for <meta http-equiv=refresh> tags
refresh_re = re.compile(ur"(?i)^\d+;\s*url=(?P<url>.+)$")
_quoted_pat = ur"('[^']+'|\"[^\"]+\"|[^\)\s]+)"
css_url_re = re.compile(ur"url\(\s*(?P<url>%s)\s*\)" % _quoted_pat)
swf_url_re = re.compile("(?i)%s" % urlutil.safe_url_pattern)
c_comment_re = re.compile(ur"/\*.*?\*/", re.DOTALL)


def strip_c_comments (text):
    """Remove C/CSS-style comments from text. Note that this method also
    deliberately removes comments inside of strings."""
    return c_comment_re.sub('', text)


class StopParse (StandardError):
    """Raised when parsing should stop."""
    pass


class TitleFinder (object):
    """Find title tags in HTML text."""

    def __init__ (self):
        """Initialize title."""
        super(TitleFinder, self).__init__()
        log.debug(LOG_CHECK, "HTML title parser")
        self.title = None

    def start_element (self, tag, attrs):
        """Search for <title> tag."""
        if tag == 'title':
            data = self.parser.peek(MAX_TITLELEN)
            data = data.decode(self.parser.encoding, "ignore")
            self.title = linkname.title_name(data)
            raise StopParse("found <title> tag")
        elif tag == 'body':
            raise StopParse("found <body> tag")


class TagFinder (object):
    """Base class handling HTML start elements.
    TagFinder instances are used as HtmlParser handlers."""

    def __init__ (self):
        """Initialize local variables."""
        super(TagFinder, self).__init__()
        # parser object will be initialized when it is used as
        # a handler object
        self.parser = None

    def start_element (self, tag, attrs):
        """Does nothing, override in a subclass."""
        pass

    def start_end_element (self, tag, attrs):
        """Delegate a combined start/end element (eg. <br/>) to
        the start_element method. Ignore the end element part."""
        self.start_element(tag, attrs)


class MetaRobotsFinder (TagFinder):
    """Class for finding robots.txt meta values in HTML."""

    def __init__ (self):
        """Initialize follow and index flags."""
        super(MetaRobotsFinder, self).__init__()
        log.debug(LOG_CHECK, "meta robots finder")
        self.follow = self.index = True

    def start_element (self, tag, attrs):
        """Search for meta robots.txt "nofollow" and "noindex" flags."""
        if tag == 'meta' and attrs.get('name') == 'robots':
            val = attrs.get_true('content', u'').lower().split(u',')
            self.follow = u'nofollow' not in val
            self.index = u'noindex' not in val
            raise StopParse("found <meta name=robots> tag")
        elif tag == 'body':
            raise StopParse("found <body> tag")


def is_meta_url (attr, attrs):
    """Check if the meta attributes contain a URL."""
    res = False
    if attr == "content":
        equiv = attrs.get_true('http-equiv', u'').lower()
        scheme = attrs.get_true('scheme', u'').lower()
        res = equiv in (u'refresh',) or scheme in (u'dcterms.uri',)
    if attr == "href":
        rel = attrs.get_true('rel', u'').lower()
        res = rel in (u'shortcut icon', u'icon')
    return res


class LinkFinder (TagFinder):
    """Find HTML links, and apply them to the callback function with the
    format (url, lineno, column, name, codebase)."""

    def __init__ (self, callback, tags=None):
        """Store content in buffer and initialize URL list."""
        super(LinkFinder, self).__init__()
        self.callback = callback
        if tags is None:
            self.tags = LinkTags
        else:
            self.tags = tags
        self.base_ref = u''
        log.debug(LOG_CHECK, "link finder")

    def start_element (self, tag, attrs):
        """Search for links and store found URLs in a list."""
        log.debug(LOG_CHECK, "LinkFinder tag %s attrs %s", tag, attrs)
        log.debug(LOG_CHECK, "line %d col %d old line %d old col %d",
            self.parser.lineno(), self.parser.column(),
            self.parser.last_lineno(), self.parser.last_column())
        if tag == "base" and not self.base_ref:
            self.base_ref = unquote(attrs.get_true("href", u''))
        tagattrs = self.tags.get(tag, [])
        # add universal tag attributes using tagname None
        tagattrs.extend(self.tags.get(None, []))
        # eliminate duplicate tag attributes
        tagattrs = set(tagattrs)
        # parse URLs in tag (possibly multiple URLs in CSS styles)
        for attr in tagattrs:
            if attr not in attrs:
                continue
            if tag == "meta" and not is_meta_url(attr, attrs):
                continue
            # name of this link
            name = self.get_link_name(tag, attrs, attr)
            # possible codebase
            base = u''
            if tag  == 'applet':
                base = unquote(attrs.get_true('codebase', u''))
            if not base:
                base = self.base_ref
            # note: value can be None
            value = unquote(attrs.get(attr))
            if tag == 'link' and attrs.get('rel') == 'dns-prefetch':
                if ':' in value:
                    value = value.split(':', 1)[1]
                value = 'dns:' + value.rstrip('/')
            # parse tag for URLs
            self.parse_tag(tag, attr, value, name, base)
        log.debug(LOG_CHECK, "LinkFinder finished tag %s", tag)

    def get_link_name (self, tag, attrs, attr):
        """Parse attrs for link name. Return name of link."""
        if tag == 'a' and attr == 'href':
            # Look for name only up to MAX_NAMELEN characters
            data = self.parser.peek(MAX_NAMELEN)
            data = data.decode(self.parser.encoding, "ignore")
            name = linkname.href_name(data)
            if not name:
                name = unquote(attrs.get_true('title', u''))
        elif tag == 'img':
            name = unquote(attrs.get_true('alt', u''))
            if not name:
                name = unquote(attrs.get_true('title', u''))
        else:
            name = u""
        return name

    def parse_tag (self, tag, attr, url, name, base):
        """Add given url data to url list."""
        assert isinstance(tag, unicode), repr(tag)
        assert isinstance(attr, unicode), repr(attr)
        assert isinstance(name, unicode), repr(name)
        assert isinstance(base, unicode), repr(base)
        assert isinstance(url, unicode) or url is None, repr(url)
        urls = []
        # look for meta refresh
        if tag == u'meta' and url:
            mo = refresh_re.match(url)
            if mo:
                urls.append(mo.group("url"))
            elif attr != 'content':
                urls.append(url)
        elif attr == u'style' and url:
            for mo in css_url_re.finditer(url):
                u = mo.group("url")
                urls.append(unquote(u, matching=True))
        elif attr == u'archive':
            urls.extend(url.split(u','))
        else:
            urls.append(url)
        if not urls:
            # no url found
            return
        for u in urls:
            assert isinstance(u, unicode) or u is None, repr(u)
            log.debug(LOG_CHECK,
              u"LinkParser found link %r %r %r %r %r", tag, attr, u, name, base)
            self.callback(u, self.parser.last_lineno(),
                          self.parser.last_column(), name, base)
