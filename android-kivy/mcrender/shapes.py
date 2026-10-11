"""Built-in shapes for vanilla blocks that have no model file.

Bedrock keeps the geometry of slabs, stairs, torches, flowers, fences, ... inside
the game, so an add-on has nothing to read.  This module re-creates the common ones
as tiny Bedrock geometries, which the normal geometry renderer then rasterises.

Every cube is given in **block units** (16 = one block, x/z centred on the block,
y measured from the block's bottom) and every face carries an explicit UV rect in
a 16x16 texture, which is what a vanilla block texture looks like.
"""
from __future__ import annotations

from .geometry import GeoBone, GeoCube, Geometry

R = tuple  # a UV rect: (u0, v0, u1, v1)


def box(x0, y0, z0, x1, y1, z1, *, all=None, sides=None, up=None, down=None,
        north=None, south=None, east=None, west=None, rot=None, pivot=None) -> dict:
    """One box, with UV rects per face (defaults: ``sides`` for the four sides)."""
    faces = {}
    for name, rect in (("north", north), ("south", south), ("east", east), ("west", west),
                       ("up", up), ("down", down)):
        rect = rect or sides or all
        if rect:
            faces[name] = rect
    if all and not faces:
        faces = {f: all for f in ("north", "south", "east", "west", "up", "down")}
    return {"origin": (x0, y0, z0), "size": (x1 - x0, y1 - y0, z1 - z0),
            "faces": faces, "rotation": rot or (0, 0, 0), "pivot": pivot or (0, 0, 0)}


FULL = (0, 0, 16, 16)

