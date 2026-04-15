from app.engine.hex import Hex, HEX_DIRECTIONS, hex_distance, hex_neighbors, hex_range


def test_hex_equality_and_hash():
    assert Hex(1, 2) == Hex(1, 2)
    assert hash(Hex(1, 2)) == hash(Hex(1, 2))
    assert Hex(1, 2) != Hex(2, 1)


def test_hex_s_coordinate():
    h = Hex(2, -1)
    assert h.s == -1
    assert h.q + h.r + h.s == 0


def test_hex_addition_returns_new_hex():
    a = Hex(1, 2)
    b = Hex(3, -1)
    result = a + b
    assert result == Hex(4, 1)
    # Immutability: originals unchanged
    assert a == Hex(1, 2)
    assert b == Hex(3, -1)


def test_hex_directions_are_six_unit_vectors():
    assert len(HEX_DIRECTIONS) == 6
    for d in HEX_DIRECTIONS:
        assert hex_distance(Hex(0, 0), d) == 1


def test_hex_neighbors_returns_six_distinct():
    origin = Hex(0, 0)
    neighbors = hex_neighbors(origin)
    assert len(neighbors) == 6
    assert len(set(neighbors)) == 6
    for n in neighbors:
        assert hex_distance(origin, n) == 1


def test_hex_distance_origin_to_self_is_zero():
    assert hex_distance(Hex(0, 0), Hex(0, 0)) == 0


def test_hex_distance_axial_cases():
    assert hex_distance(Hex(0, 0), Hex(3, 0)) == 3
    assert hex_distance(Hex(0, 0), Hex(-2, 2)) == 2
    assert hex_distance(Hex(1, -3), Hex(-1, 2)) == 5


def test_hex_range_radius_zero_returns_single_tile():
    tiles = hex_range(Hex(0, 0), 0)
    assert tiles == [Hex(0, 0)]


def test_hex_range_radius_one_returns_seven_tiles():
    tiles = hex_range(Hex(0, 0), 1)
    assert len(tiles) == 7
    assert Hex(0, 0) in tiles


def test_hex_range_radius_two_returns_nineteen_tiles():
    tiles = hex_range(Hex(5, -2), 2)
    # 1 + 6 + 12 = 19
    assert len(tiles) == 19
    assert all(hex_distance(Hex(5, -2), t) <= 2 for t in tiles)
