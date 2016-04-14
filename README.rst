===============================
Two Level Local Cache
===============================

.. image:: https://img.shields.io/travis/youngking/tlcache.svg
        :target: https://travis-ci.org/youngking/tlcache

.. image:: https://img.shields.io/pypi/v/tlcache.svg
        :target: https://pypi.python.org/pypi/tlcache


Two Level Local Cache

* Free software: ISC license
* Documentation: https://tlcache.readthedocs.org.


Usage
--------

* simple use

>>> from tlcache import TLCache
>>> cache = TLCache(cache_dir="/tmp/xxxxdir")
>>> lst = []
>>> @cache.cache()
... def apppend():
...     lst.append(1)
...     return lst
>>> append() == [1]
>>> append() == [1]

* cache refresh

>>> with cache.with_refresh():
...     append() == [1, 1]
...     append() == [1, 1, 1]
>>> append() == [1, 1, 1]




Features
--------

* Two level cache, first level is memory, and second level is the filesystem
