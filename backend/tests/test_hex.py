from app.engine.hex import Hex, HEX_DIRECTIONS, hex_distance, hex_neighbors, hex_range


def test_hex_equality_and_hash():
    assert Hex(1, 2) == Hex(1, 2)
    assert hash(Hex(1, 2)) == hash(Hex(1, 2))
    assert Hex(1, 2) != Hex(2, 1)


def test_hex_addition_returns_new_hex():
    a = Hex(1, 2)
    b = Hex(3, -1)
    result = a + b
    assert result == Hex(4, 1)
    assert a == Hex(1, 2)
    assert b == Hex(3, -1)


def test_hex_directions_are_eight_unit_vectors():
    assert len(HEX_DIRECTIONS) == 8
    assert len(set(HEX_DIRECTIONS)) == 8
    for d in HEX_DIRECTIONS:
        assert hex_distance(Hex(0, 0), d) == 1


def test_hex_neighbors_returns_eight_distinct():
    origin = Hex(0, 0)
    neighbors = hex_neighbors(origin)
    assert len(neighbors) == 8
    assert len(set(neighbors)) == 8
    for n in neighbors:
        assert hex_distance(origin, n) == 1


def test_hex_distance_origin_to_self_is_zero():
    assert hex_distance(Hex(0, 0), Hex(0, 0)) == 0


def test_hex_distance_chebyshev_cases():
    assert hex_distance(Hex(0, 0), Hex(3, 0)) == 3
    assert hex_distance(Hex(0, 0), Hex(-2, 2)) == 2  # diagonal step
    assert hex_distance(Hex(1, -3), Hex(-1, 2)) == 5
    assert hex_distance(Hex(0, 0), Hex(3, 4)) == 4  # king-move distance


def test_hex_range_radius_zero_returns_single_tile():
    tiles = hex_range(Hex(0, 0), 0)
    assert tiles == [Hex(0, 0)]


def test_hex_range_radius_one_returns_nine_tiles():
    tiles = hex_range(Hex(0, 0), 1)
    assert len(tiles) == 9
    assert Hex(0, 0) in tiles


def test_hex_range_radius_two_returns_twenty_five_tiles():
    tiles = hex_range(Hex(5, -2), 2)
    # (2*2+1)^2 = 25
    assert len(tiles) == 25
    assert all(hex_distance(Hex(5, -2), t) <= 2 for t in tiles)
