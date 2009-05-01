import managers
import fields
from django.db import models

class CachedModel(models.Model):
    from_cache = False
    class Meta:
        abstract = True

class Author(CachedModel):
    name = models.CharField(max_length=32)
    objects = managers.CachingManager()

    def __unicode__(self):
        return self.name

class Site(CachedModel):
    name = models.CharField(max_length=32)
    objects = managers.CachingManager()

    def __unicode__(self):
        return self.name

class Article(CachedModel):
    name = models.CharField(max_length=32)
    author = models.ForeignKey('Author')
    sites = fields.CachingManyToManyField(Site, related_name='articles')
    objects = managers.CachingManager()

    def __unicode__(self):
        return self.name
