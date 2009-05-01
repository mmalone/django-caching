from django.core.cache import cache
from django.utils.encoding import smart_str
import inspect


# Check if the cache backend supports min_compress_len. If so, add it.
if 'min_compress_len' in inspect.getargspec(cache._cache.add)[0] and \
   'min_compress_len' in inspect.getargspec(cache._cache.set)[0]:
    class CacheClass(cache.__class__):
        def add(self, key, value, timeout=None, min_compress_len=150000):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            # Allow infinite timeouts
            if timeout is None:
                timeout = self.default_timeout
            return self._cache.add(smart_str(key), value, timeout, min_compress_len)
        
        def set(self, key, value, timeout=None, min_compress_len=150000):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            if timeout is None:
                timeout = self.default_timeout
            self._cache.set(smart_str(key), value, timeout, min_compress_len)

    cache.__class__ = CacheClass
