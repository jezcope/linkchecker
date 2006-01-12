# -*- coding: iso-8859-1 -*-
# Copyright (C) 2004-2006 Bastian Kleineidam
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
"""
Test file parsing.
"""

import unittest
import os

import linkcheck.checker.tests


class TestFile (linkcheck.checker.tests.LinkCheckTest):
    """
    Test file:// link checking (and file content parsing).
    """

    def test_html (self):
        """
        Test links of file.html.
        """
        self.file_test("file.html")

    def test_text (self):
        """
        Test links of file.txt.
        """
        self.file_test("file.txt")

    def test_asc (self):
        """
        Test links of file.asc.
        """
        self.file_test("file.asc")

    def test_css (self):
        """
        Test links of file.css.
        """
        self.file_test("file.css")

    def test_urllist (self):
        """
        Test url list parsing.
        """
        self.file_test("urllist.txt")

    def test_files (self):
        """
        Test some direct file links.
        """
        attrs = {'curdir': os.getcwd(),
                 'datadir': 'linkcheck/checker/tests/data',
                }
        # good file
        url = u"file://%(curdir)s/%(datadir)s/file.txt" % attrs
        resultlines = [
            u"url %s" % url,
            u"cache key %s" % url,
            u"real url %s" % url,
            u"valid",
        ]
        self.direct(url, resultlines)
        # bad file
        url = u"file:/%(curdir)s/%(datadir)s/file.txt" % attrs
        resultlines = [
            u"url %s" % url,
            u"cache key %s" % url,
            u"real url %s" % url,
            u"error",
        ]
        self.direct(url, resultlines)
        # good file (missing double slash)
        url = u"file:%(curdir)s/%(datadir)s/file.txt" % attrs
        nurl = self.norm(url)
        resultlines = [
            u"url %s" % url,
            u"cache key file://%(curdir)s/%(datadir)s/file.txt" % attrs,
            u"real url file://%(curdir)s/%(datadir)s/file.txt" % attrs,
            u"warning Base URL is not properly normed. Normed URL is %s." % nurl,
            u"valid",
        ]
        self.direct(url, resultlines)
        # good dir
        url = u"file://%(curdir)s/%(datadir)s/" % attrs
        resultlines = [
            u"url %s" % url,
            u"cache key %s" % url,
            u"real url %s" % url,
            u"valid",
        ]
        self.direct(url, resultlines)


def test_suite ():
    """
    Build and return a TestSuite.
    """
    return unittest.makeSuite(TestFile)


if __name__ == '__main__':
    unittest.main()