import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import operator_search_main as osm


ROOT = Path(__file__).resolve().parent.parent


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def run() -> None:
    osm.VERBOSE = False
    osm.DATASET_PROFILE_CACHE.clear()

    first_week = osm.resolve_dataset_profile(ROOT / "demo_data" / "first_week_of_may_2011_10k_sample.csv")
    assert_equal(first_week.trip_id_column, "column_0", "first_week trip id")
    assert_equal(first_week.mapping.get("originXColumn"), "pickup_longitude", "first_week originX")
    assert_equal(first_week.mapping.get("originYColumn"), "pickup_latitude", "first_week originY")
    assert_equal(first_week.mapping.get("destinationXColumn"), "dropoff_longitude", "first_week destinationX")
    assert_equal(first_week.mapping.get("destinationYColumn"), "dropoff_latitude", "first_week destinationY")
    assert_equal(first_week.time_column, "pickup_datetime", "first_week time")
    assert_equal(first_week.mapping.get("colorColumn"), "fare_amount", "first_week color")
    assert_equal(first_week.mapping.get("sizeColumn"), "passenger_count", "first_week size")
    if "column_0" in first_week.normalize_columns:
        raise AssertionError("first_week normalizeColumns should not include id column_0")

    toy = osm.resolve_dataset_profile(ROOT / "demo_data" / "taxi_od_small.csv")
    assert_equal(toy.trip_id_column, "trip_id", "toy trip id")
    assert_equal(toy.mapping.get("originXColumn"), "origin_x", "toy originX")
    assert_equal(toy.mapping.get("originYColumn"), "origin_y", "toy originY")
    assert_equal(toy.mapping.get("destinationXColumn"), "destination_x", "toy destinationX")
    assert_equal(toy.mapping.get("destinationYColumn"), "destination_y", "toy destinationY")
    assert_equal(toy.time_column, "pickup_time", "toy time")
    assert_equal(toy.mapping.get("colorColumn"), "fare", "toy color")
    assert_equal(toy.mapping.get("sizeColumn"), "passengers", "toy size")

    print("Schema inference tests passed.")


if __name__ == "__main__":
    run()