# ---------------------------------------------------------------- shape table
SHAPES = {
    # --- blocks that are cut down -------------------------------------------
    "slab": [box(-8, 0, -8, 8, 8, 8, sides=(0, 8, 16, 16), up=FULL, down=FULL)],
    "slab_top": [box(-8, 8, -8, 8, 16, 8, sides=(0, 0, 16, 8), up=FULL, down=FULL)],
    "stairs": [
        box(-8, 0, -8, 8, 8, 8, sides=(0, 8, 16, 16), up=FULL, down=FULL),
        box(-8, 8, 0, 8, 16, 8, sides=(0, 0, 16, 8), up=FULL, down=(0, 8, 16, 8),
            north=(0, 8, 16, 16)),
    ],
    "carpet": [box(-8, 0, -8, 8, 1, 8, sides=(0, 15, 16, 16), up=FULL, down=FULL)],
    "pressure_plate": [box(-8, 0, -8, 8, 1, 8, sides=(0, 15, 16, 16), up=FULL, down=FULL)],
    "snow_layer": [box(-8, 0, -8, 8, 2, 8, sides=(0, 14, 16, 16), up=FULL, down=FULL)],
    "lily_pad": [box(-8, 0, -8, 8, 1, 8, sides=(0, 15, 16, 16), up=FULL, down=FULL)],
    "trapdoor": [box(-8, 0, -8, 8, 3, 8, up=FULL, down=FULL, sides=(0, 13, 16, 16))],

    # --- plants / flowers: two crossed planes -------------------------------
    "cross": [
        box(-8, 0, 0, 8, 16, 0, north=FULL, south=FULL, rot=(0, 45, 0), pivot=(0, 8, 0)),
        box(-8, 0, 0, 8, 16, 0, north=FULL, south=FULL, rot=(0, -45, 0), pivot=(0, 8, 0)),
    ],

    # --- light sources -------------------------------------------------------
    "torch": [box(-1, 0, -1, 1, 10, 1, sides=(7, 6, 9, 16), up=(7, 6, 9, 8), down=(7, 13, 9, 15))],
    "wall_torch": [box(-1, 3, -1, 1, 13, 1, sides=(7, 6, 9, 16), up=(7, 6, 9, 8),
                       down=(7, 13, 9, 15), rot=(-22.5, 0, 0), pivot=(0, 3, 0))],
    "lantern": [
        box(-3, 0, -3, 3, 1, 3, all=FULL),
        box(-2, 1, -2, 2, 6, 2, sides=(5, 3, 11, 8), up=(5, 3, 11, 8), down=(5, 3, 11, 8)),
        box(-3, 6, -3, 3, 7, 3, all=FULL),
    ],
    "chain": [box(-2, 0, -2, 2, 16, 2, sides=(6, 0, 10, 16), up=FULL, down=FULL)],
    "end_rod": [box(-1, 0, -1, 1, 11, 1, sides=(7, 5, 9, 16), up=(7, 5, 9, 7), down=(7, 13, 9, 15))],
    "lightning_rod": [box(-1, 0, -1, 1, 16, 1, sides=(7, 0, 9, 16), up=(7, 0, 9, 2), down=FULL)],
    "campfire": [
        box(-8, 0, -8, 8, 4, 8, sides=(0, 12, 16, 16), up=FULL, down=FULL),
        box(-6, 4, -1, 6, 6, 1, all=(0, 0, 12, 2)),
        box(-1, 4, -6, 1, 6, 6, all=(0, 0, 2, 12)),
    ],

    # --- fences / walls / panes ---------------------------------------------
    "fence": [
        box(-2, 0, -2, 2, 16, 2, sides=(6, 0, 10, 16), up=(6, 0, 10, 4)),
        box(-8, 6, -1, 8, 9, 1, sides=(0, 6, 16, 9)),
        box(-8, 12, -1, 8, 15, 1, sides=(0, 12, 16, 15)),
    ],
    "fence_gate": [
        box(-2, 0, -2, 2, 16, 2, sides=(6, 0, 10, 16), up=(6, 0, 10, 4)),
        box(2, 6, -1, 8, 9, 1, sides=(0, 6, 6, 9)),
        box(2, 12, -1, 8, 15, 1, sides=(0, 12, 6, 15)),
    ],
    "wall": [
        box(-4, 0, -4, 4, 16, 4, sides=(4, 0, 12, 16), up=(4, 0, 12, 8)),
        box(-8, 10, -3, -4, 16, 3, sides=(4, 6, 8, 12)),
        box(4, 10, -3, 8, 16, 3, sides=(4, 6, 8, 12)),
    ],
    "pane": [box(-8, 0, -1, 8, 16, 1, north=FULL, south=FULL, sides=(0, 0, 2, 16),
                 up=(0, 0, 16, 2), down=(0, 0, 16, 2))],
    "bars": [box(-8, 0, -1, 8, 16, 1, north=FULL, south=FULL, sides=(0, 0, 2, 16))],

    # --- doors / signs / ladders --------------------------------------------
    "door": [box(-8, 0, -8, 8, 16, -5, north=FULL, south=FULL, sides=(0, 0, 3, 16),
                 up=(0, 0, 16, 3), down=(0, 0, 16, 3))],
    "sign": [
        box(-1, 0, -1, 1, 9, 1, sides=(7, 0, 9, 16), up=FULL, down=FULL),
        box(-8, 9, -1, 8, 15, 1, north=FULL, south=FULL, sides=(0, 0, 2, 6),
            up=(0, 0, 16, 2), down=(0, 0, 16, 2)),
    ],
    "ladder": [box(-8, 0, -1, 8, 16, 0, north=FULL, south=FULL)],
    "banner": [box(-8, 0, -1, 8, 16, 1, north=FULL, south=FULL, sides=(0, 0, 2, 16),
                   up=(0, 0, 16, 2), down=(0, 0, 16, 2))],
    "scaffolding": [
        box(-8, 0, -8, -6, 16, -6, all=(0, 0, 2, 16)),
        box(6, 0, -8, 8, 16, -6, all=(14, 0, 16, 16)),
        box(-8, 0, 6, -6, 16, 8, all=(0, 0, 2, 16)),
        box(6, 0, 6, 8, 16, 8, all=(14, 0, 16, 16)),
        box(-8, 14, -8, 8, 16, 8, up=FULL, down=FULL, sides=(0, 14, 16, 16)),
    ],

    # --- small props ---------------------------------------------------------
    "button": [box(-3, 0, -2, 3, 2, 2, sides=(5, 14, 11, 16), up=(5, 14, 11, 16))],
    "lever": [
        box(-3, 0, -3, 3, 3, 3, sides=(5, 13, 11, 16), up=(5, 13, 11, 16)),
        box(-1, 3, -1, 1, 8, 1, sides=(7, 8, 9, 13), up=(7, 8, 9, 10)),
    ],
    "flower_pot": [
        box(-3, 0, -3, 3, 1, 3, all=FULL),
        box(-3, 1, -3, 3, 4, -2, sides=(5, 12, 11, 15), up=(5, 12, 11, 13)),
        box(-3, 1, 2, 3, 4, 3, sides=(5, 12, 11, 15), up=(5, 12, 11, 13)),
        box(2, 1, -2, 3, 4, 2, sides=(13, 12, 15, 15), up=(13, 12, 15, 14)),
        box(-3, 1, -2, -2, 4, 2, sides=(1, 12, 3, 15), up=(1, 12, 3, 14)),
    ],
    "rail": [box(-8, 0, -8, 8, 1, 8, up=FULL, down=FULL, sides=(0, 15, 16, 16))],
    "anvil": [
        box(-6, 0, -7, 6, 4, 7, all=FULL),
        box(-4, 4, -5, 4, 6, 5, all=(4, 4, 12, 10)),
        box(-7, 6, -8, 7, 10, 8, all=(0, 0, 16, 8)),
    ],
    "cake": [box(-7, 0, -7, 7, 8, 7, all=(1, 8, 15, 16))],
    "chest": [box(-7, 0, -7, 7, 14, 7, all=(1, 1, 15, 15))],
    "hopper": [
        box(-8, 6, -8, 8, 10, 8, sides=(0, 4, 16, 8), up=FULL, down=FULL),
        box(-4, 0, -4, 4, 6, 4, sides=(4, 0, 12, 8)),
    ],
    "cauldron": [
        box(-8, 0, -8, 8, 2, 8, all=(1, 14, 15, 16)),
        box(-8, 2, -8, -6, 16, 8, all=(0, 0, 3, 14)),
        box(6, 2, -8, 8, 16, 8, all=(0, 0, 3, 14)),
        box(-6, 2, -8, 6, 16, -6, all=(0, 0, 16, 14)),
        box(-6, 2, 6, 6, 16, 8, all=(0, 0, 16, 14)),
    ],
    "composter": [
        box(-8, 0, -8, 8, 2, 8, all=(0, 14, 16, 16)),
        box(-8, 2, -8, -6, 16, 8, all=(0, 0, 2, 16)),
        box(6, 2, -8, 8, 16, 8, all=(14, 0, 16, 16)),
        box(-6, 2, -8, 6, 16, -6, all=(0, 0, 12, 16)),
        box(-6, 2, 6, 6, 16, 8, all=(0, 0, 12, 16)),
    ],
    "brewing_stand": [
        box(-7, 0, -7, 7, 2, 7, all=(0, 12, 16, 16)),
        box(-1, 2, -1, 1, 12, 1, sides=(7, 4, 9, 14), up=(7, 4, 9, 6)),
        box(-4, 12, -4, 4, 14, 4, all=(4, 4, 12, 6)),
    ],
    "stonecutter": [
        box(-8, 0, -8, 8, 9, 8, all=(0, 7, 16, 16)),
        box(-4, 9, -1, 4, 16, 1, all=(4, 0, 12, 7)),
    ],
    "grindstone": [
        box(-4, 0, -6, 4, 4, 6, all=(4, 12, 12, 16)),
        box(-6, 4, -4, 6, 12, 4, all=(0, 4, 12, 12)),
    ],
    "lectern": [
        box(-8, 0, -8, 8, 13, 8, all=(0, 3, 16, 16)),
        box(-8, 13, -8, 8, 15, 8, up=FULL, down=FULL, sides=(0, 14, 16, 16)),
        box(-7, 15, 2, 7, 17, 7, all=(0, 0, 14, 8), rot=(-22.5, 0, 0), pivot=(0, 15, 2)),
    ],
    "bell": [
        box(-6, 4, -6, 6, 5, 6, all=(2, 11, 14, 12)),
        box(-4, 0, -4, 4, 4, 4, all=(4, 12, 12, 16)),
    ],
    "skull": [box(-4, 0, -4, 4, 8, 4, all=(0, 0, 8, 8))],
    "cactus": [box(-7, 0, -7, 7, 16, 7, sides=(0, 0, 15, 16), up=(0, 0, 15, 15),
                   down=(0, 0, 15, 15))],
    "bed": [
        box(-8, 3, -8, 8, 9, 8, up=(0, 0, 16, 16), sides=(0, 0, 16, 6)),
        box(-8, 0, -8, -6, 3, -6, all=(0, 0, 2, 3)),
        box(6, 0, -8, 8, 3, -6, all=(0, 0, 2, 3)),
        box(-8, 0, 6, -6, 3, 8, all=(0, 0, 2, 3)),
        box(6, 0, 6, 8, 3, 8, all=(0, 0, 2, 3)),
    ],
    "bamboo": [box(-1, 0, -1, 1, 16, 1, sides=(7, 0, 9, 16), up=(7, 0, 9, 9))],
    "cocoa": [box(-2, 2, -4, 2, 10, 4, all=(4, 4, 12, 12))],

    # --- redstone / mechanical ---------------------------------------------
    "shelf": [
        box(-8, 2, -8, 8, 5, -6, all=(0, 0, 16, 3)),
        box(-8, 2, 6, 8, 5, 8, all=(0, 0, 16, 3)),
        box(-8, 11, -8, 8, 14, -6, all=(0, 0, 16, 3)),
        box(-8, 11, 6, 8, 14, 8, all=(0, 0, 16, 3)),
        box(-8, 0, -8, -6, 16, 8, all=(0, 0, 2, 16)),
        box(6, 0, -8, 8, 16, 8, all=(14, 0, 16, 16)),
    ],
    "repeater": [
        box(-8, 0, -8, 8, 2, 8, all=FULL),
        box(-1, 1, -5, 1, 5, 5, sides=(7, 11, 9, 15), up=(7, 11, 9, 13)),
    ],
    "comparator": [
        box(-8, 0, -8, 8, 2, 8, all=FULL),
        box(-4, 1, -6, -2, 4, -4, all=(2, 12, 4, 15)),
        box(2, 1, -6, 4, 4, -4, all=(12, 12, 14, 15)),
        box(-1, 1, 2, 1, 4, 6, sides=(7, 12, 9, 15)),
    ],
    "redstone_wire": [box(-8, 0, -8, 8, 1, 8, up=FULL, down=FULL, sides=(0, 15, 16, 16))],
    "tripwire": [box(-8, 0, -8, 8, 1, 8, up=FULL, down=FULL, sides=(0, 15, 16, 16))],
    "tripwire_hook": [
        box(-1, 0, -3, 1, 3, 1, all=(7, 13, 9, 16)),
        box(-1, 3, -1, 1, 9, 1, sides=(7, 7, 9, 13), up=(7, 7, 9, 9)),
    ],
    "piston": [
        box(-8, 0, -8, 8, 4, 8, all=(0, 12, 16, 16)),
        box(-6, 4, -6, 6, 16, 6, all=(0, 0, 12, 12)),
    ],

    # --- odd blocks ---------------------------------------------------------
    "dragon_egg": [box(-6, 0, -6, 6, 16, 6, sides=(2, 0, 14, 16), up=(2, 0, 14, 12),
                       down=(2, 4, 14, 16))],
    "turtle_egg": [box(-3, 0, -3, 3, 4, 3, all=FULL)],
    "beacon": [
        box(-8, 0, -8, 8, 3, 8, all=(0, 13, 16, 16)),
        box(-3, 3, -3, 3, 10, 3, sides=(5, 6, 11, 13), up=(5, 6, 11, 8)),
    ],
    "big_dripleaf": [
        box(-1, 0, -1, 1, 12, 1, sides=(7, 4, 9, 16)),
        box(-8, 12, -8, 8, 15, 8, up=FULL, down=FULL, sides=(0, 13, 16, 16)),
    ],
    "big_dripleaf_stem": [box(-1, 0, -1, 1, 16, 1, sides=(7, 0, 9, 16))],
    "coral_fan": [
        box(-8, 0, 0, 8, 16, 0, north=FULL, south=FULL, rot=(0, 45, 0), pivot=(0, 8, 0)),
        box(-8, 0, 0, 8, 16, 0, north=FULL, south=FULL, rot=(0, -45, 0), pivot=(0, 8, 0)),
    ],
    "bamboo_sapling": [box(-1, 0, -1, 1, 12, 1, sides=(7, 0, 9, 12), up=(7, 0, 9, 9))],
    "chorus_plant": [
        box(-3, 0, -3, 3, 16, 3, sides=(5, 0, 11, 16), up=(5, 0, 11, 8)),
        box(-8, 6, -2, -3, 10, 2, sides=(5, 6, 10, 10)),
        box(3, 6, -2, 8, 10, 2, sides=(5, 6, 10, 10)),
    ],
    "chorus_flower": [box(-8, 0, -8, 8, 16, 8, sides=FULL, up=FULL, down=FULL)],
}

