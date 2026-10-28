import uuid

from django.db import models


class UUIDModel(models.Model):
    """Abstract base for every model: the primary key is a random UUID
    instead of an incrementing number, so ids can't be guessed or counted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
