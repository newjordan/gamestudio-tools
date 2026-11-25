import csv, json
import wfc_tiles, dungeon_gen


EXAMPLE = [
    "W,W,W,W,W,W",
    "W,G,G,G,G,W",
    "W,G,S,S,G,W",
    "W,G,S,S,G,W",
    "W,G,G,G,G,W",
    "W,W,W,W,W,W",
]


def test_wfc_respects_rules(tmp_path):
    ex = tmp_path / "ex.csv"; ex.write_text("\n".join(EXAMPLE))
    grid, _ = wfc_tiles.read_example(str(ex))
    tiles, weights, rules = wfc_tiles.learn(grid)
    out = wfc_tiles.generate(tiles, weights, rules, 20, 12, seed=4)
    assert len(out) == 12 and len(out[0]) == 20
    assert wfc_tiles.valid(out, rules)
    # S never touches W in example; must not in output
    for y in range(12):
        for x in range(19):
            assert {out[y][x], out[y][x + 1]} != {"S", "W"}
    o = tmp_path / "o.json"
    wfc_tiles.main([str(ex), "-o", str(o), "--size", "16x9", "--seed", "1"])
    m = json.load(open(o))
    assert len(m["layers"][0]["data"]) == 16 * 9


def test_dungeon_bsp_connected(tmp_path):
    for seed in range(5):
        g, rooms = dungeon_gen.bsp(64, 40, seed)
        assert len(rooms) >= 4
        assert len(dungeon_gen.regions(g)) == 1
        assert all(c == dungeon_gen.WALL for c in g[0]) and all(row[0] == dungeon_gen.WALL for row in g)


def test_dungeon_caves_and_export(tmp_path):
    g, _ = dungeon_gen.caves(60, 40, seed=2)
    assert len(dungeon_gen.regions(g)) == 1
    floor = sum(c == dungeon_gen.FLOOR for row in g for c in row)
    assert floor > 200
    out = str(tmp_path / "d")
    dungeon_gen.main(["--mode", "bsp", "--seed", "9", "-o", out, "--size", "48x32"])
    m = json.load(open(out + ".json"))
    assert m["width"] == 48 and set(m["layers"][0]["data"]) <= {1, 2}
    assert len(open(out + ".txt").read().splitlines()) == 32