# ------------------------------------------------------------- name mapping
SUFFIX_RULES = [
    ("_slab", "slab"), ("_stairs", "stairs"), ("_carpet", "carpet"),
    ("_pressure_plate", "pressure_plate"), ("_trapdoor", "trapdoor"),
    ("_fence_gate", "fence_gate"), ("_fence", "fence"), ("_wall", "wall"),
    ("_pane", "pane"), ("_bars", "bars"), ("_door", "door"), ("_shelf", "shelf"),
    ("_coral_fan", "coral_fan"), ("_coral", "cross"),
    ("_hanging_sign", "sign"), ("_wall_sign", "sign"), ("_sign", "sign"),
    ("_banner", "banner"), ("_button", "button"), ("_lever", "lever"),
    ("_rail", "rail"), ("_rod", "end_rod"), ("_bed", "bed"),
    ("_head", "skull"), ("_skull", "skull"), ("_torch", "torch"),
]

# plants that the vanilla game renders as two crossed planes
CROSS_PLANTS = {
    "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip",
    "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose",
    "sunflower", "lilac", "rose_bush", "peony", "torchflower", "pitcher_plant", "pink_petals",
    "yellow_flower", "red_flower", "double_plant", "grass", "tallgrass", "fern", "large_fern",
    "deadbush", "dead_bush", "sapling", "oak_sapling", "spruce_sapling", "birch_sapling",
    "jungle_sapling", "acacia_sapling", "dark_oak_sapling", "mangrove_propagule", "cherry_sapling",
    "pale_oak_sapling", "brown_mushroom", "red_mushroom", "crimson_fungus", "warped_fungus",
    "crimson_roots", "warped_roots", "nether_sprouts", "wheat", "carrots", "potatoes", "beetroot",
    "sweet_berry_bush", "nether_wart", "kelp", "seagrass", "vine", "weeping_vines", "twisting_vines",
    "glow_lichen", "sculk_vein", "spore_blossom", "chorus_flower", "sea_pickle", "big_dripleaf",
    "small_dripleaf", "azalea", "flowering_azalea", "hanging_roots", "frogspawn",
}

