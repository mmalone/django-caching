import functools
from django.db.models.fields.related import ManyToManyField, ReverseManyRelatedObjectsDescriptor, ManyRelatedObjectsDescriptor
from django.db.models.query import QuerySet
from django.db.models import signals
from cache import cache
from types import MethodType

CACHE_DURATION = 60 * 30

def invalidate_cache(obj, field):
    cache.set(obj._get_cache_key(field=field), None, 5)

def fix_where(where, modified=False):
    def wrap_add(f):
        @functools.wraps(f)
        def add(self, *args, **kwargs):
            """
            Wraps django.db.models.sql.where.add to indicate that a new
            'where' condition has been added.
            """
            self.modified = True
            return f(*args, **kwargs)
        return add
    where.modified = modified
    where.add = MethodType(wrap_add(where.add), where, where.__class__)
    return where


def get_pk_list_query_set(superclass):
    class PKListQuerySet(superclass):
        """
        QuerySet that, when unfiltered, fetches objects individually from
        the datastore by pk.

        The `pk_list` attribute is a list of primary keys for objects that
        should be fetched.

        """
        def __init__(self, pk_list=[], from_cache=False, *args, **kwargs):
            super(PKListQuerySet, self).__init__(*args, **kwargs)
            self.pk_list = pk_list
            self.from_cache = from_cache
            self.query.where = fix_where(self.query.where)

        def iterator(self):
            if not self.query.where.modified:
                for pk in self.pk_list:
                    yield self.model._default_manager.get(pk=pk)
            else:
                superiter = super(PKListQuerySet, self).iterator()
                while True:
                    yield superiter.next()

        def _clone(self, *args, **kwargs):
            c = super(PKListQuerySet, self)._clone(*args, **kwargs)
            c.query.where = fix_where(c.query.where, modified=self.query.where.modified)
            c.pk_list = self.pk_list
            c.from_cache = self.from_cache
            return c
    return PKListQuerySet


def get_caching_related_manager(superclass, instance, field_name, related_name):
    class CachingRelatedManager(superclass):
        def all(self):
            key = instance._get_cache_key(field=field_name)
            qs = super(CachingRelatedManager, self).get_query_set()
            PKListQuerySet = get_pk_list_query_set(qs.__class__)
            qs = qs._clone(klass=PKListQuerySet)
            pk_list = cache.get(key)
            if pk_list is None:
                pk_list = qs.values_list('pk', flat=True)
                cache.add(key, list(pk_list), CACHE_DURATION)
            else:
                qs.from_cache = True
            qs.pk_list = pk_list
            return qs

        def add(self, *objs):
            super(CachingRelatedManager, self).add(*objs)
            for obj in objs:
                invalidate_cache(obj, related_name)
            invalidate_cache(instance, field_name)

        def remove(self, *objs):
            super(CachingRelatedManager, self).remove(*objs)
            for obj in objs:
                invalidate_cache(obj, related_name)
            invalidate_cache(instance, field_name)

        def clear(self):
            objs = list(self.all())
            super(CachingRelatedManager, self).clear()
            for obj in objs:
                invalidate_cache(obj, related_name)
            invalidate_cache(instance, field_name)
    return CachingRelatedManager


class CachingReverseManyRelatedObjectsDescriptor(ReverseManyRelatedObjectsDescriptor):
    def __get__(self, instance, cls=None):
        manager = super(CachingReverseManyRelatedObjectsDescriptor, self).__get__(instance, cls)

        CachingRelatedManager = get_caching_related_manager(manager.__class__,
                                                            instance,
                                                            self.field.name,
                                                            self.field.rel.related_name)

        manager.__class__ = CachingRelatedManager
        return manager


class CachingManyRelatedObjectsDescriptor(ManyRelatedObjectsDescriptor):
    def __get__(self, instance, cls=None):
        manager = super(CachingManyRelatedObjectsDescriptor, self).__get__(instance, cls)

        CachingRelatedManager = get_caching_related_manager(manager.__class__,
                                                            instance,
                                                            self.related.get_accessor_name(),
                                                            self.related.field.name)

        manager.__class__ = CachingRelatedManager
        return manager


class CachingManyToManyField(ManyToManyField):
    def contribute_to_class(self, cls, name):
        super(CachingManyToManyField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, CachingReverseManyRelatedObjectsDescriptor(self))

    def contribute_to_related_class(self, cls, related):
        super(CachingManyToManyField, self).contribute_to_related_class(cls, related)
        setattr(cls, related.get_accessor_name(), CachingManyRelatedObjectsDescriptor(related))

