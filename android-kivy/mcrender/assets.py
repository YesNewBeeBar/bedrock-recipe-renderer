"""Texture / identifier resolution across a behaviour pack, a resource pack and
the vanilla (sample) resource pack."""
from __future__ import annotations

import glob
import os
import re
import sys
from dataclasses import dataclass, field

from PIL import Image

from . import jsonc
from . import shapes
from . import wiki
from .geometry import load_geometries
from .icon import Icon, missing_texture
from .vanilla import VanillaSource

# Blocks that are not full cubes: rendered as flat sprites (like the vanilla
# inventory does for cross models).  Anything not listed is rendered as a cube.
FLAT_BLOCKS = {
    # flowers / plants
    "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip",
    "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose",
    "sunflower", "lilac", "rose_bush", "peony", "torchflower", "pitcher_plant", "pitcher_crop",
    "sapling", "oak_sapling", "spruce_sapling", "birch_sapling", "jungle_sapling", "acacia_sapling",
    "dark_oak_sapling", "mangrove_propagule", "cherry_sapling", "bamboo", "bamboo_sapling",
    "grass", "tallgrass", "fern", "large_fern", "double_plant", "yellow_flower", "red_flower",
    "deadbush", "dead_bush", "cactus_flower", "vine", "weeping_vines", "twisting_vines", "kelp",
    "seagrass", "sweet_berry_bush", "cave_vines", "cave_vines_body_with_berries",
    "cave_vines_head_with_berries", "glow_lichen", "wheat", "carrots", "potatoes", "beetroot",
    "pumpkin_stem", "melon_stem", "brown_mushroom", "red_mushroom", "crimson_fungus",
    "warped_fungus", "crimson_roots", "warped_roots", "nether_sprouts", "spore_blossom",
    "chorus_flower", "chorus_plant", "big_dripleaf", "small_dripleaf", "azalea", "flowering_azalea",
    "moss_carpet", "hanging_roots", "sea_pickle", "lily_pad", "waterlily", "nether_wart",
    "sculk_vein", "frogspawn", "torchflower_crop",
    # rails / redstone bits / thin things
    "rail", "golden_rail", "detector_rail", "activator_rail", "redstone_torch", "unlit_redstone_torch",
    "redstone_wire", "torch", "soul_torch", "lantern", "soul_lantern", "chain", "end_rod",
    "lightning_rod", "lever", "tripwire", "trip_wire", "tripwire_hook", "flower_pot", "candle",
    "white_candle", "red_candle", "cake", "brewing_stand", "cauldron", "campfire", "soul_campfire",
    "composter", "fire", "soul_fire", "cobweb", "web", "ladder", "scaffolding", "grindstone",
    "stonecutter", "stonecutter_block", "lectern", "bell", "conduit", "hopper", "chest", "barrel",
    "trapped_chest", "ender_chest", "shulker_box", "undyed_shulker_box", "bed", "banner", "skull",
    "head", "player_head", "sign", "standing_sign", "wall_sign", "hanging_sign", "wall_banner",
    "item_frame", "glow_item_frame", "painting", "armor_stand", "frame",
}


# Bedrock item ids whose vanilla texture key / file name differs from the id.
TEXTURE_ALIASES = {
    "netherstar": "nether_star",
    "cooked_beef": "beef_cooked",
    "cooked_porkchop": "porkchop_cooked",
    "cooked_chicken": "chicken_cooked",
    "cooked_mutton": "mutton_cooked",
    "cooked_rabbit": "rabbit_cooked",
    "cooked_cod": "cooked_fish",
    "redstone": "redstone_dust",
    "book": "book_normal",
    "bone_meal": "dye_powder_white",
    "dye": "dye_powder_white",
    "slime_ball": "slimeball",
    "firework_rocket": "fireworks",
    "firework_star": "firework_charge",
    "snowball": "snowball",
    "melon_slice": "melon",
    "sugar_cane": "reeds",
    "lily_pad": "waterlily",
    "cobweb": "web",
    "cactus": "cactus_side",
    "melon_block": "melon",
    # items whose texture file does not match the id (the game ships these names)
    "bow": "bow_standby",
    "crossbow": "crossbow_standby",
    "clock": "clock_item",
    "compass": "compass_item",
    "recovery_compass": "recovery_compass_item",
    "fishing_rod": "fishing_rod_uncast",
    "carrot_on_a_stick": "carrot_on_a_stick",
    "warped_fungus_on_a_stick": "warped_fungus_on_a_stick",
    "empty_map": "map_empty",
    "map": "map_filled",
    "firework_rocket": "fireworks",
    "firework_star": "firework_charge",
    "nether_star": "nether_star",
    "slime_ball": "slimeball",
    "totem_of_undying": "totem",
    "ominous_trial_key": "trial_key_ominous",
    "trial_key": "trial_key",
    "music_disc_13": "record_13",
    "music_disc_cat": "record_cat",
    "music_disc_blocks": "record_blocks",
    "music_disc_chirp": "record_chirp",
    "music_disc_far": "record_far",
    "music_disc_mall": "record_mall",
    "music_disc_mellohi": "record_mellohi",
    "music_disc_stal": "record_stal",
    "music_disc_strad": "record_strad",
    "music_disc_ward": "record_ward",
    "music_disc_11": "record_11",
    "music_disc_wait": "record_wait",
    "music_disc_pigstep": "record_pigstep",
    "music_disc_otherside": "record_otherside",
    "music_disc_relic": "record_relic",
    "music_disc_creator": "record_creator",
    "music_disc_precipice": "record_precipice",
}

    # suffixes the game uses when the id and the texture file disagree (bow -> bow_standby)
ITEM_FILE_SUFFIXES = ("_item", "_standby", "_uncast", "_normal", "_empty", "_filled", "_0")
# more id -> texture-file naming quirks of Bedrock
MEAT_RAW = {"beef", "chicken", "porkchop", "mutton", "rabbit"}
FISH_FILES = {
    "cod": "fish_raw", "cooked_cod": "fish_cooked",
    "salmon": "fish_salmon_raw", "cooked_salmon": "fish_salmon_cooked",
    "tropical_fish": "fish_clownfish_raw", "pufferfish": "fish_pufferfish_raw",
}
EXTRA_ALIASES = {
    "lapis_lazuli": "dye_powder_blue",
    "glass_bottle": "potion_bottle_empty",
    "enchanted_golden_apple": "apple_golden",
    "fermented_spider_eye": "spider_eye_fermented",
    "turtle_scute": "turtle_shell_piece",
    "nether_brick": "netherbrick",
    "golden_carrot": "carrot_golden",
    "baked_potato": "potato_baked",
    "poisonous_potato": "potato_poisonous",
    "sweet_berries": "sweet_berries",
    "glow_berries": "glow_berries",
    "netherite_scrap": "netherite_scrap",
    "dried_kelp": "dried_kelp",
    "sea_pickle": "sea_pickle",
    "honey_bottle": "honey_bottle",
    "experience_bottle": "experience_bottle",
    "ominous_bottle": "ominous_bottle",
    "cookie": "cookie",
    "rabbit_hide": "rabbit_hide",
    "rabbit_foot": "rabbit_foot",
    "dragon_breath": "dragon_breath",
    "nausea_potion": "potion_bottle_confusion",
    "pufferfish": "fish_pufferfish_raw",
    "cooked_rabbit": "rabbit_cooked",
    "cooked_porkchop": "porkchop_cooked",
    "cooked_chicken": "chicken_cooked",
    "cooked_mutton": "mutton_cooked",
    "cooked_beef": "beef_cooked",
    "cooked_cod": "fish_cooked",
    "cooked_salmon": "fish_salmon_cooked",
}
_COLOUR_NAMES = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
                 "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")

