.. :changelog:

History

0.2.1 (2017-06-21)
-------------------
* Fix missing exception stack

0.2.0 (2016-08-07)
-------------------
* Even cache when got empty results
* When exception, use old data to cache degraded

0.1.7 (2016-4-14)
-----------------
* cache refresh manager, should be used with lock

0.1.6 (2016-4-14)
-----------------
* add cache refresh context manager

0.1.5 (2016-4-14)
------------------
* decrese logging warnings

0.1.4 (2016-3-16)
-------------------
* make sure fd is closed when fdopen occus exception
* set memory before file

0.1.3 (2015-11-24)
------------------
* Don't cache when results is empty

0.1.2 (2015-11-13)
__________________
* Fix a bug that which causes when cache invalidate wil not cached again.

0.1.1 (2015-11-10)
--------------------
* Inside the tlcache's `add` method, use the filecache's `set` method internally.

0.1.0 (2015-11-10)
---------------------

* First release on PyPI.
