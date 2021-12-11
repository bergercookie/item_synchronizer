from dataclasses import dataclass
from functools import total_ordering
from typing import List, MutableMapping

import pytest
from bidict import MutableBidict, bidict  # type: ignore

from item_synchronizer import Synchronizer
from item_synchronizer.helpers import SideChanges
from item_synchronizer.resolution_strategy import (
    AlwaysFirstRS,
    AlwaysSecondRS,
    ResolutionStrategy,
)
from item_synchronizer.types import ID


@total_ordering
@dataclass
class Item:
    val: str

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        return self.val < other.val


class ItemA(Item):
    pass


class ItemB(Item):
    pass


ItemStoreA = MutableMapping[str, ItemA]
ItemStoreB = MutableMapping[str, ItemB]


def create_synchronizer(
    store_A: ItemStoreA,
    store_B: ItemStoreB,
    resolution_strategy: ResolutionStrategy = AlwaysFirstRS(),
    deleted_ids: List[ID] = [],
):
    def A_inserter(item: ItemA) -> ID:
        store_A[item.val] = item
        return str(item)

    def B_inserter(item: ItemB) -> ID:
        store_B[item.val] = item
        return str(item)

    def A_updater(id_: ID, item: ItemA):
        store_A[id_] = item

    def B_updater(id_: ID, item: ItemB):
        store_B[id_] = item

    def A_deleter(id_: ID):
        del store_A[id_]

    def B_deleter(id_: ID):
        del store_B[id_]

    def A_item_getter(id_: ID) -> Item:
        return store_A[id_]

    def B_item_getter(id_: ID) -> Item:
        return store_B[id_]

    # create correspondences
    bidict_: MutableBidict = bidict()

    # the A<->B mapping should still contain entries for deleted items
    for id_ in list(store_A.keys()) + list(store_B.keys()) + deleted_ids:
        bidict_[str(id_)] = str(id_)

    s = Synchronizer(
        A_to_B=bidict_,
        inserter_to_A=A_inserter,
        inserter_to_B=B_inserter,
        updater_to_A=A_updater,
        updater_to_B=B_updater,
        deleter_to_A=A_deleter,
        deleter_to_B=B_deleter,
        converter_to_A=lambda item_B: ItemA(item_B.val),
        converter_to_B=lambda item_A: ItemB(item_A.val),
        item_getter_A=A_item_getter,
        item_getter_B=B_item_getter,
        resolution_strategy=resolution_strategy,  # type: ignore
    )

    return s


def run_sync_n_compare(
    synchronizer: Synchronizer,
    store_A: ItemStoreA,
    store_B: ItemStoreB,
    changes_A: SideChanges,
    changes_B: SideChanges,
    args: List[int],
):
    assert store_A != store_B
    synchronizer.sync(changes_A, changes_B)
    assert len(store_A) == len(store_B)
    assert store_A == store_B
    assert len(store_A) == len(args)
    assert sorted(store_A.keys()) == sorted([str(i) for i in args])
    assert sorted(store_A.values()) == sorted([ItemA(str(i)) for i in args])


def test_new_items_from_both_empty_both():
    changes_A = SideChanges(new={"1", "2", "3", "4", "5"})
    changes_B = SideChanges(new={"10", "20", "30", "40", "50"})
    store_A = {id_: ItemA(id_) for id_ in changes_A.new}
    store_B = {id_: ItemB(id_) for id_ in changes_B.new}

    synchronizer = create_synchronizer(store_A, store_B)

    run_sync_n_compare(
        synchronizer,
        store_A,
        store_B,
        changes_A,
        changes_B,
        [1, 2, 3, 4, 5, 10, 20, 30, 40, 50],
    )


