"""House of the bi-directional Synchronizer class."""
from typing import Any, Callable, Literal, Optional, Tuple, TypeVar, cast

from bidict import MutableBidict  # type: ignore
from loguru import logger

from item_synchronizer.helpers import (
    SideChanges,
    TypeStats,
    delete_n_pop,
    item_getter_handle_exc,
)
from item_synchronizer.resolution_strategy import ResolutionResult, ResolutionStrategy
from item_synchronizer.types import (
    ID,
    ConverterFn,
    DeleterFn,
    InserterFn,
    Item,
    ItemGetterFn,
    UpdaterFn,
)

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])


class Synchronizer:  # pylint: disable="R0903,R0902"
    """
    Synchronize items from two different sources.

    This class aims to offer an abstract and versatile way to create, update and/or delete
    items to keep two "sources" in sync.

    These "items" may range from Calendar entries, TODO task lists, or whatever else you want
    as long as the user registers the appropriate functions/methods to convert from one said
    item to another.
    """

    def __init__(
        self,
        *,
        A_to_B: MutableBidict,
        inserter_to_A: InserterFn,
        inserter_to_B: InserterFn,
        updater_to_A: UpdaterFn,
        updater_to_B: UpdaterFn,
        deleter_to_A: DeleterFn,
        deleter_to_B: DeleterFn,
        converter_to_A: ConverterFn,
        converter_to_B: ConverterFn,
        item_getter_A: ItemGetterFn,
        item_getter_B: ItemGetterFn,
        resolution_strategy: ResolutionStrategy,
        side_names: Tuple[str, str] = ("A Side", "B Side"),
    ):
        self._A_to_B: MutableBidict = A_to_B
        self._B_to_A: MutableBidict = A_to_B.inverse
        self._inserter_to_A = self._catch_exc(inserter_to_A)
        self._inserter_to_B = self._catch_exc(inserter_to_B)
        self._updater_to_A = self._catch_exc(updater_to_A)
        self._updater_to_B = self._catch_exc(updater_to_B)
        self._deleter_to_A = self._catch_exc(delete_n_pop(deleter_to_A, self._A_to_B))
        self._deleter_to_B = self._catch_exc(delete_n_pop(deleter_to_B, self._B_to_A))
        self._converter_to_A = self._catch_exc(converter_to_A)
        self._converter_to_B = self._catch_exc(converter_to_B)
        self._item_getter_A = item_getter_handle_exc(item_getter_A)
        self._item_getter_B = item_getter_handle_exc(item_getter_B)
        self._rs = resolution_strategy
        self._stats = tuple(TypeStats(name) for name in side_names)

    def _catch_exc(self, fn: _FuncT) -> _FuncT:
        """Run the decorated function and catch all exceptions."""

        def wrapper(*args, **kargs):
            try:
                return fn(*args, **kargs)
            except:  # pylint: disable="W0702"
                if fn.__doc__ is not None:
                    desc = fn.__doc__.split("\n")[0].strip().rstrip(".")
                else:
                    desc = str(fn)
                logger.error(f"[{desc}] Operation failed.")
                logger.opt(exception=True).debug(f"[{desc}] Operation failed.")
                return None

        return cast(_FuncT, wrapper)

    def _convert_n_insert(self, id_: ID, insert_to_side: Literal["A", "B"]) -> Optional[ID]:
        if insert_to_side == "A":
            item_getter = self._item_getter_B
            converter = self._converter_to_A
            inserter = self._inserter_to_A
        elif insert_to_side == "B":
            item_getter = self._item_getter_A
            converter = self._converter_to_B
            inserter = self._inserter_to_B
        else:
            raise RuntimeError()

        item = item_getter(id_)
        if item is None:
            return None
        converted_item = converter(item)
        if converted_item is None:
            return None
        new_id: ID = inserter(converted_item)

        if insert_to_side == "A":
            self._stats[0].create_new()
        else:
            self._stats[1].create_new()

        return new_id

    def _convert_n_update_to_A(self, id_A: ID, item: Item):
        assert item is not None
        converted_item = self._converter_to_A(item)
        if converted_item is None:
            return

        self._updater_to_A(id_A, converted_item)
        self._stats[0].update()

    def _convert_n_update_to_B(self, id_B: ID, item: Item):
        assert item is not None
        converted_item = self._converter_to_B(item)
        if converted_item is None:
            return

        self._updater_to_B(id_B, converted_item)
        self._stats[1].update()

    def sync(self, changes_A: SideChanges, changes_B: SideChanges):
        """
        Main method for running a full bi-directional sync given changes from the two sides
        involved.

        This is the main method you are supposed to call after the instance initialization to
        actually synchronize the two sides.
        """
        try:
            return self._sync(changes_A=changes_A, changes_B=changes_B)
        finally:
            logger.warning(f"\n\n{self._stats[0]}\n{self._stats[1]}")

    def _sync_new_items(self, changes_A: SideChanges, changes_B: SideChanges):
        """
        Sync only the new items from each side.

        Items that are new on either side should have no problem getting added to the other
        insert_to_side.
        """
        props = (
            (self._A_to_B, changes_A.new, "B"),
            (self._B_to_A, changes_B.new, "A"),
        )
        for (map_, new_changes, insert_to_side) in props:
            for id_ in new_changes:
                insert_to_side = cast(Literal["A", "B"], insert_to_side)
                inserted_id = self._convert_n_insert(id_, insert_to_side)
                if inserted_id is None:
                    continue
                map_[id_] = inserted_id

    def _sync(
        self, changes_A: SideChanges, changes_B: SideChanges
    ):  # pylint: disable="R0912,R0915,R0914"
        self._sync_new_items(changes_A=changes_A, changes_B=changes_B)

        # items modified on both sides --------------------------------------------------------
        touched_from_B = changes_B.modified.union(changes_B.deleted)
        touched_from_B_in_A_map = {self._B_to_A[change]: change for change in touched_from_B}
        touched_from_A = changes_A.modified.union(changes_A.deleted)
        touched_from_A_in_B_map = {self._A_to_B[change]: change for change in touched_from_A}

        def format_conflict_id(conflict: ID) -> str:
            prefix_mod = "Modified from"
            prefix_del = "Deleted from"

            # find whether the A ID was deleted or modified
            conflict_in_A = touched_from_A_in_B_map[conflict]
            if conflict_in_A in changes_A.deleted:
                a_str = f"{prefix_del} A"
            elif conflict_in_A in changes_A.modified:
                a_str = f"{prefix_mod} A"
            else:
                logger.exception(
                    f"Programmatic Error regarding conflict ID [{conflict} / {conflict_in_A}]"
                )

            if conflict in changes_B.deleted:
                b_str = f"{prefix_del} B"
            elif conflict in changes_B.modified:
                b_str = f"{prefix_mod} B"
            else:
                logger.exception(
                    f"Programmatic Error regarding conflict ID [{conflict} / {conflict_in_A}]"
                )

            s = f"- [B] {conflict} / [A] {conflict_in_A}\n  {b_str}\n  {a_str}"  # type: ignore
            return s

        conflicts_in_B = touched_from_B.intersection(touched_from_A_in_B_map)
        if conflicts_in_B:
            s = "\n\n"
            s += "Modified items on both sides:\n\n"
            s += "\n".join([format_conflict_id(conflict) for conflict in conflicts_in_B])
            s += f"\n\nResolution strategy: {self._rs.__class__.__name__}"
            logger.opt(lazy=True).debug(s)

        for conflict_in_B in conflicts_in_B:
            conflict_in_A = self._B_to_A[conflict_in_B]

            # find the items in conflict
            item_B = self._item_getter_B(conflict_in_B)
            item_A = self._item_getter_A(conflict_in_A)
            result = self._rs.resolve(item_A=item_A, item_B=item_B)
            if result.result_id == ResolutionResult.ID.Mix:
                raise RuntimeError("Can't handle mixed results at the moment.")
            elif result.result_id == ResolutionResult.ID.A:
                if item_A is None:
                    if conflict_in_B in changes_B.deleted:
                        # item already deleted - just remove it from the mapping
                        self._B_to_A.pop(conflict_in_B)
                    else:
                        self._deleter_to_B(conflict_in_B)
                        self._stats[1].delete()
                else:
                    self._convert_n_update_to_B(conflict_in_B, item_A)
            else:
                if item_B is None:
                    if conflict_in_A in changes_A.deleted:
                        # item already deleted - just remove it from the mapping
                        self._A_to_B.pop(conflict_in_A)
                    else:
                        self._deleter_to_A(conflict_in_A)
                        self._stats[0].delete()
                else:
                    self._convert_n_update_to_A(conflict_in_A, item_B)

        not_conflicts_from_B = touched_from_B.difference(touched_from_A_in_B_map)
        not_conflicts_from_A = touched_from_A.difference(touched_from_B_in_A_map)

        # delete and update at will
        for id_B in not_conflicts_from_B:
            id_A = self._B_to_A[id_B]
            if id_B in changes_B.modified:
                item_B = self._item_getter_B(id_B)
                self._convert_n_update_to_A(id_A, item_B)
            elif id_B in changes_B.deleted:
                self._deleter_to_A(id_A)
                self._stats[0].delete()
            else:
                raise RuntimeError("Programmatic Error")
        for id_A in not_conflicts_from_A:
            id_B = self._A_to_B[id_A]
            if id_A in changes_A.modified:
                item_A = self._item_getter_A(id_A)
                self._convert_n_update_to_B(id_B, item_A)
            elif id_A in changes_A.deleted:
                self._deleter_to_B(id_B)
                self._stats[1].delete()
            else:
                raise RuntimeError("Programmatic Error")