# Legacy potion data values -> potion name (Bedrock order), used with the colour
# table below to paint the potion overlay the way the game does.
POTION_DATA = {
    0: "water", 1: "mundane", 2: "thick", 3: "awkward",
    4: "night_vision", 5: "night_vision", 6: "invisibility", 7: "invisibility",
    8: "leaping", 9: "leaping", 10: "leaping",
    11: "fire_resistance", 12: "fire_resistance",
    13: "swiftness", 14: "swiftness", 15: "swiftness",
    16: "slowness", 17: "slowness",
    18: "water_breathing", 19: "water_breathing",
    20: "healing", 21: "healing", 22: "harming", 23: "harming",
    24: "poison", 25: "poison", 26: "poison",
    27: "regeneration", 28: "regeneration", 29: "regeneration",
    30: "strength", 31: "strength", 32: "strength",
    33: "weakness", 34: "weakness", 35: "decay",
    36: "turtle_master", 37: "turtle_master", 38: "turtle_master",
    39: "slow_falling", 40: "slow_falling", 41: "slow_falling",
    42: "luck", 43: "decay",
}
POTION_COLOURS = {
    "water": (0x38, 0x5D, 0xC6), "mundane": (0x38, 0x5D, 0xC6),
    "thick": (0x38, 0x5D, 0xC6), "awkward": (0x38, 0x5D, 0xC6),
    "night_vision": (0x1F, 0x1F, 0xA1), "invisibility": (0x7F, 0x83, 0x92),
    "leaping": (0x22, 0xFF, 0x4C), "fire_resistance": (0xFF, 0x99, 0x00),
    "swiftness": (0x7C, 0xAF, 0xC6), "slowness": (0x5A, 0x6C, 0x81),
    "water_breathing": (0x98, 0xDA, 0xC0), "healing": (0xF8, 0x24, 0x23),
    "harming": (0x43, 0x0A, 0x09), "poison": (0x4E, 0x93, 0x31),
    "regeneration": (0xCD, 0x5C, 0xAB), "strength": (0x93, 0x24, 0x23),
    "weakness": (0x48, 0x4D, 0x48), "decay": (0x73, 0x61, 0x56),
    "turtle_master": (0x7A, 0xC5, 0xB4), "slow_falling": (0xF7, 0xF8, 0xD4),
    "luck": (0x33, 0x99, 0x00), "wind_charged": (0x8E, 0xC4, 0xD6),
    "weaving": (0x78, 0x6A, 0x5A), "oozing": (0x99, 0xFF, 0xA4),
    "infested": (0x8C, 0x9C, 0x60),
}
POTION_BOTTLES = {
    "potion": "potion_bottle_drinkable",
    "splash_potion": "potion_bottle_splash",
    "lingering_potion": "potion_bottle_lingering",
    "medicine": "potion_bottle_drinkable",
}
# wiki file stems for each potion, per kind; the wiki's own renders are used first
# and the composed bottle above is only the offline fallback
_POTION_TITLES = {
    "water": "Water Bottle", "mundane": "Mundane Potion", "thick": "Thick Potion",
    "awkward": "Awkward Potion", "night_vision": "Potion of Night Vision",
    "invisibility": "Potion of Invisibility", "leaping": "Potion of Leaping",
    "fire_resistance": "Potion of Fire Resistance", "swiftness": "Potion of Swiftness",
    "slowness": "Potion of Slowness", "water_breathing": "Potion of Water Breathing",
    "healing": "Potion of Healing", "harming": "Potion of Harming",
    "poison": "Potion of Poison", "regeneration": "Potion of Regeneration",
    "strength": "Potion of Strength", "weakness": "Potion of Weakness",
    "decay": "Potion of Decay", "turtle_master": "Potion of the Turtle Master",
    "slow_falling": "Potion of Slow Falling", "luck": "Potion of Luck",
    "oozing": "Potion of Oozing", "weaving": "Potion of Weaving",
    "infested": "Potion of Infestation", "wind_charged": "Potion of Wind Charging",
    "levitation": "Potion of Levitation", "freezing": "Potion of Freezing",
}
POTION_KIND_TITLE = {
    "potion": "{}",
    "splash_potion": "Splash {}",
    "lingering_potion": "Lingering {}",
}
# potion data name -> the potion whose wiki render we should use
POTION_WIKI_ALIASES = {
    "long_night_vision": "night_vision", "strong_night_vision": "night_vision",
    "long_invisibility": "invisibility", "strong_invisibility": "invisibility",
    "long_leaping": "leaping", "strong_leaping": "leaping",
    "long_fire_resistance": "fire_resistance", "long_swiftness": "swiftness",
    "strong_swiftness": "swiftness", "long_slowness": "slowness",
    "long_water_breathing": "water_breathing", "strong_healing": "healing",
    "strong_harming": "harming", "long_poison": "poison", "strong_poison": "poison",
    "long_regeneration": "regeneration", "strong_regeneration": "regeneration",
    "long_strength": "strength", "strong_strength": "strength", "long_weakness": "weakness",
    "long_turtle_master": "turtle_master", "strong_turtle_master": "turtle_master",
    "long_slow_falling": "slow_falling", "strong_slow_falling": "slow_falling",
    "long_levitation": "levitation", "strong_levitation": "levitation",
    "long_freezing": "freezing", "strong_freezing": "freezing",
}


# Blocks with a hand-written model in the game that we cannot build from data:
# their wiki inventory render is used instead of a plain cube.
WIKI_SPECIAL = {
    "chest", "trapped_chest", "ender_chest", "barrel", "decorated_pot",
    "undyed_shulker_box", "bell", "book", "conduit", "copper_golem_statue",
    "end_portal", "end_gateway", "bed", "banner", "skull", "head", "player_head",
    "standing_sign", "wall_sign", "hanging_sign", "sign", "item_frame", "glow_item_frame",
    "frame", "glow_frame", "shelf", "dried_ghast", "crafter", "chiseled_bookshelf",
    "vault", "trial_spawner", "creaking_heart", "respawn_anchor",
    # heads: the official sample pack ships no head texture at all, so the item icon
    # comes from the wiki (the game's own inventory sprite) and the built-in skull
    # model stays as the offline fallback
    "skeleton_skull", "skeleton_head", "wither_skeleton_skull", "wither_skull",
    "wither_skeleton_head", "zombie_head", "zombie_skull", "creeper_head", "creeper_skull",
    "dragon_head", "dragon_skull", "piglin_head", "piglin_skull",
    # two-block flowers: the game shows their item sprite in an inventory slot, and the
    # wiki's inventory icon is that sprite (the block model would be a grey cross)
    "sunflower", "lilac", "rose_bush", "peony", "pitcher_plant",
}

# legacy data / variation values -> concrete item name (Bedrock colour order)
_COLOURS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
            "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black")
