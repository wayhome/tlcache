#!/usr/bin/env python
# encoding: utf-8
import logging
import inspect
import os
import tempfile
import threading
import time
from hashlib import md5
from itertools import izip
import cPickle as pickle
from functools import wraps
import errno


def generate_cache_key(namespace, f, *args, **kwargs):
    """Generates a string key, based on a given function
    as well as arguments to the returned function itself.

    """
    argspec = inspect.getargspec(f)
    has_self = bool(argspec[0]) and argspec[0][0] in ('self', 'cls')
    if has_self:
        args = args[1:]

    if not isinstance(f, basestring):
        key_name = f.__name__
    else:
        key_name = f
    if not namespace:
        namespace = u'%s' % key_name
    else:
        namespace = u'%s|%s' % (namespace, key_name)

    kwargs = kwargs.items()
    if kwargs:
        kwargs = map(lambda x: ','.join(x),
                     map(lambda x: map(unicode, x),
                         sorted(kwargs,
                                key=lambda x: x[0])))
    return u':'.join([namespace] + map(unicode, args) + kwargs).encode('utf-8')


def _items(mappingorseq):
    """Wrapper for efficient iteration over mappings represented by dicts
    or sequences::

        >>> for k, v in _items((i, i*i) for i in xrange(5)):
        ...    assert k*k == v

        >>> for k, v in _items(dict((i, i*i) for i in xrange(5))):
        ...    assert k*k == v

    """
    return mappingorseq.iteritems() if hasattr(mappingorseq, 'iteritems') \
        else mappingorseq


class BaseCache(object):
    """Baseclass for the cache systems.  All the cache systems implement this
    API or a superset of it.

    :param default_timeout: the default timeout that is used if no timeout is
                            specified on :meth:`set`.
    """

    def __init__(self, default_timeout=300):
        self.default_timeout = default_timeout

    def get(self, key):
        """Looks up key in the cache and returns the value for it.
        If the key does not exist `None` is returned instead.

        :param key: the key to be looked up.
        """
        return None

    def delete(self, key):
        """Deletes `key` from the cache.  If it does not exist in the cache
        nothing happens.

        :param key: the key to delete.
        """
        pass

    def get_many(self, *keys):
        """Returns a list of values for the given keys.
        For each key a item in the list is created.  Example::

            foo, bar = cache.get_many("foo", "bar")

        If a key can't be looked up `None` is returned for that key
        instead.

        :param keys: The function accepts multiple keys as positional
                     arguments.
        """
        return map(self.get, keys)

    def get_dict(self, *keys):
        """Works like :meth:`get_many` but returns a dict::

            d = cache.get_dict("foo", "bar")
            foo = d["foo"]
            bar = d["bar"]

        :param keys: The function accepts multiple keys as positional
                     arguments.
        """
        if not keys:
            return {}
        return dict(izip(keys, self.get_many(*keys)))

    def set(self, key, value, timeout=None):
        """Adds a new key/value to the cache (overwrites value, if key already
        exists in the cache).

        :param key: the key to set
        :param value: the value for the key
        :param timeout: the cache timeout for the key (if not specified,
                        it uses the default timeout).
        """
        pass

    def add(self, key, value, timeout=None):
        """Works like :meth:`set` but does not overwrite the values of already
        existing keys.

        :param key: the key to set
        :param value: the value for the key
        :param timeout: the cache timeout for the key or the default
                        timeout if not specified.
        """
        pass

    def set_many(self, mapping, timeout=None):
        """Sets multiple keys and values from a mapping.

        :param mapping: a mapping with the keys/values to set.
        :param timeout: the cache timeout for the key (if not specified,
                        it uses the default timeout).
        """
        for key, value in _items(mapping):
            self.set(key, value, timeout)

    def delete_many(self, *keys):
        """Deletes multiple keys at once.

        :param keys: The function accepts multiple keys as positional
                     arguments.
        """
        for key in keys:
            self.delete(key)

    def clear(self):
        """Clears the cache.  Keep in mind that not all caches support
        completely clearing the cache.
        """
        pass

    def inc(self, key, delta=1):
        """Increments the value of a key by `delta`.  If the key does
        not yet exist it is initialized with `delta`.

        For supporting caches this is an atomic operation.

        :param key: the key to increment.
        :param delta: the delta to add.
        """
        self.set(key, (self.get(key) or 0) + delta)

    def dec(self, key, delta=1):
        """Decrements the value of a key by `delta`.  If the key does
        not yet exist it is initialized with `-delta`.

        For supporting caches this is an atomic operation.

        :param key: the key to increment.
        :param delta: the delta to subtract.
        """
        self.set(key, (self.get(key) or 0) - delta)

    def cache(self, namespace=None, timeout=None):
        def wrapper(f):

            @wraps(f)
            def call(*args, **kwargs):
                cache_key = generate_cache_key(namespace, f, *args, **kwargs)
                rv = self.get(cache_key)
                if rv is None:
                    rv = f(*args, **kwargs)
                    self.add(cache_key, rv, timeout=timeout)
                return rv
            return call

        return wrapper


