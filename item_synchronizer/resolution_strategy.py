from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Callable, final

from item_synchronizer.types import DateGetterFn, Item


def named(cls):
    cls.name = cls.__name__
    return cls


class ResolutionResult:
    """Result of a resolution.

    None signifise that the item is resolved to "Deleted"
    """

    class ID(Enum):
        A = 0
        B = 1
        Mix = 2

    def __init__(self, id: ID, item: Item):
        self._id = id
        self._item = item

    @property
    def result_id(self) -> ID:
        return self._id

    @property
    def item(self) -> Item:
        return self._item


class ResolutionStrategy(ABC):
    def __init__(self, *args, **kargs):
        """
        Implementations of this should accept whatever arguments they require for the resolve step that follows.
        """
        pass

    def can_resolve(self) -> bool:
        """
        Implementation can override this to signify whether the current RS is ready to
        resolve items.
        """
        return True

    @abstractmethod
    def resolve(self, item_A: Item, item_B: Item) -> ResolutionResult:
        """
        Resolve a conflice between the two items and return the resolution result as well as
        the resolved version of the item.

        If an item is None, it means that it was deleted from the corresponding side.
        """
        raise NotImplementedError()

    @classmethod
    def name(cls):
        pass


class _RecencyRS(ResolutionStrategy):
    def __init__(
        self,
        date_getter_A: DateGetterFn,
        date_getter_B: DateGetterFn,
        compare_dates: Callable[[datetime, datetime], bool],
        *args,
        **kargs,
    ):
        self._date_getter_A = date_getter_A
        self._date_getter_B = date_getter_B
        self._compare_dates = compare_dates

        super().__init__(*args, **kargs)

    def resolve(self, item_A: Item, item_B: Item) -> ResolutionResult:
        # handle None(s) ----------------------------------------------------------------------
        if item_A is None and item_B is None:
            return ResolutionResult(id=ResolutionResult.ID.A, item=item_A)
        if item_A is None:
            return ResolutionResult(id=ResolutionResult.ID.B, item=item_B)
        if item_B is None:
            return ResolutionResult(id=ResolutionResult.ID.A, item=item_A)

        # both have dates
        if self._compare_dates(self._date_getter_A(item_A), self._date_getter_B(item_B)):
            return ResolutionResult(id=ResolutionResult.ID.A, item=item_A)
        else:
            return ResolutionResult(id=ResolutionResult.ID.B, item=item_B)


@named
class MostRecentRS(_RecencyRS):
    def __init__(
        self,
        date_getter_A: DateGetterFn,
        date_getter_B: DateGetterFn,
    ):
        super().__init__(
            date_getter_A=date_getter_A,
            date_getter_B=date_getter_B,
            compare_dates=lambda date1, date2: date1 >= date2,
        )


@named
class LeastRecentRS(_RecencyRS):
    def __init__(
        self,
        date_getter_A: DateGetterFn,
        date_getter_B: DateGetterFn,
    ):
        super().__init__(
            date_getter_A=date_getter_A,
            date_getter_B=date_getter_B,
            compare_dates=lambda date1, date2: date1 <= date2,
        )


@named
class AlwaysFirstRS(ResolutionStrategy):
    def resolve(self, item_A: Item, item_B: Item) -> ResolutionResult:
        return ResolutionResult(id=ResolutionResult.ID.A, item=item_A)


@named
class AlwaysSecondRS(ResolutionStrategy):
    def resolve(self, item_A: Item, item_B: Item) -> ResolutionResult:
        return ResolutionResult(id=ResolutionResult.ID.B, item=item_B)


all_resolution_strategies = [AlwaysFirstRS, AlwaysSecondRS, MostRecentRS, LeastRecentRS]
