from dataclasses import dataclass
from datetime import datetime

from item_synchronizer.resolution_strategy import (
    AlwaysFirstRS,
    AlwaysSecondRS,
    LeastRecentRS,
    MostRecentRS,
    ResolutionResult,
)

dt = lambda s: datetime.fromisoformat(s)


@dataclass
class SampleItem:
    id: int
    date: datetime


sample_items = [
    SampleItem(id=1, date=dt("2021-11-01")),
    SampleItem(id=2, date=dt("2021-11-02")),
    SampleItem(id=3, date=dt("2021-11-03")),
    SampleItem(id=4, date=dt("2021-11-04")),
]


def item_getter(item: SampleItem) -> datetime:
    return item.date


def test_most_resent_rs():
    rs = MostRecentRS(date_getter_A=item_getter, date_getter_B=item_getter)
    for i in range(1, 3):
        resolution = rs.resolve(sample_items[i], sample_items[i + 1])
        assert resolution.item == sample_items[i + 1]
        assert resolution.result_id == ResolutionResult.ID.B
    for i in range(3, 1, -1):
        resolution = rs.resolve(sample_items[i], sample_items[i - 1])
        assert resolution.item == sample_items[i]
        assert resolution.result_id == ResolutionResult.ID.A


def test_least_resent_rs():
    rs = LeastRecentRS(date_getter_A=item_getter, date_getter_B=item_getter)
    for i in range(1, 3):
        resolution = rs.resolve(sample_items[i], sample_items[i + 1])
        assert resolution.item == sample_items[i]
        assert resolution.result_id == ResolutionResult.ID.A
    for i in range(3, 1, -1):
        resolution = rs.resolve(sample_items[i], sample_items[i - 1])
        assert resolution.item == sample_items[i - 1]
        assert resolution.result_id == ResolutionResult.ID.B


def test_always_first_rs():
    rs = AlwaysFirstRS()
    for i in range(1, 3):
        resolution = rs.resolve(sample_items[i], sample_items[i + 1])
        assert resolution.item == sample_items[i]
        assert resolution.result_id == ResolutionResult.ID.A
    for i in range(3, 1, -1):
        resolution = rs.resolve(sample_items[i], sample_items[i - 1])
        assert resolution.item == sample_items[i]
        assert resolution.result_id == ResolutionResult.ID.A


def test_always_second_rs():
    rs = AlwaysSecondRS()
    for i in range(1, 3):
        resolution = rs.resolve(sample_items[i], sample_items[i + 1])
        assert resolution.item == sample_items[i + 1]
        assert resolution.result_id == ResolutionResult.ID.B
    for i in range(3, 1, -1):
        resolution = rs.resolve(sample_items[i], sample_items[i - 1])
        assert resolution.item == sample_items[i - 1]
        assert resolution.result_id == ResolutionResult.ID.B