class FileSystemCache(BaseCache):

    """A cache that stores the items on the file system.  This cache depends
    on being the only user of the `cache_dir`.  Make absolutely sure that
    nobody but this cache stores files there or otherwise the cache will
    randomly delete files therein.

    :param cache_dir: the directory where cache files are stored.
    :param threshold: the maximum number of items the cache stores before
                      it starts deleting some.
    :param default_timeout: the default timeout that is used if no timeout is
                            specified on :meth:`~BaseCache.set`. A timeout of
                            0 indicates that the cache never expires.
    :param mode: the file mode wanted for the cache files, default 0600
    """

    #: used for temporary files by the FileSystemCache
    _fs_transaction_suffix = '.__wz_cache'

    def __init__(self, cache_dir, threshold=500, default_timeout=300,
                 mode=0o600):
        BaseCache.__init__(self, default_timeout)
        self._path = cache_dir
        self._threshold = threshold
        self._mode = mode
        self.lock = threading.Lock()

        try:
            os.makedirs(self._path)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

    def _list_dir(self):
        """return a list of (fully qualified) cache filenames
        """
        return [os.path.join(self._path, fn) for fn in os.listdir(self._path)
                if not fn.endswith(self._fs_transaction_suffix)]

    def _prune(self):
        entries = self._list_dir()
        if len(entries) > self._threshold:
            now = time.time()
            try:
                for idx, fname in enumerate(entries):
                    with open(fname, 'rb') as f:
                        expires = pickle.load(f)
                    remove = (expires != 0 and expires <= now) or idx % 3 == 0

                    if remove:
                        os.remove(fname)
            except (IOError, OSError):
                pass

    def clear(self):
        with self.lock:
            for fname in self._list_dir():
                try:
                    os.remove(fname)
                except (IOError, OSError):
                    return False
        return True

    def _get_filename(self, key):
        if isinstance(key, unicode):
            key = key.encode('utf-8')  # XXX unicode review
        _hash = md5(key).hexdigest()
        return os.path.join(self._path, _hash)

    def get(self, key):
        filename = self._get_filename(key)
        try:
            with open(filename, 'rb') as f:
                pickle_time = pickle.load(f)
                if pickle_time == 0 or pickle_time >= time.time():
                    return pickle.load(f)
                else:
                    os.remove(filename)
                    return None
        except (IOError, OSError, pickle.PickleError):
            return None

    def add(self, key, value, timeout=None):
        filename = self._get_filename(key)
        if not os.path.exists(filename):
            return self.set(key, value, timeout)
        return False

    def set(self, key, value, timeout=None):
        if timeout is None:
            timeout = int(time.time() + self.default_timeout)
        elif timeout != 0:
            timeout = int(time.time() + timeout)
        filename = self._get_filename(key)
        with self.lock:
            self._prune()
            try:
                fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix,
                                           dir=self._path)
                try:
                    with os.fdopen(fd, 'wb') as f:
                        pickle.dump(timeout, f, 1)
                        pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
                except Exception as e:
                    try:
                        logging.error("fdopen error: %s", e)
                        os.close(fd)
                    except:
                        pass
                os.rename(tmp, filename)
                os.chmod(filename, self._mode)
            except (IOError, OSError):
                return False
            else:
                return True

    def delete(self, key):
        with self.lock:
            try:
                os.remove(self._get_filename(key))
            except (IOError, OSError):
                return False
            else:
                return True

    def has(self, key):
        filename = self._get_filename(key)
        try:
            with open(filename, 'rb') as f:
                pickle_time = pickle.load(f)
                if pickle_time == 0 or pickle_time >= time.time():
                    return True
                else:
                    os.remove(filename)
                    return False
        except (IOError, OSError, pickle.PickleError):
            return False


class SimpleCache(BaseCache):

    """Simple memory cache for single process environments.  This class exists
    mainly for the development server and is not 100% thread safe.  It tries
    to use as many atomic operations as possible and no locks for simplicity
    but it could happen under heavy load that keys are added multiple times.

    :param threshold: the maximum number of items the cache stores before
                      it starts deleting some.
    :param default_timeout: the default timeout that is used if no timeout is
                            specified on :meth:`~BaseCache.set`. A timeout of
                            0 indicates that the cache never expires.
    """

    def __init__(self, threshold=500, default_timeout=300):
        BaseCache.__init__(self, default_timeout)
        self._cache = {}
        self.clear = self._cache.clear
        self._threshold = threshold

    def _prune(self):
        if len(self._cache) > self._threshold:
            now = time.time()
            toremove = []
            for idx, (key, (expires, _)) in enumerate(self._cache.items()):
                if (expires != 0 and expires <= now) or idx % 3 == 0:
                    toremove.append(key)
            for key in toremove:
                self._cache.pop(key, None)

    def _get_expiration(self, timeout):
        if timeout is None:
            timeout = self.default_timeout
        if timeout > 0:
            timeout = time.time() + timeout
        return timeout

    def get(self, key):
        try:
            expires, value = self._cache[key]
            if expires == 0 or expires > time.time():
                return pickle.loads(value)
        except (KeyError, pickle.PickleError):
            return None

    def set(self, key, value, timeout=None):
        expires = self._get_expiration(timeout)
        self._prune()
        self._cache[key] = (expires, pickle.dumps(value,
                                                  pickle.HIGHEST_PROTOCOL))
        return True

    def add(self, key, value, timeout=None):
        expires = self._get_expiration(timeout)
        self._prune()
        item = (expires, pickle.dumps(value,
                                      pickle.HIGHEST_PROTOCOL))
        if key in self._cache:
            return False
        self._cache.setdefault(key, item)
        return True

    def delete(self, key):
        return self._cache.pop(key, None) is not None

    def has(self, key):
        try:
            expires, value = self._cache[key]
            return expires == 0 or expires > time.time()
        except KeyError:
            return False