# a few blocks whose name does not follow a suffix rule
EXACT = {
    "torch": "torch", "soul_torch": "torch", "redstone_torch": "torch",
    "unlit_redstone_torch": "torch", "wall_torch": "wall_torch", "soul_wall_torch": "wall_torch",
    "rail": "rail", "golden_rail": "rail", "detector_rail": "rail", "activator_rail": "rail",
    "lantern": "lantern", "soul_lantern": "lantern", "chain": "chain", "end_rod": "end_rod",
    "lightning_rod": "lightning_rod", "campfire": "campfire", "soul_campfire": "campfire",
    "flower_pot": "flower_pot", "anvil": "anvil", "chipped_anvil": "anvil",
    "damaged_anvil": "anvil", "cake": "cake", "chest": "chest", "trapped_chest": "chest",
    "ender_chest": "chest", "hopper": "hopper", "cauldron": "cauldron",
    "water_cauldron": "cauldron", "lava_cauldron": "cauldron", "powder_snow_cauldron": "cauldron",
    "composter": "composter", "brewing_stand": "brewing_stand", "stonecutter": "stonecutter",
    "stonecutter_block": "stonecutter", "grindstone": "grindstone", "lectern": "lectern",
    "bell": "bell", "lily_pad": "lily_pad", "waterlily": "lily_pad", "snow_layer": "snow_layer",
    "cactus": "cactus", "bamboo": "bamboo", "scaffolding": "scaffolding", "ladder": "ladder",
    "iron_bars": "bars", "cobweb": "cross", "web": "cross", "tall_grass": "cross",
    "repeater": "repeater", "powered_repeater": "repeater", "unpowered_repeater": "repeater",
    "comparator": "comparator", "powered_comparator": "comparator",
    "unpowered_comparator": "comparator", "redstone_wire": "redstone_wire",
    "redstone_dust": "redstone_wire", "tripwire": "tripwire", "tripwire_hook": "tripwire_hook",
    "piston": "piston", "sticky_piston": "sticky_piston", "dragon_egg": "dragon_egg",
    "turtle_egg": "turtle_egg", "beacon": "beacon", "big_dripleaf": "big_dripleaf",
    "big_dripleaf_stem": "big_dripleaf_stem", "coral_fan": "coral_fan",
    "bamboo_sapling": "bamboo_sapling", "chorus_plant": "chorus_plant",
    "chorus_flower": "chorus_flower", "cactus_flower": "cactus_flower",
    "large_amethyst_bud": "cross", "medium_amethyst_bud": "cross", "small_amethyst_bud": "cross",
    "amethyst_cluster": "cross", "candle": "button",
}