DATA_VARIANTS = {
    "skull": {0: "skeleton_skull", 1: "wither_skeleton_skull", 2: "zombie_head",
              3: "player_head", 4: "creeper_head", 5: "dragon_head", 6: "piglin_head"},
    "wool": {i: f"{c}_wool" for i, c in enumerate(_COLOURS)},
    "carpet": {i: f"{c}_carpet" for i, c in enumerate(_COLOURS)},
    # 染料 data 值按**维基"物品数据值"表**：0 墨囊 / 1 红 / 2 绿 / 3 可可豆 / 4 青金石 /
    # … / 15 骨粉，16~19 是 *_new。注意 _COLOURS 是 1.21 新染料的顺序，不能当 legacy data 用。
    "dye": {0: "dye_powder_black", 1: "dye_powder_red", 2: "dye_powder_green",
            3: "dye_powder_brown", 4: "dye_powder_blue", 5: "dye_powder_purple",
            6: "dye_powder_cyan", 7: "dye_powder_silver", 8: "dye_powder_gray",
            9: "dye_powder_pink", 10: "dye_powder_lime", 11: "dye_powder_yellow",
            12: "dye_powder_light_blue", 13: "dye_powder_magenta",
            14: "dye_powder_orange", 15: "dye_powder_white",
            16: "dye_powder_black_new", 17: "dye_powder_brown_new",
            18: "dye_powder_blue_new", 19: "dye_powder_white_new"},
    "concrete": {i: f"{c}_concrete" for i, c in enumerate(_COLOURS)},
    "concrete_powder": {i: f"{c}_concrete_powder" for i, c in enumerate(_COLOURS)},
    "stained_glass": {i: f"{c}_stained_glass" for i, c in enumerate(_COLOURS)},
    "stained_glass_pane": {i: f"{c}_stained_glass_pane" for i, c in enumerate(_COLOURS)},
    "carpet": {i: f"{c}_carpet" for i, c in enumerate(_COLOURS)},
    "terracotta": {i: f"{c}_terracotta" for i, c in enumerate(_COLOURS)},
    "planks": {0: "oak_planks", 1: "spruce_planks", 2: "birch_planks", 3: "jungle_planks",
               4: "acacia_planks", 5: "dark_oak_planks"},
    "log": {0: "oak_log", 1: "spruce_log", 2: "birch_log", 3: "jungle_log"},
    "log2": {0: "acacia_log", 1: "dark_oak_log"},
    "sapling": {0: "oak_sapling", 1: "spruce_sapling", 2: "birch_sapling", 3: "jungle_sapling",
                4: "acacia_sapling", 5: "dark_oak_sapling"},
    "leaves": {0: "oak_leaves", 1: "spruce_leaves", 2: "birch_leaves", 3: "jungle_leaves"},
    "leaves2": {0: "acacia_leaves", 1: "dark_oak_leaves"},
    "stone": {0: "stone", 1: "granite", 2: "polished_granite", 3: "diorite",
              4: "polished_diorite", 5: "andesite", 6: "polished_andesite"},
    "dirt": {0: "dirt", 1: "coarse_dirt", 2: "podzol"},
    "sand": {0: "sand", 1: "red_sand"},
    "sandstone": {0: "sandstone", 1: "chiseled_sandstone", 2: "cut_sandstone"},
    "stonebrick": {0: "stone_bricks", 1: "mossy_stone_bricks", 2: "cracked_stone_bricks",
                   3: "chiseled_stone_bricks"},
    "monster_egg": {0: "infested_stone", 1: "infested_cobblestone", 2: "infested_stone_bricks"},
    "coral": {0: "tube_coral", 1: "brain_coral", 2: "bubble_coral", 3: "fire_coral",
              4: "horn_coral"},
}
WIKI_SUFFIXES = ("_shulker_box", "_bed", "_banner", "_sign", "_head", "_skull", "_pot",
                 "_shelf", "_frame", "_statue")
# head items named directly (instead of "skull" + data value) -> Bedrock's variant index
SKULL_BY_NAME = {
    "skeleton_skull": 0, "skeleton_head": 0, "skull": 0,
    "wither_skeleton_skull": 1, "wither_skull": 1, "wither_skeleton_head": 1,
    "zombie_head": 2, "zombie_skull": 2,
    "player_head": 3, "head": 3,
    "creeper_head": 4, "creeper_skull": 4,
    "dragon_head": 5, "dragon_skull": 5,
    "piglin_head": 6, "piglin_skull": 6,
}
WIKI_PLANTS = {
    "tallgrass", "short_grass", "grass", "fern", "large_fern", "double_plant",
    "double_plant_grass", "reeds", "sugar_cane", "vine", "weeping_vines", "twisting_vines",
    "glow_lichen", "sculk_vein", "seagrass", "kelp", "sweet_berry_bush", "cave_vines",
    "cave_vines_body_with_berries", "cave_vines_head_with_berries", "hanging_roots",
    "spore_blossom", "chorus_flower", "chorus_plant", "nether_sprouts", "crimson_roots",
    "warped_roots", "coral_fan", "coral_fan_dead", "big_dripleaf", "big_dripleaf_stem",
    "small_dripleaf", "azalea", "flowering_azalea", "moss_carpet", "deadbush", "dead_bush",
    "lily_pad", "waterlily", "pink_petals", "wheat", "carrots", "potatoes", "beetroot",
    "torchflower_crop", "pitcher_crop", "nether_wart", "cocoa", "cactus_flower",
}
for _suffix in WIKI_SUFFIXES:
    WIKI_SPECIAL.add(_suffix)          # matched by suffix below


# 染料的 data 值 → 贴图文件（Bedrock 的经典顺序，与 item_texture 列表下标无关）
DYE_BY_DATA = {
    0: "dye_powder_black",
    1: "dye_powder_red",
    2: "dye_powder_green",
    3: "dye_powder_brown",
    4: "dye_powder_blue",
    5: "dye_powder_purple",
    6: "dye_powder_cyan",
    7: "dye_powder_silver",
    8: "dye_powder_gray",
    9: "dye_powder_pink",
    10: "dye_powder_lime",
    11: "dye_powder_yellow",
    12: "dye_powder_light_blue",
    13: "dye_powder_magenta",
    14: "dye_powder_orange",
    15: "dye_powder_white",
}

# 桶的 data 值 → item_texture 里的键（顺序与列表不同，必须显式映射）
# 桶的 data 值 → 贴图文件（顺序与 item_texture 列表不同，必须显式映射）。
# 用户实测：空 0 / 奶 1 / 水 8 / 岩浆 10 / 细雪 11。
BUCKET_BY_DATA = {
    0: "bucket_empty", 1: "bucket_milk", 2: "bucket_water", 3: "bucket_cod",
    4: "bucket_salmon", 5: "bucket_tropical", 6: "bucket_pufferfish",
    7: "bucket_axolotl", 8: "bucket_water", 9: "bucket_tadpole",
    10: "bucket_lava", 11: "bucket_powder_snow",
}


def _is_wiki_block(name: str) -> bool:
    if name in WIKI_SPECIAL or name in WIKI_PLANTS:
        return True
    return any(name.endswith(suffix) for suffix in WIKI_SUFFIXES)


