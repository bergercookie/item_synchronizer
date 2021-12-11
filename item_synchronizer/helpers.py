"""Helper functions and classes"""
from dataclasses import dataclass, field
from typing import MutableMapping, Set

from item_synchronizer.types import ID, DeleterFn, ItemGetterFn


@dataclass
class SideChanges:
    """Hold the items that are new, modified or deleted compared to the previous run.

    The items related to deletions have indeed already been deleted but the corresponding
    A <-> B mapping has not been updated yet. It's the responsibility of the Synchronizer class
    to do so
    """

    new: Set[ID] = field(default_factory=set)
    modified: Set[ID] = field(default_factory=set)
    deleted: Set[ID] = field(default_factory=set)

    def __str__(self) -> str:
        s = f"New Items:      {len(self.new)}\n\t"
        s += "\n\t".join(id_ for id_ in self.new)
        s = s.rstrip("\n\t")
        s += f"\nModified Items: {len(self.modified)}\n\t"
        s += "\n\t".join(id_ for id_ in self.modified)
        s = s.rstrip("\n\t")
        s += f"\nDeleted Item:   {len(self.deleted)}\n\t"
        s += "\n\t".join(id_ for id_ in self.deleted)
        s = s.rstrip("\t")
        return s


def item_getter_handle_exc(item_getter: ItemGetterFn) -> ItemGetterFn:
    """ItemGetter decorator function that handles exception when handing over the item."""

    def fn(*args, **kargs):
        try:
            return item_getter(*args, **kargs)
        except KeyError:
            return None

    return fn


def delete_n_pop(deleter: DeleterFn, map_: MutableMapping) -> DeleterFn:
    """Wrapper function for deleting and popping an item from the given map mapping."""
    delete_n_pop.__doc__ = deleter.__doc__

    def fn(id_):
        deleter(id_)
        map_.pop(id_)

    return fn


class TypeStats:
    """Container class for printing execution stats on exit - per type."""

    def __init__(self, title: str):
        self._title = title

        self._created_new = 0
        self._updated = 0
        self._deleted = 0
        self._errors = 0

        self._sep = "-" * len(self._title)

    def create_new(self):
        """Report an insertion event."""
        self._created_new += 1

    def update(self):
        """Report an update event."""
        self._updated += 1

    def delete(self):
        """Report a delete event."""
        self._deleted += 1

    def error(self):
        """Report an error during an event operation."""
        self._errors += 1

    def __str__(self) -> str:
        s = (
            f"{self._title}\n"
            f"{self._sep}\n"
            f"\t* Items created: {self._created_new}\n"
            f"\t* Items updated: {self._updated}\n"
            f"\t* Items deleted: {self._deleted}\n"
        )
        return s