def test_new_items_from_A():
    changes_A = SideChanges(new={"3", "4", "5"})
    changes_B = SideChanges(new=set())
    store_A = {str(id_): ItemA(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    store_B = {str(id_): ItemB(str(id_)) for id_ in [1, 2]}
    synchronizer = create_synchronizer(store_A, store_B)
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [1, 2, 3, 4, 5])


def test_new_items_from_A_empty_B():
    changes_A = SideChanges(new={"1", "2", "3", "4", "5"})
    changes_B = SideChanges(new=set())
    store_A = {str(id_): ItemA(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    store_B = {}
    synchronizer = create_synchronizer(store_A, store_B)
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [1, 2, 3, 4, 5])


def test_new_items_from_B_empty_A():
    changes_A = SideChanges(new=set())
    changes_B = SideChanges(new={"1", "2", "3", "4", "5"})
    store_A = {}
    store_B = {str(id_): ItemB(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    synchronizer = create_synchronizer(store_A, store_B)
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [1, 2, 3, 4, 5])


def test_modified_items_from_A():
    changes_A = SideChanges(new=set(), modified={"1", "2", "3", "4", "5"})
    changes_B = SideChanges()
    store_A = {str(id_): ItemA(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    store_B = {str(id_): ItemB(f"old_{id_}") for id_ in [1, 2, 3, 4, 5]}

    synchronizer = create_synchronizer(store_A, store_B)
    assert store_A != store_B
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [1, 2, 3, 4, 5])


# You should manually delete items from the mappings, even if the deletion happened on the same
# side
# If a deletion happened in store A then I should be the one to remove it from the mapping. if
# I assume it it already deleted from the mapping then I wouldn't know what's the corresponding
# item in store B to delete
def test_deleted_items_from_A():
    changes_A = SideChanges(new=set(), deleted={"1", "2", "3"})
    changes_B = SideChanges()
    store_A = {str(id_): ItemA(str(id_)) for id_ in [4, 5]}
    store_B = {str(id_): ItemB(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    synchronizer = create_synchronizer(store_A, store_B, deleted_ids=["1", "2", "3"])
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [4, 5])


def test_deleted_items_from_B():
    changes_A = SideChanges()
    changes_B = SideChanges(deleted={"2"})
    store_A = {str(id_): ItemA(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    store_B = {str(id_): ItemB(str(id_)) for id_ in [1, 3, 4, 5]}
    synchronizer = create_synchronizer(store_A, store_B, deleted_ids=["2"])
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, [1, 3, 4, 5])


@pytest.mark.parametrize(
    "resolution_strategy,results",
    [(AlwaysFirstRS(), [1, 3, 4, 5]), (AlwaysSecondRS(), [1, 4, 5])],
)
def test_modified_from_A_deleted_from_B(
    resolution_strategy: ResolutionStrategy, results: List[int]
):
    changes_A = SideChanges(new=set(), modified={"3", "4"})
    changes_B = SideChanges(new=set(), deleted={"2", "3"})
    store_A = {str(id_): ItemA(str(id_)) for id_ in [1, 2, 3, 4, 5]}
    store_B = {
        "1": ItemB("1"),
        "4": ItemB("old_4"),
        "5": ItemB("5"),
    }
    if resolution_strategy == AlwaysFirstRS:
        store_B["3"] = ItemB("old_3")

    synchronizer = create_synchronizer(
        store_A, store_B, resolution_strategy=resolution_strategy, deleted_ids=["2", "3"]
    )
    run_sync_n_compare(synchronizer, store_A, store_B, changes_A, changes_B, results)


@pytest.mark.parametrize(
    "resolution_strategy,suffix",
    [(AlwaysFirstRS(), "A"), (AlwaysSecondRS(), "B")],
)
def test_modified_from_A_modified_from_B(resolution_strategy: ResolutionStrategy, suffix: str):
    common_modified_range = range(2, 12)
    full_range = range(1, 13)
    changes_A = SideChanges(
        new=set(), modified={"1", *[str(i) for i in common_modified_range]}
    )
    changes_B = SideChanges(
        new=set(), modified={*[str(i) for i in common_modified_range], "12"}
    )

    # 1 is always going to be from A
    # 12 is always going to be from B
    # 2->11 depends on the parameter of the test
    store_A = {str(i): ItemA(str(i)) for i in full_range}
    store_A = {"1": ItemA("1_modified_by_A")}
    store_A.update({str(i): ItemA(f"{i}_modified_by_A") for i in common_modified_range})
    store_B = {str(i): ItemB(str(i)) for i in full_range}
    store_B = {"12": ItemB("12_modified_by_B")}
    store_B.update({str(i): ItemB(f"{i}_modified_by_B") for i in common_modified_range})

    synchronizer = create_synchronizer(
        store_A,
        store_B,
        resolution_strategy=resolution_strategy,
    )

    expected_A_results = {str(i): ItemA(str(i)) for i in full_range}
    expected_A_results["1"] = ItemA("1_modified_by_A")
    expected_A_results["12"] = ItemA("12_modified_by_B")
    expected_A_results.update(
        {str(i): ItemA(f"{i}_modified_by_{suffix}") for i in common_modified_range}
    )

    assert store_A != store_B
    synchronizer.sync(changes_A, changes_B)
    assert len(store_A) == len(store_B)
    assert store_A == store_B
    assert sorted(store_A.keys()) == sorted(expected_A_results.keys())
    assert sorted(store_A.values()) == sorted(expected_A_results.values())


@pytest.mark.parametrize(
    "resolution_strategy",
    [AlwaysFirstRS(), AlwaysSecondRS()],
)
def test_deleted_from_A_deleted_from_B(resolution_strategy):
    common_deleted_range = [5, 6, 7]
    changes_A = SideChanges(new=set(), deleted={"4", *[str(i) for i in common_deleted_range]})
    changes_B = SideChanges(new=set(), deleted={*[str(i) for i in common_deleted_range], "8"})

    # 4 is deleted from A
    # 8 is deleted from B
    # 5, 6, 7 deleted from both
    store_A = {str(i): ItemA(str(i)) for i in [1, 2, 3, 8, 9, 10]}
    store_B = {str(i): ItemB(str(i)) for i in [1, 2, 3, 4, 9, 10]}

    synchronizer = create_synchronizer(
        store_A,
        store_B,
        resolution_strategy=resolution_strategy,
        deleted_ids=["4", "5", "6", "7", "8"],
    )

    expected_A_results = {str(i): ItemA(str(i)) for i in [1, 2, 3, 9, 10]}

    assert store_A != store_B
    synchronizer.sync(changes_A, changes_B)
    assert len(store_A) == len(store_B)
    assert store_A == store_B
    assert sorted(store_A.keys()) == sorted(expected_A_results.keys())
    assert sorted(store_A.values()) == sorted(expected_A_results.values())


@pytest.mark.skip()
def test_multiple_syncs():
    pass


@pytest.mark.skip()
def test_wrong_insert_cb():
    pass


@pytest.mark.skip()
def test_wrong_update_cb():
    pass


@pytest.mark.skip()
def test_wrong_delete_cb():
    pass


@pytest.mark.skip()
def test_wrong_item_getter_cb():
    pass