@dataclass
class Assets:
    bp_dir: str | None = None
    rp_dir: str | None = None
    vanilla_dir: str | None = None
    wiki_root: str | None = None          # where to cache downloaded wiki icons
    wiki_icons: str = "auto"              # auto | always | never
    wiki_language: str = "en"
    vanilla_download: bool = True         # fetch missing vanilla files from the sample repo
    local_only: bool = False              # everything is cached: never touch the network
    tool_root: str | None = None          # where the vanilla / wiki caches live
    bundle_root: str | None = None        # read-only data shipped *inside* the exe

    item_texture: dict = field(default_factory=dict)
    terrain_texture: dict = field(default_factory=dict)
    blocks: dict = field(default_factory=dict)
    bp_icons: dict = field(default_factory=dict)
    block_models: dict = field(default_factory=dict)
    geometries: dict = field(default_factory=dict)
    tag_items: dict = field(default_factory=dict)     # "namespace:tag" -> a member item id
    tag_members: dict = field(default_factory=dict)   # "namespace:tag" -> [all known members]
    kinds: dict = field(default_factory=dict)         # id -> "item" | "block"
    tag_db: dict = field(default_factory=dict)      # 标签 -> 成员（维基数据）

    def __post_init__(self):
        self.rp_roots = []
        for rp in self._as_dirs(self.rp_dir):
            self.rp_roots.append(rp)
            self.rp_roots += sorted(d for d in glob.glob(os.path.join(glob.escape(rp), "subpacks", "*"))
                                    if os.path.isdir(d))
        self.bp_dirs = self._as_dirs(self.bp_dir)
        # some add-ons ship as a *project* (BP + RP + assets/): the textures and the
        # texture indexes live in a sibling folder, so pick those roots up as well
        seeds = list(self.rp_roots) + list(self.bp_dirs)
        for extra in self._find_asset_roots(seeds):
            if extra not in self.rp_roots:
                self.rp_roots.append(extra)
        self.vanilla_root = self.vanilla_dir
        # UI sprites (arrows, flame, brewing bubbles, smithing overlays ...) and a few
        # stand-in textures ship inside the tool, so a failed download can never leave a
        # panel half-drawn.  Both the writable copy and the copy bundled in the exe are
        # searched.
        roots = [r for r in (self.tool_root, self.bundle_root) if r]
        bundled = []
        for base in roots:
            for name in ("ui", "vanilla_extra"):
                cand = os.path.join(base, "assets", name)
                if os.path.isdir(cand) and cand not in bundled:
                    bundled.append(cand)
        self.vanilla = VanillaSource(
            local_dirs=bundled + ([self.vanilla_dir] if self.vanilla_dir else []),
            zip_files=self._as_zips(self.vanilla_dir),
            cache_dir=os.path.join(self.tool_root or os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "vanilla_cache"),
            allow_download=bool(self.vanilla_download) and not self.local_only)
        self._images: dict[str, Image.Image | None] = {}
        self._tinted_cache: dict = {}
        self._colormap_cache: dict = {}
        self._potion_cache: dict = {}
        self._item_key_by_name: dict | None = None
        self.notes: list[str] = []

        # vanilla indexes: local pack → cache → official sample repo
        for rel, target in (("textures/item_texture.json", self.item_texture),
                            ("textures/terrain_texture.json", self.terrain_texture)):
            data = self.vanilla.read_json(rel)
            if isinstance(data, dict):
                target.update(data.get("texture_data", {}))
        blocks_json = self.vanilla.read_json("blocks.json")
        if isinstance(blocks_json, dict):
            self.blocks.update({k: v for k, v in blocks_json.items() if k != "format_version"})
        # then the packs the user pointed at (they override vanilla).  Iterate in
        # reverse so the first root - the pack itself - wins over discovered ones.
        for layer in reversed(self.rp_roots):
            it = self._read(os.path.join(layer, "textures", "item_texture.json"))
            if it:
                self.item_texture.update(it.get("texture_data", {}))
            tt = self._read(os.path.join(layer, "textures", "terrain_texture.json"))
            if tt:
                self.terrain_texture.update(tt.get("texture_data", {}))
            bj = self._read(os.path.join(layer, "blocks.json"))
            if isinstance(bj, dict):
                bj = {k: v for k, v in bj.items() if k != "format_version"}
                self.blocks.update(bj)
        # 基岩版全部标签 → 成员（build_tag_db.py 从维基 Module:GameTag/RelOriBE 生成）
        self.tag_db: dict = {}
        for base in self.resource_roots():
            if not base:
                continue
            fp = os.path.join(base, "tags_be.json")
            if os.path.isfile(fp):
                try:
                    data = jsonc.load(fp)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    self.tag_db = data
                break
        # 原版物品/方块定义表（fetch_vanilla_kinds.py 生成，含个别手工修正）
        for base in self.resource_roots():
            if not base:
                continue
            fp = os.path.join(base, "vanilla_kinds.json")
            if os.path.isfile(fp):
                try:
                    data = jsonc.load(fp)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    self.kinds.update(data)
                break
        if self.bp_dirs:
            self._load_bp_icons()
            self._load_block_models()
            self._load_item_definitions()
        self.geometries = load_geometries(self.rp_roots)

    # ------------------------------------------------------------------ io
    @staticmethod
    def _find_asset_roots(seeds) -> list:
        """Folders next to a pack that look like a texture root (``<dir>/textures``).

        Only used for add-ons shipped as a *project* - a folder holding a behaviour
        pack, a resource pack and a shared ``assets/``.  A plain pack folder sitting
        among unrelated packs (``development_resource_packs/``) must not pull its
        neighbours in, so the shared folder has to contain both a BP-like and an
        RP-like child.
        """

        def looks_like(entries, needles):
            return any(needle in name.lower() for name in entries for needle in needles)

        found = []
        for seed in seeds:
            base = os.path.abspath(seed)
            for up in (os.path.dirname(base), os.path.dirname(os.path.dirname(base))):
                if not up or not os.path.isdir(up):
                    continue
                try:
                    entries = os.listdir(up)
                except OSError:
                    continue
                if not (looks_like(entries, ("bp", "behavior")) and
                        looks_like(entries, ("rp", "resource"))):
                    continue
                for name in entries:
                    cand = os.path.join(up, name)
                    if not os.path.isdir(cand):
                        continue
                    tex = os.path.join(cand, "textures")
                    if not os.path.isdir(tex):
                        continue
                    if not any(os.path.isfile(os.path.join(tex, f))
                               for f in ("item_texture.json", "terrain_texture.json")):
                        continue
                    if cand not in found:
                        found.append(cand)
        return found

    @staticmethod
    def _as_dirs(value) -> list:
        """Accept a folder, a list of folders, or None."""
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            return [v for v in value if v and os.path.isdir(v)]
        return [value] if os.path.isdir(value) else []

    @staticmethod
    def _as_zips(value) -> list:
        """Accept a .zip/.mcpack/.mcaddon path, a list of them, or None."""
        if not value:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        return [v for v in items if v and os.path.isfile(v)
                and v.lower().endswith((".zip", ".mcpack", ".mcaddon", ".mcworld"))]

    @staticmethod
    def _read(path):
        if not os.path.exists(path):
            return None
        try:
            return jsonc.load(path)
        except Exception:
            return None

    def _load_bp_icons(self):
        for bp in self.bp_dirs:
            for path in sorted(glob.glob(os.path.join(glob.escape(bp), "items", "**", "*.json"),
                                         recursive=True)):
                data = self._read(path)
                if not isinstance(data, dict):
                    continue
                for key, body in data.items():
                    if not key.startswith("minecraft:") or not isinstance(body, dict):
                        continue
                    desc = body.get("description", {})
                    ident = desc.get("identifier")
                    comps = body.get("components") or {}
                    icon = comps.get("minecraft:icon")
                    if isinstance(icon, dict):
                        icon = icon.get("texture")
                    if ident:
                        self.bp_icons[ident] = icon
                    if ident:
                        self.kinds[ident] = "item"
                    # item tags: remember one member per tag so a shapeless recipe
                    # written as {"tag": "..."} has something to draw
                    tags = comps.get("minecraft:tags")
                    if ident and isinstance(tags, dict):
                        for tag in (tags.get("tags") or []):
                            if isinstance(tag, str):
                                self.tag_items.setdefault(tag, ident)
                                members = self.tag_members.setdefault(tag, [])
                                if ident not in members:
                                    members.append(ident)

    def members_for_tag(self, tag: str, limit: int = 12) -> list:
        """标签的已知成员列表（用于「同标签物品轮播」的 GIF）。

        来源：① 附加包自己声明的 tag 成员（最准）② 原版代表物品
              ③ 按名字猜：minecraft:planks → item_texture 里所有 *_planks
        """
        out: list = []
        seen = set()
        # ① 维基标签库（最全，覆盖基岩版全部 116 个标签）
        for cand in (tag, tag.split(":")[-1], "minecraft:" + tag.split(":")[-1]):
            for member in (self.tag_db or {}).get(cand, []):
                if member not in seen:
                    seen.add(member)
                    out.append(member)
        if out:
            return out[:limit]
        for cand in (tag, tag.split(":")[-1] if ":" in tag else tag,
                     "minecraft:" + tag.split(":")[-1]):
            for member in self.tag_members.get(cand, []):
                if member not in seen:
                    seen.add(member)
                    out.append(member)
        from .render import TAG_ITEMS          # 延迟导入，避免循环依赖
        rep = TAG_ITEMS.get(tag) or TAG_ITEMS.get("minecraft:" + tag.split(":")[-1])
        if rep and rep not in seen:
            seen.add(rep)
            out.append(rep)
        # 名字启发：minecraft:planks → acacia_planks / birch_planks / ...
        # （方块类物品的键在 blocks.json，不在 item_texture，两边都要找）
        last = tag.split(":")[-1]
        if len(out) < 2:
            pool = list(self.item_texture) + list(self.blocks)
            for key in sorted(set(pool)):
                short = key.split(":")[-1]
                if short.endswith("_" + last) or short == last:
                    if key not in seen:
                        seen.add(key)
                        out.append(key)
        return out[:limit]

    def pinned_icon(self, name: str):
        """人工钉死的物品图标（wiki_pinned/）：优先级最高，联网抓取也覆盖不了。"""
        key = name.split(":")[-1]
        for base in self.resource_roots():
            if not base:
                continue
            for cand in (key, name.replace(":", "__")):
                fp = os.path.join(base, "wiki_pinned", f"minecraft__{cand}.png")
                if os.path.isfile(fp):
                    img = self._image(fp)
                    if img is not None:
                        return img
        return None

    def resource_roots(self) -> list:
        """查资源时要看的所有根目录。

        PyInstaller 打包后，--add-data 的内容被解压到 sys._MEIPASS ——
        之前只找 bundle_root/tool_root，导致 exe 里读不到 wiki_pinned / tags_be.json。
        """
        bases = [self.bundle_root, self.tool_root,
                 os.path.dirname(os.path.abspath(__file__)),
                 os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases += [meipass, os.path.join(meipass, "mcrender")]
        bases.append(os.getcwd())
        out = []
        for b in bases:
            if b and b not in out:
                out.append(b)
        return out

    def kind_of(self, name: str) -> str:
        """物品还是方块？附加包定义 minecraft:item / minecraft:block 优先，
        其次原版定义表，最后看贴图归属（item_texture=物品 / terrain、blocks=方块）。
        物品一律画物品图标，绝不画立方体；方块画立方体。"""
        key = name.split(":")[-1]
        # 短名兜底只在 minecraft: 命名空间（或本来就没写命名空间）时启用。
        # 自定义命名空间必须整名匹配，否则 xyby:honey_block 会被原版的
        # minecraft:honey_block 串成方块（issue #10）。
        ns = name.split(":")[0] if ":" in name else "minecraft"
        allow_short = ns == "minecraft"
        for cand in ((name, "minecraft:" + key, key) if allow_short else
                     (name, "minecraft:" + key)):
            kind = self.kinds.get(cand)
            if kind:
                return kind
        if name in self.item_texture or (allow_short and key in self.item_texture):
            return "item"
        # 自定义方块（stonecraft:lv1stone 这类）**只**登记在 terrain_texture，
        # 不认它就会被判成 item → 方块分支被跳过 → 方块贴图全丢（用户反馈的回归）。
        # 顺序：blocks.json → terrain_texture；BP 定义（self.kinds）最优先，已在上面处理。
        if (name in self.blocks
                or (allow_short and key in self.blocks)
                or name in self.terrain_texture
                or (allow_short and key in self.terrain_texture)):
            return "block"
        # 判不出来的按**物品**处理：乱画成立方体比缺图更糟（用户多次反馈过）
        return "item"

    def _load_item_definitions(self):
        """BP item definitions: ``minecraft:item`` → 记为物品。

        与 _load_block_models 对称。缺了它，自定义物品会掉到「贴图归属」判断，
        被包内 terrain_texture 的短名命中而误判成方块（issue #10）。
        """
        for bp in self.bp_dirs:
            for path in glob.glob(os.path.join(glob.escape(bp), "items", "**", "*.json"),
                                  recursive=True):
                data = self._read(path)
                if not isinstance(data, dict):
                    continue
                for key, body in data.items():
                    if not key.startswith("minecraft:item") or not isinstance(body, dict):
                        continue
                    ident = (body.get("description") or {}).get("identifier")
                    if ident:
                        self.kinds[ident] = "item"

    def _load_block_models(self):
        """BP block definitions: ``minecraft:geometry`` + ``minecraft:material_instances``."""
        for bp in self.bp_dirs:
            for path in glob.glob(os.path.join(glob.escape(bp), "blocks", "**", "*.json"), recursive=True):
                data = self._read(path)
                if not isinstance(data, dict):
                    continue
                for key, body in data.items():
                    if not key.startswith("minecraft:block") or not isinstance(body, dict):
                        continue
                    ident = (body.get("description") or {}).get("identifier")
                    if not ident:
                        continue
                    self.kinds[ident] = "block"
                    comps = body.get("components") or {}
                    geometry = comps.get("minecraft:geometry")
                    if isinstance(geometry, dict):
                        geometry = geometry.get("identifier")
                    textures = {}
                    mats = comps.get("minecraft:material_instances") or {}
                    if isinstance(mats, dict):
                        for face, spec in mats.items():
                            if isinstance(spec, dict):
                                tex = spec.get("texture")
                            else:
                                tex = spec if isinstance(spec, str) else None
                            if tex:
                                textures[face] = tex
                    self.block_models[ident] = {"geometry": geometry, "textures": textures}

    # ----------------------------------------------------------- textures
    @staticmethod
    def _key_tokens(text: str) -> set:
        """把 id / item_texture 键拆成可比较的词元。

        lv0stone_boots        → {lv0stone, boots, lv0, stone}
        stonecraft.boots.lv0  → {stonecraft, boots, lv0}
        """
        text = text.split(":")[-1]
        out = set()
        for part in re.split(r"[^0-9A-Za-z]+", text):
            if not part:
                continue
            out.add(part.lower())
            for m in re.finditer(r"[0-9]+|[A-Za-z]+", part):
                out.add(m.group(0).lower())
        return out

    def _fuzzy_item_key(self, name: str, exclude=None) -> str | None:
        """按词元重合度，在 item_texture 里找最像这个物品 id 的键。"""
        want = self._key_tokens(name)
        if not want:
            return None
        best, best_score, best_hits = None, 0.0, 0
        for key in self.item_texture:
            if exclude and key in exclude:
                continue
            have = self._key_tokens(key)
            if not have:
                continue
            hits = len(want & have)
            if hits < 2:                      # 只重合一个词太容易误判
                continue
            # 候选词元比目标还多，说明它是个"更长的近亲"：
            # oxidized_copper → oxidized_copper_door、copper → copper_door。
            # 这类只能是误判，直接排除（issue：铜块被认成铜门）。
            if len(have) > len(want):
                continue
            score = hits / max(1, min(len(want), len(have)))
            if (score, hits) > (best_score, best_hits):
                best, best_score, best_hits = key, score, hits
        return best if best_score >= 0.6 else None

    def _flipbook_paths(self) -> set:
        """登记为动态纹理（flipbook）的贴图路径集合。

        基岩版把动画贴图竖着拼成一长条，flipbook_textures.json 里逐条登记。
        只认这份元数据、不按「高 > 宽」去猜 —— 本来就有很高的静态贴图，
        猜错会把它们裁坏（issue #10 里岩浆块被画成一整条动画帧就是这个原因）。
        """
        cached = getattr(self, "_flipbook_cache", None)
        if cached is not None:
            return cached
        found: set = set()
        roots = []
        for attr in ("rp_dirs", "bp_dirs"):
            roots += list(getattr(self, attr, []) or [])
        roots += list(getattr(self, "rp_roots", []) or [])
        vdir = getattr(self, "vanilla_dir", None)
        if vdir:
            roots.append(vdir)
        for base in roots:
            if not base:
                continue
            for rel in ("textures/flipbook_textures.json", "flipbook_textures.json"):
                fp = os.path.join(base, rel)
                if not os.path.isfile(fp):
                    continue
                try:
                    import json as _json
                    data = _json.load(open(fp, encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    tex = entry.get("flipbook_texture") or ""
                    if not tex:
                        continue
                    tex = str(tex).replace("\\", "/").lstrip("/").lower()
                    if not tex.endswith(".png"):
                        tex += ".png"
                    found.add(tex)
                    found.add(os.path.basename(tex))
        self._flipbook_cache = found
        return found

    def _image(self, path: str | None) -> Image.Image | None:
        if not path:
            return None
        if path not in self._images:
            try:
                im = Image.open(path).convert("RGBA")
                # 动态纹理（岩浆块、水、火…）是竖着拼的长条：只取第一帧，
                # 否则会把整条 16x256 当成立方体的一面（issue #10）。
                try:
                    rel = os.path.relpath(path, getattr(self, "root", "") or ".")
                except Exception:
                    rel = path
                norm = str(rel).replace("\\", "/").lstrip("./").lower()
                fb = self._flipbook_paths()
                # 动态纹理（岩浆块 16x48、水、火…）是竖着拼的长条：一律取第一帧。
                # 与 icon.py::_flat 规则一致 —— 立方体的"面"本来就该是方的，
                # 整条长条贴上去必然是错的（issue #10 的岩浆块就是这样画坏的）。
                if im.height > im.width and im.height % im.width == 0:
                    im = im.crop((0, 0, im.width, im.width))
                    im = im.crop((0, 0, im.width, im.width))
                self._images[path] = im
            except Exception:
                self._images[path] = None
        return self._images[path]

    def find_file(self, token: str | None) -> str | None:
        """Resolve 'textures/blocks/foo' (with or without extension) to a real file."""
        if not token:
            return None
        tok = str(token).replace("\\", "/")
        for ext in (".png", ".tga"):
            if tok.lower().endswith(ext):
                tok = tok[: -len(ext)]
                break
        for root in self.rp_roots:
            for ext in (".png", ".tga"):
                p = os.path.join(root, tok.replace("/", os.sep) + ext)
                if os.path.isfile(p):
                    return p
        return self.vanilla.find(tok, extensions=(".png", ".tga"))

    @staticmethod
    def _texture_by_variant(value, variant):
        """item_texture 的**列表**项要按 data 值取（Bedrock 的桶/刷怪蛋就是这样写的）。

        ``bucket`` 的列表是 [空桶, 奶桶, 水桶, 岩浆桶, …]，
        配方写 ``{"item": "minecraft:bucket", "data": 10}`` 时不能再一律取第 0 项，
        否则所有桶都画成空桶（issue #5）。
        """
        if isinstance(value, dict):
            value = value.get("textures", value)
        if isinstance(value, list):
            if variant is not None and str(variant).lstrip("-").isdigit():
                idx = int(variant)
                if 0 <= idx < len(value):
                    item = value[idx]
                    return item if isinstance(item, str) else None
                return None
            first = value[0] if value else None
            return first if isinstance(first, str) else None
        return value if isinstance(value, str) else None

    def _first_texture(self, value):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            return self._first_texture(value[0])
        if isinstance(value, dict):
            for key in ("textures", "texture", "path"):
                if key in value:
                    return self._first_texture(value[key])
        return None

    def _terrain_image(self, key: str) -> Image.Image | None:
        entry = self.terrain_texture.get(key)
        if entry is None:
            return None
        token = self._first_texture(entry)
        img = self._image(self.find_file(token))
        if img is None:
            return None
        tint = self._tint_for(key, entry, token)
        if tint and not self._looks_grayscale(img):
            # an overlay_color only tints the overlay, so a texture that is already
            # coloured (a grass block side, say) must be left alone
            if isinstance(entry, dict) and entry.get("overlay_color"):
                tint = None
        return self._tinted(img, tint, key) if tint else img

    @staticmethod
    def _looks_grayscale(img: Image.Image) -> bool:
        px = img.convert("RGBA")
        step = max(1, img.width // 16)
        for y in range(0, img.height, step):
            for x in range(0, img.width, step):
                r, g, b, a = px.getpixel((x, y))
                if a and max(r, g, b) - min(r, g, b) > 24:
                    return False
        return True

    # ------------------------------------------------------------- tinting
    def plains_colour(self, kind: str):
        """Grass / foliage colour of the plains biome, sampled from the vanilla colormap."""
        if kind in self._colormap_cache:
            return self._colormap_cache[kind]
        colour = (0x91, 0xBD, 0x59) if kind == "grass" else (0x59, 0xAE, 0x30)
        path = self.vanilla.find(f"textures/colormap/{kind}.png", extensions=(".png",))
        if path:
            try:
                im = Image.open(path).convert("RGBA")
                # plains = temperature 0.8, downfall 0.4
                colour = im.getpixel((int((1 - 0.8) * 255), int((1 - 0.4) * 255)))[:3]
            except Exception:
                pass
        self._colormap_cache[kind] = colour
        return colour

    def _tint_for(self, key: str, entry, token: str | None):
        """Colour multiplier for a texture: explicit tint_color, else the biome colormap."""
        if isinstance(entry, dict):
            for field in ("tint_color", "overlay_color"):
                value = entry.get(field)
                if isinstance(value, str) and value.startswith("#"):
                    try:
                        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
                    except ValueError:
                        pass
            for item in (entry.get("textures") or []):
                if isinstance(item, dict) and isinstance(item.get("tint_color"), str):
                    value = item["tint_color"]
                    try:
                        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
                    except ValueError:
                        pass
        blob = f"{key} {token or ''}".lower()
        if any(word in blob for word in ("grass", "fern", "reeds", "double_plant", "bush")):
            return self.plains_colour("grass")
        if any(word in blob for word in ("leaves", "vine", "lily", "foliage", "mangrove_roots")):
            return self.plains_colour("foliage")
        return None

    def _tinted(self, img: Image.Image, tint, cache_key=None) -> Image.Image:
        key = (cache_key or id(img), tuple(tint))
        if key in self._tinted_cache:
            return self._tinted_cache[key]
        out = img.copy()
        px = out.load()
        tr, tg, tb = tint
        for y in range(out.height):
            for x in range(out.width):
                r, g, b, a = px[x, y]
                px[x, y] = (r * tr // 255, g * tg // 255, b * tb // 255, a)
        self._tinted_cache[key] = out
        return out

    def _face_image(self, token: str | None) -> Image.Image | None:
        """A face token may be a terrain_texture key or a file path."""
        if not token:
            return None
        if token in self.terrain_texture:
            return self._terrain_image(token)
        return self._image(self.find_file(token))

    def _wiki_potion(self, name: str, potion: str):
        """The wiki's own potion render (``Invicon Potion of ...``), if reachable."""
        if self.wiki_icons == "never":
            return None
        if self.local_only:
            # offline: only a previously cached icon may be used
            cached = os.path.join(wiki.cache_dir(self.wiki_root or "."),
                                  f"potion_{name}_{POTION_WIKI_ALIASES.get(potion, potion)}.png")
            if not os.path.exists(cached):
                return None
        base = POTION_WIKI_ALIASES.get(potion, potion)
        title = _POTION_TITLES.get(base)
        if not title:
            return None
        pattern = POTION_KIND_TITLE.get(name, "{}")
        stem = pattern.format(title)
        cache_key = ("wiki", name, potion)
        if cache_key in self._potion_cache:
            return self._potion_cache[cache_key]
        img = None
        for suffix in ("", " Bottle"):            # e.g. "Splash Water Bottle"
            candidate = f"Invicon {stem}{suffix}.png"
            img = wiki.fetch_file(candidate, self.wiki_root or ".", self.wiki_language,
                                  cache_name=f"potion_{name}_{base}")
            if img is not None:
                break
        self._potion_cache[cache_key] = img
        return img

    def _potion_icon(self, name: str, potion: str):
        """Bottle texture + the grayscale overlay tinted with the potion's colour."""
        colour = POTION_COLOURS.get(potion)
        if colour is None:
            return None
        cache_key = ("compose", name, potion)
        if cache_key in self._potion_cache:
            return self._potion_cache[cache_key]
        bottle_key = POTION_BOTTLES[name]

        def image_for(key):
            entry = self.item_texture.get(key)
            if entry is None:
                return None
            return self._image(self.find_file(self._first_texture(entry)))

        bottle = image_for(bottle_key)
        overlay = image_for("potion_overlay")
        if bottle is None:
            self._potion_cache[cache_key] = None
            return None
        out = bottle.copy()
        if overlay is not None:
            tinted = overlay.convert("RGBA")
            px = tinted.load()
            tr, tg, tb = colour
            for y in range(tinted.height):
                for x in range(tinted.width):
                    r, g, b, a = px[x, y]
                    if a:
                        px[x, y] = (r * tr // 255, g * tg // 255, b * tb // 255, a)
            out.alpha_composite(tinted)
        self._potion_cache[cache_key] = out
        return out

    def _face_map(self, faces: dict) -> dict:
        out = {}
        if "side" in faces:
            out["*"] = faces["side"]
            for face in ("up", "down"):
                if face in faces:
                    out[face] = faces[face]
        else:
            out.update(faces)
        if not out:
            out["*"] = next(iter(faces.values()))
        # the cube renderer looks faces up by name, then "side", then "up"
        if "*" in out:
            out.setdefault("side", out["*"])
        else:
            out.setdefault("side", out.get("north") or out.get("up") or next(iter(out.values())))
        out.setdefault("up", out.get("side"))
        out.setdefault("down", out.get("down") or out.get("side"))
        return out

    # ------------------------------------------------------------ resolve
    def resolve(self, ident: str) -> Icon:
        if not ident:
            return Icon("", "missing", note="empty")
        ident = str(ident)
        variant = None
        if "#" in ident:                       # legacy data value from the recipe
            ident, _, variant = ident.partition("#")
        norm = ident if ":" in ident else "minecraft:" + ident
        ns, name = norm.split(":", 1)
        if variant and variant.lstrip("-").isdigit() and ns == "minecraft":
            mapped = DATA_VARIANTS.get(name, {}).get(int(variant))
            if mapped:
                name = mapped
                norm = f"{ns}:{mapped}"
        # head/skull items are named either "minecraft:skull" (with a data value) or by
        # the concrete head ("minecraft:wither_skull"); normalise both to a variant so
        # the built-in skull model can pick the right texture frame
        if ns == "minecraft" and name in SKULL_BY_NAME:
            variant = SKULL_BY_NAME[name]
        elif ns == "minecraft" and name == "skull" and variant is None:
            variant = 0
        if ns == "minecraft" and name in ("skull", "skeleton_skull", "skeleton_head",
                                          "wither_skeleton_skull", "wither_skull",
                                          "zombie_skull", "creeper_skull", "dragon_skull",
                                          "piglin_skull"):
            mapped = DATA_VARIANTS["skull"].get(int(variant))
            if mapped:
                name = mapped
                norm = f"{ns}:{mapped}"
        # only vanilla ids can exist in the official sample pack: a custom id that
        # has no texture locally must not turn into a dozen fruitless downloads.
        # "local_only" (set after 补全原版资源) switches the network off for good.
        if getattr(self, "vanilla", None) is not None:
            self.vanilla.allow_download = (bool(self.vanilla_download)
                                           and not self.local_only and ns == "minecraft")
        icon_key = self.bp_icons.get(ident) or self.bp_icons.get(norm)

        candidates = []
        if icon_key:
            candidates.append(icon_key)
        candidates += [f"{ns}.{name}", norm, name]
        # 兜底：有些包把 item_texture 的键拼成 "命名空间.类别.等级"（如 stonecraft.boots.lv0），
        # 而物品 id 是 lv0stone_boots —— 直接按名字查必然落空。这里按"词元"找最接近的键。
        fuzzy = self._fuzzy_item_key(name, exclude=set(candidates))
        if fuzzy and fuzzy not in candidates:
            candidates.append(fuzzy)

        # 0a. potions: the game paints the grayscale overlay over the bottle with the
        #     potion's own colour, so a legacy data value (or potion_type) must not all
        #     come out as the same blue bottle
        if ns == "minecraft" and name in POTION_BOTTLES:
            key = None
            if variant and not variant.lstrip("-").isdigit():
                key = variant.lower()                # potion_type:regeneration
            elif variant and variant.lstrip("-").isdigit():
                key = POTION_DATA.get(int(variant))
            if key:
                img = self._wiki_potion(name, key)
                if img is not None:
                    return Icon(ident, "item", item=img, note=f"wiki potion {key}")
                img = self._potion_icon(name, key)
                if img is not None:
                    return Icon(ident, "item", item=img, note=f"potion {key}")

        # 0. special renderers and biome-tinted plants: the wiki's inventory render
        #    is closer to the game than anything we can build from the add-on
        # 0. wiki inventory icon (the game's own item sprite)
        #    对**任何**物品都试一次：抓取端已经只认 "Invicon X[_BE].png"（不再回退到
        #    文章插图），所以这里拿到的要么是游戏物品栏图标，要么就是没有。
        #    离线时 offline=True → 只查本地缓存，不会联网。
        # 传【完整 id】而不是短名：短名会丢掉命名空间，自定义命名空间就被当成
        # minecraft:，短名兜底又会命中包内 terrain/blocks 的同名条目（issue #10）。
        kind = self.kind_of(norm)
        # 1b. 染料：data 值也走显式映射（不能拿列表下标当 data）
        if name in ("dye", "dye_powder") and variant is not None and str(variant).isdigit():
            fname = DYE_BY_DATA.get(int(variant))
            if fname:
                img = (self._image(self.find_file(f"textures/items/{fname}"))
                       or self._image(self.find_file(f"textures/items/{fname.replace('dye_powder', 'dye')}")))
                if img is not None:
                    return Icon(ident, "item", item=img, note=f"dye data {variant}")

        pinned = self.pinned_icon(name)
        if pinned is not None:
            return Icon(ident, "item", item=pinned, smooth=True, note="pinned icon")
        # 1c. 桶：data 值走显式映射（列表下标与 data 值并不一致）
        if name == "bucket" and variant is not None and str(variant).isdigit():
            fname = BUCKET_BY_DATA.get(int(variant))
            if fname:
                img = self._image(self.find_file(f"textures/items/{fname}"))
                if img is not None:
                    return Icon(ident, "item", item=img, note=f"bucket data {variant}")

        # 物品和方块**都先试维基物品栏图标** —— 游戏里信标在物品栏就是那张带光柱的图标，
        # 普通立方体反而不对（用户指出过）。拿不到才退回方块立方体。
        if self.wiki_icons != "never":
            if name not in self.item_texture or _is_wiki_block(name) \
                    or name in WIKI_SPECIAL or kind == "item":
                img = wiki.fetch_icon(norm, self.wiki_root or ".", self.wiki_language,
                                      offline=self.local_only)
                if img is not None:
                    return Icon(ident, "item", item=img, smooth=True, note="wiki icon")

        # 0a2. ...and those plants use that item sprite even if a shape exists
        if name in WIKI_PLANTS and name in self.item_texture:
            img = self._image(self.find_file(self._first_texture(self.item_texture[name])))
            if img is not None:
                return Icon(ident, "item", item=img, note="plant item sprite")

        # 0b. blocks with a custom geometry get a real model render
        #     **只对方块生效**：附加包里的物品 id 常常也在 blocks/ 下有几何定义
        #     （issue #10 的 更多投掷球 就是如此），若对物品也走这条分支，
        #     物品会被画成立方体 —— 用户看到的现象就是"自定义物品还是方块"。
        model = self.block_models.get(norm) or self.block_models.get(name)
        if (kind == "block" and model and model.get("geometry")
                and "full_block" not in str(model["geometry"])):
            geo = self.geometries.get(model["geometry"])
            if geo is not None:
                faces = {}
                for face, token in (model.get("textures") or {}).items():
                    img = self._face_image(token)
                    if img is not None:
                        faces[face] = img
                if "*" in faces:
                    faces = {"*": faces["*"]}
                if faces:
                    return Icon(ident, "model", faces=faces, geometry=geo,
                                note=f"geometry {model['geometry']}")

        # 0c. a plain cube whose faces are declared by the behaviour pack itself
        #     (material_instances is authoritative - it may use namespaced texture keys
        #     that never appear in the resource pack's terrain_texture.json)
        geometry = str(model.get("geometry")) if model else ""
        if model and model.get("textures") and ("full_block" in geometry or not geometry):
            faces = {}
            for face, token in model["textures"].items():
                img = self._face_image(token)
                if img is not None:
                    faces[face] = img
            if faces:
                return Icon(ident, "block", faces=self._face_map(faces),
                            note="behaviour pack material_instances")

        # 1. built-in shapes for vanilla blocks whose model lives inside the game.
        #    但**有方块贴图的**不该走这里：游戏里信标/仙人掌/TNT 在物品栏就是
        #    普通立方体，手写模型反而画得不像（用户反馈过）。
        _probe_faces = self._block_faces(
            name, self.blocks.get(norm) or self.blocks.get(name)
            or self.blocks.get(f"minecraft:{name}"))

        #    (slab / stairs / torch / flowers / fences / ...) - preferred over a flat
        #    item sprite, because the game renders the block model as the item icon
        shape = shapes.shape_name(name)
        if shape:
            block_entry = (self.blocks.get(norm) or self.blocks.get(name)
                           or self.blocks.get(f"minecraft:{name}"))
            shape_faces = self._block_faces(name, block_entry)
            if shape_faces:
                geo = shapes.build_geometry(shape, None)
                if geo is not None and kind != "item":
                    return Icon(ident, "model", faces=self._face_map(shape_faces), geometry=geo,
                                note=f"built-in shape {shape}")

        # 2. item icons (id, BP icon key, vanilla aliases, spelling variants)
        candidates += self._extra_candidates(name)
        for cand in candidates:
            for shape in (cand, f"{ns}.{cand}", f"{ns}:{cand}") if ":" not in cand else (cand,):
                if shape not in self.item_texture:
                    continue
                # 列表项按 data 值取（桶 #0 空 / #1 奶 / #3 岩浆 …）—— issue #5
                token = self._texture_by_variant(self.item_texture[shape], variant)
                if not isinstance(token, str):
                    continue
                # 有些物品在索引里指向**实体**贴图（如 shield → textures/entity/shield）——
                # 那不是物品图标，用了就会画成一整张实体贴图（issue #4）
                if "/entity/" in token.replace("\\", "/"):
                    continue
                img = self._image(self.find_file(token))
                if img is not None:
                    return Icon(ident, "item", item=img)
        # 3. block faces from blocks.json / terrain_texture
        block_entry = self.blocks.get(norm) or self.blocks.get(name) or self.blocks.get(f"minecraft:{name}")
        faces = self._block_faces(name, block_entry) if kind != "item" else {}
        if faces:
            if name == "dried_ghast":
                # offline fallback for the hand-written dried ghast model
                art = dict(faces)
                tent = self._terrain_image("dried_ghast_tentacles") or self._face_image(
                    "textures/blocks/dried_ghast_tentacles")
                if tent is not None:
                    art["tentacles"] = tent
                geo = shapes.dried_ghast(art)
                if geo is not None:
                    return Icon(ident, "model", faces=self._face_map(faces), geometry=geo,
                                note="built-in shape dried_ghast")
            flat = name in FLAT_BLOCKS
            if flat:
                img = faces.get("side") or faces.get("up") or faces.get("north")
                if img is not None:
                    return Icon(ident, "item", item=img, note="flat block sprite")
            if kind != "item":
                return Icon(ident, "block", faces=faces)
        # 3. direct files (also tried for every alias/variant spelling)
        for cand in [name] + self._extra_candidates(name):
            for sub, sub_kind in (("items", "item"), ("blocks", "block")):
                p = self.find_file(f"textures/{sub}/{cand}")
                if p:
                    img = self._image(p)
                    if img is None:
                        continue
                    if sub_kind == "item" or cand in FLAT_BLOCKS or kind == "item":
                        return Icon(ident, "item", item=img)
                    if kind == "item":
                        return Icon(ident, "item", item=img)
                    return Icon(ident, "block", faces={k: img for k in ("up", "down", "side")})
        # 4. last resort: the game sometimes suffixes an item's texture file
        #    (bow -> bow_standby, clock -> clock_item, compass -> compass_item)
        for cand in [name] + self._extra_candidates(name):
            for suffix in ITEM_FILE_SUFFIXES:
                p = self.find_file(f"textures/items/{cand}{suffix}")
                if p:
                    img = self._image(p)
                    if img is not None:
                        return Icon(ident, "item", item=img, note=f"texture {cand}{suffix}")
        # 5. 通用兜底：以上都没找到时，试一次维基库存图标。
        #    盾牌就是典型：item_texture 里只有实体贴图（已被跳过），方块表里也没有，
        #    而游戏里它的库存图标就是维基那张 32×32 的图（issue #4）。
        if self.wiki_icons != "never":
            img = wiki.fetch_icon(norm, self.wiki_root or ".", self.wiki_language,
                                  offline=self.local_only)
            if img is not None:
                return Icon(ident, "item", item=img, smooth=True, note="wiki icon")
        return Icon(ident, "missing", item=missing_texture(16), note="no texture found")

    @staticmethod
    def _extra_candidates(name: str) -> list[str]:
        """Alias + spelling variants used when the plain id lookup fails."""
        out = []
        plain = name.split(":")[-1]
        for table in (TEXTURE_ALIASES, EXTRA_ALIASES):
            alias = table.get(plain)
            if alias:
                out.append(alias)
        # Bedrock's own naming quirks
        if plain.startswith("wooden_"):
            out.append("wood_" + plain[len("wooden_"):])          # wooden_sword -> wood_sword
        if plain.startswith("golden_"):
            out.append("gold_" + plain[len("golden_"):])          # golden_helmet -> gold_helmet
        if plain.endswith("_dye") and plain[:-4] in _COLOUR_NAMES:
            out.append("dye_powder_" + plain[:-4])                # white_dye -> dye_powder_white
        if plain.endswith("_bucket"):
            out.append("bucket_" + plain[:-len("_bucket")])       # powder_snow_bucket
        if plain.endswith("_seeds"):
            out.append("seeds_" + plain[:-len("_seeds")])         # wheat_seeds -> seeds_wheat
        if plain.endswith("_sign"):
            stem = plain[:-len("_sign")]                      # oak_sign -> sign (generic)
            if stem == "oak":
                out.append("sign")
            out.append("sign_" + stem)                        # spruce_sign -> sign_spruce
            out.append("sign_" + stem.replace("_", ""))       # dark_oak_sign -> sign_darkoak
        if plain == "tropical_fish_bucket":
            out.append("bucket_tropical")
        if plain in MEAT_RAW:
            out.append(plain + "_raw")                            # beef -> beef_raw
        if plain in FISH_FILES:
            out.append(FISH_FILES[plain])
        if plain.startswith("potion") or name.startswith("potion"):
            kind = plain.split(":")[-1]
            out.append("potion_bottle_" + kind)
            out.append("potion_bottle_drinkable")
        parts = plain.split("_")
        if len(parts) == 2:
            out.append(parts[1] + "_" + parts[0])                 # cooked_beef -> beef_cooked
        out.append(plain.replace("_", ""))                        # nether_star -> netherstar
        seen, uniq = set(), []
        for c in out:
            if c and c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    def _block_faces(self, name: str, entry) -> dict[str, Image.Image]:
        faces: dict[str, Image.Image] = {}
        # face keys from blocks.json
        tex = (entry or {}).get("textures") if isinstance(entry, dict) else None
        if isinstance(tex, str):
            img = self._face_image(tex)
            if img is not None:
                faces.update({k: img for k in ("up", "down", "side")})
        elif isinstance(tex, dict):
            mapping = {
                "up": ("up", "top", "side", "all"),
                "down": ("down", "bottom", "side", "all"),
                "north": ("north", "side", "front", "all"),
                "south": ("south", "side", "all"),
                "east": ("east", "side", "all"),
                "west": ("west", "side", "all"),
            }
            for face, keys in mapping.items():
                for k in keys:
                    if k in tex:
                        img = self._face_image(tex[k] if isinstance(tex[k], str) else None)
                        if img is not None:
                            faces[face] = img
                            break
        # terrain_texture convention: <name>, <name>_up, <name>_down, <name>_side, ...
        if not faces:
            for face, suffixes in (("up", ("_up", "_top", "")), ("down", ("_down", "_bottom", "")),
                                   ("north", ("_north", "_front", "_side", "")), ("south", ("_south", "_side", "")),
                                   ("east", ("_east", "_side", "")), ("west", ("_west", "_side", ""))):
                for suf in suffixes:
                    key = name + suf if suf else name
                    img = self._terrain_image(key)
                    if img is None:
                        img = self._face_image(key)
                    if img is not None:
                        faces[face] = img
                        break
        if not faces:
            p = self.find_file(f"textures/blocks/{name}")
            img = self._image(p)
            if img is not None:
                faces.update({k: img for k in ("up", "down", "side")})
        if not faces:
            # spelling/alias variants (lily_pad -> waterlily, cobweb -> web, ...)
            for cand in self._extra_candidates(name):
                for face, suffixes in (("up", ("_up", "_top", "")), ("down", ("_down", "_bottom", "")),
                                       ("north", ("_north", "_front", "_side", "")),
                                       ("south", ("_south", "_side", "")),
                                       ("east", ("_east", "_side", "")), ("west", ("_west", "_side", ""))):
                    for suf in suffixes:
                        key = cand + suf if suf else cand
                        img = self._terrain_image(key) or self._face_image(key)
                        if img is not None:
                            faces[face] = img
                            break
                if faces:
                    break
        if faces:
            if "side" not in faces:
                faces["side"] = faces.get("north") or faces.get("up") or next(iter(faces.values()))
            for face in ("up", "down"):
                if face not in faces:
                    faces[face] = faces["side"]
        return faces