# top slabs and specific rotations we cannot guess from the name alone
TOP_SLABS = {"smooth_stone_slab", "stone_slab", "sandstone_slab", "petrified_oak_slab",
             "cobblestone_slab", "brick_slab", "stone_brick_slab", "nether_brick_slab",
             "quartz_slab", "red_sandstone_slab", "purpur_slab", "smooth_sandstone_slab",
             "smooth_quartz_slab", "smooth_red_sandstone_slab", "cut_sandstone_slab",
             "cut_red_sandstone_slab", "blackstone_slab", "polished_blackstone_slab"}


def dried_ghast(images: dict):
    """The dried ghast: a squat body plus the tentacles it hangs by.

    Bedrock draws this one with a hard-coded model built from six block faces and a
    separate tentacle texture, so the cubes carry their own images.
    """
    body = {face: images.get(face) for face in ("north", "south", "east", "west")}
    body["up"] = images.get("up")
    body["down"] = images.get("down")
    side = images.get("side") or images.get("north")
    faces = {face: img for face, img in body.items() if img is not None}
    if not faces:
        return None
    tentacle = images.get("tentacles") or side
    bone = GeoBone(name="dried_ghast", pivot=(0, 0, 0), rotation=(0, 0, 0))
    bone.cubes.append(GeoCube(origin=(-5, 6, -5), size=(10, 10, 10),
                              uv={f: (0, 0, 16, 16) for f in faces}, textures=faces))
    if tentacle is not None:
        for tx, tz in ((-4, -4), (1, -4), (-4, 1), (1, 1)):
            bone.cubes.append(GeoCube(
                origin=(tx, 0, tz), size=(3, 6, 3),
                uv={f: (0, 0, 16, 16) for f in ("north", "south", "east", "west", "up", "down")},
                textures={"*": tentacle}))
    geo = Geometry(identifier="builtin.dried_ghast", texture_width=16, texture_height=16,
                   bones=[bone])
    geo.resolve()
    return geo


def shape_name(name: str) -> str | None:
    """Block short name -> built-in shape name (or None)."""
    if name in EXACT:
        return EXACT[name]
    if name in CROSS_PLANTS:
        return "cross"
    for suffix, shape in SUFFIX_RULES:
        if name.endswith(suffix):
            return shape
    if name.endswith("_slab") or name in TOP_SLABS:
        return "slab"
    return None


def build_geometry(name: str, texture_keys, texture_width: int = 16,
                   texture_height: int = 16) -> Geometry | None:
    """Turn a built-in shape into a Geometry the renderer can rasterise."""
    cubes = SHAPES.get(name)
    if not cubes:
        return None
    bone = GeoBone(name="shape", pivot=(0, 0, 0), rotation=(0, 0, 0))
    for spec in cubes:
        bone.cubes.append(GeoCube(
            origin=spec["origin"], size=spec["size"], uv=dict(spec["faces"]),
            pivot=spec.get("pivot", (0, 0, 0)), rotation=spec.get("rotation", (0, 0, 0)),
        ))
    geo = Geometry(identifier=f"builtin.{name}", texture_width=texture_width,
                   texture_height=texture_height, bones=[bone])
    geo.resolve()
    return geo
