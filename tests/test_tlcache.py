#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_tlcache
----------------------------------

Tests for `tlcache` module.
"""

import logging
import unittest
import time

import gevent

from flexmock import flexmock

from tlcache.tlcache import TLCache

from gevent import monkey
monkey.patch_all()

logging.basicConfig(level="INFO")


class TestTlcache(unittest.TestCase):

    def setUp(self):
        self.cache = TLCache("/tmp/tlcache")

    def tearDown(self):
        self.cache.clearall()

    def test_000_cache(self):
        global i
        i = 0

        @self.cache.cache(timeout=0.1)
        def incr():
            global i
            i += 1
            return i
        incr()
        self.assertEqual(incr(), 1)
        time.sleep(0.1)
        incr()
        self.assertEqual(incr(), 2)

    def test_cache_concurrency(self):
        global i
        i = 0

        @self.cache.cache(timeout=0.1)
        def incr():
            global i
            i += 1
            gevent.sleep(0)
            return i
        threads = [gevent.spawn(incr) for _ in range(10)]
        gevent.joinall(threads, timeout=0.1)
        self.assertEqual(incr(), 1)
        time.sleep(0.1)
        threads = [gevent.spawn(incr) for _ in range(10)]
        gevent.joinall(threads, timeout=0.1)
        self.assertEqual(incr(), 2)

    def test_cache_none(self):
        global i
        i = 0

        @self.cache.cache(timeout=0.1)
        def incr():
            global i
            i += 1

        incr()
        self.assertEqual(i, 1)
        incr()
        self.assertEqual(i, 1)

    def test_cache_refresh(self):
        lst = []

        @self.cache.cache(timeout=10)
        def append():
            lst.append(1)
            return lst
        append()
        self.assertEqual(append(), [1])
        with self.cache.with_refresh():
            append()
            self.assertEqual(lst, [1, 1])
            self.assertEqual(append(), [1, 1, 1])
        append()
        self.assertEqual(lst, [1, 1, 1])

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
