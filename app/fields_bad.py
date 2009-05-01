from django.db.models.fields.related import ManyToManyField, ReverseManyRelatedObjectsDescriptor, ManyRelatedObjectsDescriptor
from django.db.models.query import QuerySet
from django.db.models import signals
from cache import cache

def invalidate_cache(obj, field):
    cache.set(obj._get_cache_key(field=field), None, 5)


def get_caching_related_manager(superclass, instance, field_name, related_name):
    class CachingRelatedManager(superclass):
        def all(self):
            key = instance._get_cache_key(field=field_name)
            qs = cache.get(key)
            if qs is None:
                qs = super(CachingRelatedManager, self).all()
                cache.add(key, qs, 60*30)
                qs.from_cache = False
            else:
                qs.from_cache = True
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
