#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_tlcache
----------------------------------

Tests for `tlcache` module.
"""

import unittest
import time

from flexmock import flexmock

from tlcache.tlcache import TLCache


class TestTlcache(unittest.TestCase):

    def setUp(self):
        self.cache = TLCache("/tmp/tlcache")

    def tearDown(self):
        self.cache.clearall()

    def test_000_cache(self):
        global i
        i = 1

        @self.cache.cache(timeout=0.1)
        def incr():
            global i
            i += 1
            return i
        incr()
        self.assertEqual(incr(), 2)
        time.sleep(0.1)
        incr()
        self.assertEqual(incr(), 3)

    def test_cache_when_raises(self):

        class Number(object):
            def __init__(self):
                self.number = 0

            def add(self, num):
                self.number += 1
                return self.number + num

        @self.cache.cache(timeout=0.1)
        def incr(c):
            return Number().add(c)

        incr(0)
        self.assertEqual(incr(0), 1)
        flexmock(Number).should_receive('add').and_raise(ValueError)
        time.sleep(0.1)
        self.assertEqual(incr(0), 1)
        with self.assertRaises(ValueError):
            incr(1)


if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
