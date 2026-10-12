"""
TODO(bootcamper): write the tests for ``src/waypoint_utils.py`` in here.

The example below covers files that parse fine: with and without ``home``,
and files with comments and blank lines in them. The rest is yours:

- Bad data: a file whose top level isn't a mapping, waypoints missing
  ``lat``, ``lon``, or ``alt``, values that aren't numbers, YAML that
  doesn't parse, and a file that isn't there.
- Out of range: latitudes past +/-90 and longitudes past +/-180 get
  rejected.
- Nothing to work with: an empty file, an empty ``waypoints`` list, and
  ``sort_clockwise_sweep`` given a list of 0 or 1 waypoints.
- ``east_north_coordinate_offset_m``: offsets you worked out yourself,
  compared with ``pytest.approx``. Never use ``==`` on meters.
- Ordering: with no ``home``, ``sort_clockwise_sweep`` goes clockwise
  starting from north.
- With a ``home``: the order starts in home's direction instead, and goes
  back to starting at north if home is right on top of the centroid.
- Two waypoints in the same direction: the closer one comes first.
- Parsing gives you frozen ``Coordinate`` objects that can't be changed.

Graded by ``warg run utils grade-tests``: pass on the real code, 90% branch
coverage, and fail on every broken copy in ``grader/mutants/``.
"""

import dataclasses

import pytest

from src.types import Coordinate
from src.waypoint_utils import (
    east_north_coordinate_offset_m,
    parse_waypoints_file,
    sort_clockwise_sweep,
)

#stored the shared data used
ONE_DEGREE_M = 111195.08

NORTH = Coordinate(1.0, 0.0, 10.0)
EAST = Coordinate(0.0, 1.0, 10.0)
SOUTH = Coordinate(-1.0, 0.0, 10.0)
WEST = Coordinate(0.0, -1.0, 10.0)


# The helper and the test below are given to you.


def write_to_tmp_waypoints_file(tmp_path, text):
    """Write ``text`` to a YAML file and hand back its path.

    ``tmp_path`` is a pytest fixture: a fresh empty directory per test.
    """
    path = tmp_path / "waypoints.yaml"
    path.write_text(text)
    return path


# One test, three files. ``parametrize`` runs the test body once per
# ``(text, expected)`` pair, and ``ids`` names each run so a failure tells you
# which file broke.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """
            home: {lat: 1, lon: 2, alt: 3}
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
        (
            """
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
              - {lat: 7, lon: 8, alt: 9}
            """,
            (None, [Coordinate(4, 5, 6), Coordinate(7, 8, 9)]),
        ),
        (
            """
            # a lap

            home: {lat: 1, lon: 2, alt: 3}

            waypoints:
              # first leg
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
    ],
    ids=["home-and-waypoints", "no-home", "comments-and-blank-lines"],
)

#Nothing/No Values to work with
def test_parse_waypoints_file_success(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


def test_parse_empty_file(tmp_path):
    # Empty file must give (None, [])
    path =write_to_tmp_waypoints_file(tmp_path, "")
    assert parse_waypoints_file(path) == (None, [])

@pytest.mark.parametrize(
    "text",
    ["waypoints: []", "waypoints:", "home: {lat: 1, lon: 2, alt: 3}"],
    ids=["empty-list","null-waypoints", "home-only"],
)

def test_parse_no_waypoints_gives_empty_list(tmp_path, text):
    path= write_to_tmp_waypoints_file(tmp_path, text)
    _, waypoints = parse_waypoints_file(path)
    assert waypoints == [] 

def test_parse_sort_empty_list():
    assert sort_clockwise_sweep([]) == []

def test_parse_sort_single_waypoint():
    assert sort_clockwise_sweep([NORTH]) == [NORTH]


#Testing Bad Data
@pytest.mark.parametrize(
    "text",
    [
        "waypoints: [unclosed",
        "- 1\n- 2\n",
        "just a string",
        "waypoints: {lat: 1, lon: 2, alt: 3}",
        "waypoints:\n  - 5\n",
        "home: 5\nwaypoints: []\n",
    ],
    ids=[
        "invalid-yaml",
        "top-level-list",
        "top-level-string",
        "waypoints-not-a-list",
        "waypoint-not-a-mapping",
        "home-not-a-mapping",
    ],
)

def test_parse_file_raises(tmp_path, text):
    path= write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError):
        parse_waypoints_file(path)

@pytest.mark.parametrize(
    "entry",
    ["{lon: 2, alt: 3}", "{lat: 1, alt: 3}", "{lat: 1, lon: 2}"],
    ids=["missing-lat", "missing-lon", "missing-alt"],
)

def test_parse_missing_key_raises(tmp_path, entry):
    path = write_to_tmp_waypoints_file(tmp_path, f"waypoints:\n  - {entry}\n")
    with pytest.raises(ValueError):
        parse_waypoints_file(path)

@pytest.mark.parametrize(
    "entry",
    [
        "{lat: abc, lon: 2, alt: 3}",
        "{lat: 1, lon: abc, alt: 3}",
        "{lat: 1, lon: 2, alt: abc}",
        "{lat: [1, 2], lon: 2, alt: 3}",
    ],
    ids=["text-lat", "text-lon", "text-alt", "list-lat"],
)

def test_parse_non_numeric_raises(tmp_path, entry):
    path = write_to_tmp_waypoints_file(tmp_path, f"waypoints:\n  - {entry}\n")
    with pytest.raises(ValueError):
        parse_waypoints_file(path)

def test_parse_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        parse_waypoints_file(tmp_path / "does_not_exist.yaml")


#Out of range and frozen coordinates
@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90, 0), (-90, 0), (0, 180), (0, -180)],
    ids=["lat-max", "lat-min", "lon-max", "lon-min"],
)

def test_parse_accepts_edges(tmp_path, lat ,lon):
    text = f"waypoints:\n  - lat: {lat}\n    lon: {lon}\n    alt: 0\n"
    path=write_to_tmp_waypoints_file(tmp_path, text)
    _, waypoints = parse_waypoints_file(path)
    assert waypoints == [Coordinate(lat, lon, 0)]

@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90.5, 0), (-90.5, 0), (0, 180.5), (0, -180.5)],
    ids=["lat-too-high", "lat-too-low", "lon-too-high", "lon-too-low"],
)

def test_parse_elements_out_of_range(tmp_path, lat, lon):
    text = f"waypoints:\n  - lat: {lat}\n    lon: {lon}\n    alt: 0\n"
    path=write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError):
        parse_waypoints_file(path)

def test_parsed_coordinates_are_frozen(tmp_path):
    path = write_to_tmp_waypoints_file(
        tmp_path, "waypoints:\n  - {lat: 4, lon: 5, alt: 6}\n"
    )
    _, waypoints = parse_waypoints_file(path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        waypoints[0].lat=0.0

#East/North coordinates offset

def test_offset_towards_north():
    east, north = east_north_coordinate_offset_m(0.0,0.0,1.0,0.0)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north ==pytest.approx(ONE_DEGREE_M, abs=1.0)

def test_offset_towards_east_at_equator():
    east, north = east_north_coordinate_offset_m(0.0,0.0,0.0,1.0)
    assert east ==pytest.approx(ONE_DEGREE_M, abs=1.0)
    assert north == pytest.approx(0.0, abs=1e-6)

def test_offset_east_shrinks_at_60_degrees():
    east, _ = east_north_coordinate_offset_m(60.0,0.0,60.0,1.0)
    assert east ==pytest.approx(ONE_DEGREE_M / 2, abs=1.0)

def test_offset_due_south_is_negative_north():
    _, north = east_north_coordinate_offset_m(0.0,0.0,-1.0,0.0)
    assert north == pytest.approx(-ONE_DEGREE_M, abs=1.0)

def test_offset_due_west_is_negative_east():
    east, _ = east_north_coordinate_offset_m(0.0,0.0,0.0,-1.0)
    assert east ==pytest.approx(-ONE_DEGREE_M, abs=1.0)

#testing sort_clockwise_sweep ordering

def test_sort_clockwise_from_north():
    scrambled = [WEST, SOUTH, NORTH, EAST]
    assert sort_clockwise_sweep(scrambled) == [NORTH, EAST, SOUTH, WEST]

def test_sort_starts_in_homes_direction():
    home = Coordinate(0.0,5.0,0.0)
    scrambled = [NORTH, WEST, EAST, SOUTH]
    assert sort_clockwise_sweep(scrambled, home) == [EAST, SOUTH, WEST, NORTH]
      
def test_sort_home_on_centroid_starts_from_north():
  home = Coordinate(0.0,0.0,0.0)
  scrambled = [NORTH, WEST, EAST, SOUTH]
  assert sort_clockwise_sweep(scrambled, home) == [NORTH, EAST, SOUTH, WEST]

def test_sort_same_bearing_closer_first():
    near = Coordinate(1.0,0.0,0.0)
    far = Coordinate(2.0,0.0,0.0)
    south=Coordinate(-3.0,0.0,0.0)
    assert sort_clockwise_sweep([south, far, near]) == [near, far, south]

  

                                                                