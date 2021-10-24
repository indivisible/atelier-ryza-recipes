#!/usr/bin/env python3

from __future__ import annotations

from typing import Generator, Iterable, Optional, TextIO, TypeVar, Union
import typing
import xml.etree.ElementTree as ET
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from itertools import count
import string
import csv
import json

# tag lists were pulled from `strings <game exe>`

# TODO: maybe parse item potentials data?


# these affect XML parsing, thunder and air is correct here
class Element(Enum):
    FIRE = 'Fire'
    ICE = 'Ice'
    THUNDER = 'Thunder'
    AIR = 'Air'

    def __str__(self):
        return self.value


# the game uses both strings and numbers to refer to the elements...
ELEMENT_VALUES = {
    'ITEM_ELEM_FIRE': Element.FIRE,
    'ITEM_ELEM_ICE': Element.ICE,
    'ITEM_ELEM_THUNDER': Element.THUNDER,
    'ITEM_ELEM_AIR': Element.AIR,
}

ELEMENT_LOOKUP = list(Element)

ELEMENT_STR_MAP_GAME = {'ryza1': 4063340, 'ryza2': 4194395}

EFFECT_DESC_OFFSET = 3538945

RING_TYPE_OFFSETS = {
    # label and help starting offsets
    'ryza1': (10092545, 10092565),
    'ryza2': (10092545, 10092585),
}


@dataclass
class TaggedObject:
    db: Database
    idx: int
    tag: str
    name: str
    name_id: int
    description: str = ''

    def __str__(self):
        return self.name


TaggedType = TypeVar('TaggedType', bound=TaggedObject)
Ingredient = Union['Item', 'Category']


class Category(TaggedObject):
    pass


class Potential(TaggedObject):
    pass


class EVEffect(TaggedObject):
    effects: list[Effect]


@dataclass
class Effect(TaggedObject):
    type: str = 'unknown effect'
    int_value: Optional[int] = None
    category_value: Optional[str] = None
    element_value: Optional[Element] = None

    def init_effect(self, node: ET.Element):
        # effects can ACT on multiple stats
        # actTag_[0-9] tells which actions it will do, and min_ and max_ attrs
        # are the ranges for the actions
        # the whole thing looks pretty complicated for not much
        # interesting data
        for num in count():
            act = node.get(f'actTag_{num}')
            if not act:
                break
            min_1 = node.get(f'min_1_{num}')
            if act == 'ACT_MIX_ADD_CATEGORY':
                self.type = 'add_category'
                self.category_value = min_1
            elif act == 'ACT_MIX_ADD_ELEMENT':
                self.type = 'add_element'
                assert min_1
                self.element_value = ELEMENT_VALUES[min_1]
            elif act == 'ACT_MIX_ADD_ELEMENT_POINT':
                self.type = 'add_element_value'
                assert min_1
                self.int_value = int(min_1)


@dataclass
class EffectSpec:
    effect: Effect
    # reachable only with an essence
    is_essence: bool


class MixfieldRingValue:
    item_value: Optional[Item] = None
    int_value: int = 0
    effect_value: Optional[Effect] = None
    effect_sort_idx: int = 0
    # locked behind essence
    is_locked: bool = False

    def __repr__(self):
        value = self.item_value or self.effect_value or self.int_value
        return f'<{value} {self.is_locked}>'


class MixfieldRing:
    type: int = -1
    is_essential: bool = False
    ev_lv: int = 0
    element: Element
    ingredient: Ingredient
    x: int = 0
    y: int = 0
    # ring 0 has no parent
    parent_idx: Optional[int] = None
    morph_item: Optional[Item] = None
    # keys are target element values
    effects: dict[int, MixfieldRingValue]

    def __init__(self, recipe: Recipe, ring: ET.Element):
        self.effects = {}
        self.type = int(ring.attrib['type'])
        self.ev_lv = int(ring.get('EvLv', '0'))
        self.x = int(ring.get('x', '0'))
        self.y = int(ring.get('y', '0'))
        ingredient_idx = ring.get('restrict')
        if ingredient_idx:
            self.ingredient = recipe.ingredients[int(ingredient_idx)]
        else:
            tag = ring.attrib['ex_material']
            self.ingredient = recipe.db.items[tag]
        self.is_essential = ring.get('is_essential') is not None
        self.element = ELEMENT_LOOKUP[int(ring.attrib['elem'])]

        con = ring.find('Connect')
        if con is not None:
            idx = con.get('idx')
            # first ring might have invalid connection
            if idx:
                # TODO: store elemental locks (elem and val attrs)
                self.parent_idx = int(idx)

        param = ring.find('Param')
        assert param is not None
        for num in count():
            v = param.get(f'v{num}')
            if not v:
                break
            e = int(param.attrib[f'e{num}'])

            level_effect = MixfieldRingValue()
            level_effect.is_locked = param.get(f'n{num}') is not None
            self.effects[e] = level_effect

            if self.type in (0, 1, 2, 3):
                # effect type rings
                # update effect flags with what we now learn about them
                v = int(v)
                group = recipe.available_effects[self.type]
                level_effect.effect_value = group[v]
                level_effect.effect_sort_idx = v
            elif self.type == 6:
                # recipe morph
                child_tag = param.attrib['v0'][12:]
                level_effect.item_value = recipe.db.items[child_tag]
            else:
                level_effect.int_value = int(v)

    def apply_to_item(self, item: Item, ev_lv: int) -> None:
        if ev_lv < self.ev_lv:
            return

        if self.type == 6 and ev_lv == 0:
            # recipe morph
            first = next(iter(self.effects.values()))
            target = first.item_value
            assert target
            if target not in item.children:
                item.children.append(target)
            if item not in target.parents:
                target.parents.append(item)
            return

        if self.ingredient not in item.ingredients:
            item.ingredients.append(self.ingredient)
        if self.is_essential:
            if self.ingredient not in item.essential_ingredients:
                item.essential_ingredients.append(self.ingredient)

        # we only care about morph and effect rings
        if self.type not in (0, 1, 2, 3):
            return

        # make sure the effect group exists
        while len(item.effects) <= self.type:
            item.effects.append({})
        group = item.effects[self.type]
        for ring_effect in self.effects.values():
            eff = ring_effect.effect_value
            assert eff
            spec = group.get(ring_effect.effect_sort_idx)
            if not spec:
                spec = EffectSpec(eff, ring_effect.is_locked)
                group[ring_effect.effect_sort_idx] = spec
            else:
                if not ring_effect.is_locked:
                    spec.is_essence = False


class Mixfield:
    '''The mirage loops for an item and all its EV-link descendants'''
    rings: dict[int, MixfieldRing]

    def __init__(self, recipe: Recipe, fielddata: ET.Element):
        self.rings = {}

        try:
            for idx, node in self.find_reachable_rings(fielddata).items():
                self.rings[idx] = MixfieldRing(recipe, node)
        except Exception:
            item = recipe.item
            print(f'error parsing mixfield: {item.tag} {item.name}')
            print(xml_to_str(fielddata))
            raise

    def find_reachable_rings(self,
                             fielddata: ET.Element) -> dict[int, ET.Element]:
        all_rings = fielddata.findall('Ring')
        # find out which rings are actually connected to the recipe
        # unconnected rings are often broken
        connected = set([0])
        changed = True
        # simple flood starting from ring 0
        while changed:
            changed = False
            for idx, ring in enumerate(all_rings):
                if idx in connected:
                    continue
                connect = ring.find('Connect')
                if connect is None:
                    continue
                idx_str = connect.get('idx')
                if not idx_str:
                    continue
                other = int(idx_str)
                if other in connected:
                    connected.add(idx)
                    changed = True
        return dict((idx, all_rings[idx]) for idx in sorted(connected))

    def apply_to_item(self, item: Item, ev_lv: int) -> None:
        for ring in self.rings.values():
            ring.apply_to_item(item, ev_lv)
        item.apply_effects()


class Recipe:
    db: Database
    item: Item

    available_effects: list[dict[int, Effect]]
    ingredients: list[Ingredient]
    recipe_category: str
    make_num: int = 0
    is_ev_extended: bool = False
    # seems to mean if the thing is actually craftable
    has_data: bool = False
    ev_extend_item: Optional[Item] = None
    ev_extend_mat: Optional[Ingredient] = None

    mixfield: Optional[Mixfield] = None

    def __init__(self, db, item: Item, nodes: list[ET.Element]):
        self.db = db
        self.item = item

        assert nodes
        first = nodes[0]
        self.available_effects = []
        self.ingredients = []
        self.make_num = int(first.get('MakeNum', '1'))
        self.recipe_category = first.get('RecipeCategory', '(unkown)')
        extend_recipe = first.get('EvExtendRecipe')
        if extend_recipe:
            # self.is_ev_extended = True
            # strip 'ITEM_RECIPE_' prefix
            self.ev_extend_item = db.items[extend_recipe[12:]]
            self.ev_extend_mat = db.get_ingredient(first.attrib['EvExtendMat'])
        if first.get('HasData') == 'TRUE':
            self.has_data = True

        if self.is_ev_extended:
            assert len(nodes) == 1
            # FIXME: parse EV-link items properly
            # EV items have no materials to parse
            return

        def maybe_effect(node, attr: str) -> Optional[Effect]:
            raw = node.get(attr)
            if raw and raw != 'ITEM_EFF_EFFECT_NONE':
                return db.effects[raw]

        for node in nodes:
            mat_tag = node.get('MatTag')
            if mat_tag:
                # is_category = node.get('IsCategory')
                ingredient = db.get_ingredient(mat_tag)
                self.ingredients.append(ingredient)
            recipe_group = {}
            item_group = {}
            # default effect when no element level is reached
            mass_eff = maybe_effect(node, 'MassEffect')
            if mass_eff:
                recipe_group[-1] = mass_eff
                item_group[-1] = EffectSpec(mass_eff, False)
            for eff_num in range(10):
                eff = maybe_effect(node, f'AddEff{eff_num}')
                if not eff:
                    continue
                # FIXME: is this even useful?
                # is_ev = node.get(f'EvLv{eff_num}')
                recipe_group[eff_num] = eff
            self.available_effects.append(recipe_group)
            item.effects.append(item_group)

    def parse_mixfield(self, fd: ET.Element):
        # FIXME: is this ok?
        if fd.get('EvLv'):
            return
        self.mixfield = Mixfield(self, fd)


@dataclass
class ForgeEffect:
    forged_effect: Effect
    source_effects: list[Effect]


class Item(TaggedObject):
    level: int = -1
    price: int = -1

    categories: list[Category]
    possible_categories: list[Category]
    elements: list[Element]
    possible_elements: dict[Element, str]
    element_value: int = 0
    add_element_value: int = 0

    children: list[Item]
    parents: list[Item]

    recipe: Optional[Recipe] = None
    # structure: [effect_1, effect_2, effect_3, effect_4]
    # where effect_n: {effect_level: EffectSpec}
    # -1 is default effect_level, active without reaching anything in recipe
    effects: list[dict[int, EffectSpec]]
    ingredients: list[Ingredient]
    essential_ingredients: list[Ingredient]

    ev_base: Optional[Item] = None

    gathering: Optional[str] = None
    shop_data: Optional[str] = None
    seed: Optional[Item] = None
    fixed_potentials: list[Potential]
    forge_effects: list[list[ForgeEffect]]
    # keys are UseEnemy, UseParty, Accessory
    ev_effects: dict[str, list[EVEffect]]

    def post_init(self):
        self.children = []
        self.parents = []
        self.fixed_potentials = []
        self.forge_effects = []
        self.ev_effects = {}
        self.__effect_cache = []

        self.categories = []
        self.possible_categories = []
        self.elements = []
        self.possible_elements = {}

        self.ingredients = []
        self.essential_ingredients = []
        self.effects = []

    def parse_itemdata(self, node: ET.Element):
        self.element_value = int(node.get('elemValue', 0))
        for elem in Element:
            attr = 'elem' + elem.value
            if node.get(attr) is not None:
                self.elements.append(elem)
        for name, value in node.attrib.items():
            if name.startswith('cat_'):
                self.categories.append(self.db.categories[value])
        self.price = int(node.get('price', '0'))
        self.level = int(node.get('lv', '0'))

    def parse_recipedata(self, nodes):
        self.recipe = Recipe(self.db, self, nodes)

    def apply_ev_effects(self, ev_effects: dict[str, dict[str,
                                                          EVEffect]]) -> None:
        tags = list(sorted(i.tag for i in self.__effect_cache))
        for tag in tags:
            spec = ev_effects.get(tag)
            if not spec:
                continue
            for key, effect in spec.items():
                if key not in self.ev_effects:
                    self.ev_effects[key] = []
                self.ev_effects[key].append(effect)

    def apply_forge_effects(self, forge_effects: list[list[ForgeEffect]]):
        # books have no itemdata in ryza1
        if self.level < 0:
            return
        for group in forge_effects:
            new_group = []
            for forge_effect in group:
                accepted_effects = []
                for src in forge_effect.source_effects:
                    if src in self.__effect_cache:
                        accepted_effects.append(src)
                if accepted_effects:
                    new_group.append(
                        ForgeEffect(forge_effect.forged_effect,
                                    accepted_effects))
            if new_group:
                self.forge_effects.append(new_group)

    def apply_effects(self, enable_essence=True):
        self.__effect_cache = []
        for group in self.effects:
            for spec in group.values():
                if not enable_essence and spec.is_essence:
                    continue
                self.__effect_cache.append(spec.effect)
                # ignore unobatainable effects
                eff = spec.effect
                source_type = 'normal' if not spec.is_essence else 'essence'
                if eff.type == 'add_element':
                    value = eff.element_value
                    assert value
                    self.possible_elements[value] = source_type
                elif eff.type == 'add_category':
                    value = eff.category_value
                    assert value
                    cat = self.db.categories[value]
                    self.possible_categories.append(cat)
                elif eff.type == 'add_element_value':
                    value = eff.int_value
                    assert value
                    self.add_element_value = max(self.add_element_value, value)

    def format_effects(self):
        names = []
        for group in self.effects:
            for spec in reversed(group.values()):
                name = spec.effect.name
                if spec.is_essence:
                    name += '*'
                names.append(name)
                break
        names.sort()
        return ', '.join(names)

    def print(self, verbose=False):
        print(self.long_desc())
        print()
        if verbose:
            print_map(self)

    def long_desc(self):
        lines = []
        lines.append(f'{self.name} -- {self.tag}')
        lines.append(f'  Level: {self.level}, price: {self.price}')

        def list_str(normal, optional, sort=False):
            names = list(map(str, normal))
            names.extend(str(i) + '*' for i in optional)
            if sort:
                names.sort()
            return ', '.join(names)

        def add_list(description, normal, optional=[], sort=False):
            joined = list_str(normal, optional, sort)
            if joined:
                lines.append(f'  {description}: {joined}')

        add_list('Categories', self.categories, self.possible_categories)

        def translate_elems(elems: Iterable[Element]):
            return [self.db.elements[elem] for elem in elems]

        elems_str = list_str(translate_elems(self.elements),
                             translate_elems(self.possible_elements.keys()))
        elem_range = str(self.element_value)
        if self.add_element_value > 0:
            elem_range += f"+{self.add_element_value}"
        lines.append(f'  Elements: {elem_range} {elems_str}')

        if self.recipe:
            effects = self.format_effects()
            if effects:
                lines.append(f'  Effects: {effects}')
        add_list('Ingredients', self.ingredients)
        add_list('Essential ingredients', self.essential_ingredients)
        resolved_parents = []
        parents = self.parents
        while parents:
            if len(parents) > 1:
                lines.append(f'!!WARNING: got multiple parents: {parents}')
            parent = parents[0]
            resolved_parents.insert(0, str(parent))
            parents = parent.parents
        if resolved_parents:
            lines.append(f'  Parents: {" --> ".join(resolved_parents)}')
        add_list('Children', self.children)

        return '\n'.join(lines)


class Database:
    game: str
    lang: str
    items: dict[str, Item]
    categories: dict[str, Category]
    effects: dict[str, Effect]
    potentials: dict[str, Potential]
    elements: dict[Element, str]
    ev_effects: dict[str, EVEffect]
    ring_types: dict[int, tuple[str, str]]

    data_dir: Path

    def __init__(self, game: str, lang: str = 'en'):
        self.game = game
        self.lang = lang
        self.data_dir = Path(f'game_files/{game}/data')
        self.items = {}
        self.categories = {}
        self.effects = {}
        self.potentials = {}
        self.elements = {}
        self.ev_effects = {}
        self.ring_types = {}

        with open(f'game_files/{game}/tags.json') as fp:
            tags = json.load(fp)

        self.strings = self.load_strings()
        # first load basic data: tags and names
        # these magic offsets are the same for ryza 1 & 2
        init_data = [
            (self.items, 'items', Item, 6750209),
            (self.items, 'items_dlc_1', Item, 6750989),
            (self.items, 'items_dlc_2', Item, 6751114),
            (self.items, 'items_furniture', Item, 6751039),
            (self.categories, 'categories', Category, 6815745),
            (self.effects, 'effects', Effect, 6881281),
            (self.potentials, 'potentials', Potential, 6946817),
            (self.ev_effects, 'ev_effects', EVEffect, 7208961),
        ]
        for target, attr, factory, offset in init_data:
            val = self.get_tag_map(factory, tags[attr], offset)
            target.update(val)

        self.parse_effects()
        # FIXME: something has to be wrong with DLC data parsing
        if self.game == 'ryza1':
            # ITEM_DLC_014 has no name or itemData
            # but has a recipe and a mixfield, and is referenced by
            # ITEM_DLC_012's mixfield...
            # maybe the item's name is at another offset?
            for bad_tag in ['ITEM_DLC_014', 'ITEM_DLC_037']:
                bad = Item(self, -1, bad_tag, '???', -1)
                self.items[bad_tag] = bad
        self.parse_items()
        self.parse_recipedata()
        self.parse_mixfield()
        self.parse_descriptions()
        self.parse_gathering()
        # TODO: parse potential effects from item/item_potential.xml?
        self.parse_item_status()
        self.parse_forge_effects()
        self.parse_ev_effects()
        self.parse_appear_ev_effect()
        self.parse_ring_types()

    def parse_ring_types(self):
        name_offset, desc_offset = RING_TYPE_OFFSETS[self.game]
        for i in range(desc_offset - name_offset):
            name = self.strings.get(name_offset + i)
            if not name:
                continue
            desc = self.strings[desc_offset + i]
            self.ring_types[i] = (name, desc)

    def parse_appear_ev_effect(self):
        xml_path = self.data_dir / 'Saves/item/item_appear_ev_effect.xml'
        if not xml_path.exists():
            return
        root = self.open_xml(xml_path)

        specs = {}
        for node in root:
            src_tag = node.attrib['srcEff']
            effs = {}
            for typ in ('UseEnemy', 'UseParty', 'Accessory'):
                effs[typ] = self.ev_effects[node.attrib[f'evEff{typ}']]
            specs[src_tag] = effs
        for item in self.items.values():
            item.apply_ev_effects(specs)

    def parse_ev_effects(self):
        xml_path = self.data_dir / 'Saves/item/item_ev_effect_no.xml'
        if not xml_path.exists():
            return
        root = self.open_xml(xml_path)

        for ev_eff in self.ev_effects.values():
            # FIXME:
            # ITEM_EV_EFF_DUMMY_166 & ITEM_EV_EFF_DUMMY_167 are split badly
            # this results in freeze protection not having any effects
            ev_eff.effects = []

        for node in root:
            name_id = int(node.attrib['nameID'])
            try:
                ev_eff = self.with_name_id(self.ev_effects, name_id)
            except ValueError:
                continue
            for i in range(10):
                eff_tag = node.get(f'effTag_{i}')
                if not eff_tag:
                    break
                ev_eff.effects.append(self.effects[eff_tag])

    def parse_forge_effects(self):
        for eq_type in ('accessory', 'weapon', 'armor'):
            part = eq_type.title()
            path_part = f'Saves/weaponForge/{part}ForgeEffectTable.xml'
            xml_path = self.data_dir / path_part
            # ryza 1 only has weapon forge
            if not xml_path.exists():
                continue
            root = self.open_xml(xml_path)

            effect_groups = []
            current = {}

            def maybe_emit(num):
                nonlocal current
                if not current or num != current['num']:
                    if current:
                        effect_groups.append(current['forge_effects'])
                    current = {'num': num, 'forge_effects': []}

            for node in root:
                dst = self.effects[node.attrib['dst']]
                num = int(node.attrib['No'])
                maybe_emit(num)
                srcs = []
                for i in range(10):
                    src = node.get(f'src{i}')
                    if not src:
                        break
                    srcs.append(self.effects[src])
                current['forge_effects'].append(ForgeEffect(dst, srcs))
            maybe_emit(-1)

            for item in self.items.values():
                item.apply_forge_effects(effect_groups)

    def parse_item_status(self):
        if not self.potentials:
            print('WARNING: potentials were not parsed!')
            return
        xml_path = self.data_dir / 'Saves/item/item_status.xml'
        root = self.open_xml(xml_path)

        nodes = root.iter('item_status')
        for node, item in zip(nodes, self.items.values()):
            for i in range(10):
                pot = node.get(f'pot_{i}')
                eff = node.get(f'eff_{i}')
                if pot:
                    potential = self.potentials[pot]
                    item.fixed_potentials.append(potential)
                if eff:
                    effect = self.effects[eff]
                    assert len(item.effects) <= i
                    item.effects.append({-1: EffectSpec(effect, False)})

    def load_strings(self) -> dict[int, str]:
        str_path = f'Saves/Text_{self.lang.upper()}/strCombineAll.xml'
        stringmap = {}
        root = self.open_xml(Path(self.data_dir / str_path))
        for node in root.iter('str'):
            text = node.attrib['Text'].strip(' \r\t\u200b')
            stringmap[int(node.attrib['String_No'])] = text
        return stringmap

    def dump(self, fp: TextIO):
        import json

        dump = {}
        for field in ['items', 'effects', 'categories', 'ev_effects']:
            dump[field] = {
                k: json_dump_helper(v, True)
                for k, v in getattr(self, field).items()
            }
        dump['elements'] = {k.value: v for k, v in self.elements.items()}
        dump['ring_types'] = self.ring_types
        json.dump(dump, fp, default=json_dump_helper)

    def find_items(self, query: str) -> Generator[Item, None, None]:
        query = query.upper()
        for item in self.items.values():
            if query in item.tag or query in item.name.upper():
                yield item

    def parse_gathering(self):
        csv_path = self.data_dir / 'materials.csv'
        if not csv_path.exists():
            return
        seeds = {}
        for num in count(1):
            tag = f'ITEM_MIX_MATERIAL_SEED_{num:03d}'
            seed = self.items.get(tag)
            if not seed:
                break
            seeds[seed.name.split()[0]] = seed
        with csv_path.open() as fp:
            for row in csv.DictReader(fp):
                # FIXME: DLC items are missing
                name = row['Item'].strip(' \r\t\u200b')
                for item in self.items.values():
                    if item.name == name:
                        break
                else:
                    continue
                item.gathering = row['Location Info']
                item.shop_data = row['Development Info']
                seed = row['Seed']
                if seed:
                    item.seed = seeds[row['Seed']]

    def parse_descriptions(self):
        offset = ELEMENT_STR_MAP_GAME[self.game]
        for idx, element in enumerate(Element):
            self.elements[element] = self.strings[offset + idx]

        offset = EFFECT_DESC_OFFSET
        first_eff = next(iter(self.effects.values()))
        for eff in self.effects.values():
            idx = eff.name_id - first_eff.name_id + offset
            desc = self.strings.get(idx)
            if not desc:
                continue
            eff.description = desc

        for item in self.items.values():
            idx = item.name_id - 3276800
            desc = self.strings.get(idx)
            if not desc:
                continue
            item.description = desc

    def parse_mixfield(self):
        xml_path = self.data_dir / 'Saves/mix/mixFieldData.xml'
        root = self.open_xml(xml_path)

        for fd in root.iter('FieldData'):
            fd_tag = fd.get('tag', '')
            item = self.items[fd_tag]
            assert item.recipe, (item.tag, item.name)
            # FIXME: I'm not sure EV-link item handling is correct
            item.recipe.parse_mixfield(fd)
            if not item.recipe.mixfield:
                continue
            item.recipe.mixfield.apply_to_item(item, 0)
            extend = item.recipe.ev_extend_item
            if extend:
                item.recipe.mixfield.apply_to_item(extend, 1)
                extend.ev_base = item

    def parse_recipedata(self):
        xml_path = self.data_dir / 'Saves/item/itemRecipeData.xml'
        root = self.open_xml(xml_path)
        item = None
        recipe = []

        def parse_current_recipe():
            nonlocal recipe, item
            if not recipe:
                return
            assert item, list(map(xml_to_str, recipe))
            item.parse_recipedata(recipe)
            item = None
            recipe = []

        for node in root.iter('itemRecipeData'):
            item_tag = node.get('ItemTag')
            if item_tag:
                parse_current_recipe()
                item = self.items.get(item_tag)
                if item is None:
                    # 'reserve' items and some furniture?
                    continue
            if item is not None:
                recipe.append(node)
        parse_current_recipe()

    def parse_items(self):
        for item in self.items.values():
            # make sure evey item has basic structures
            item.post_init()
        xml_path = self.data_dir / 'Saves/item/itemData_no.xml'
        root = self.open_xml(xml_path)
        for node in root.iter('itemData'):
            name_id = node.get('nameID')
            if name_id is None:
                continue
            name_id = int(name_id)
            try:
                item = self.with_name_id(self.items, name_id)
            except ValueError:
                kind = node.get('kindTag')
                cat_0 = node.get('cat_0')
                is_dlc = node.get('isDlc')
                name = self.strings[name_id]
                # I have no idea where tags for mists are in ryza 2
                if kind == 'ITEM_KIND_IMPORTANT' and cat_0 is None:
                    continue
                elif kind == 'ITEM_KIND_MATERIAL' and is_dlc:
                    continue
                print(f'{name_id} {name} {xml_to_str(node)}')
                raise ValueError(f'unkown item: {name} {name_id}')
            item.parse_itemdata(node)

    def parse_effects(self):
        xml_path = self.data_dir / 'Saves/item/item_effect_no.xml'
        root = self.open_xml(xml_path)
        for node in root.iter('item_effect'):
            name_id = node.get('nameID')
            if name_id is None:
                continue
            name_id = int(name_id)
            effect = self.with_name_id(self.effects, name_id)
            effect.init_effect(node)

    def with_name_id(self, items: dict[str, TaggedType],
                     name_id: int) -> TaggedType:
        results = [item for item in items.values() if item.name_id == name_id]
        if len(results) != 1:
            raise ValueError(f'expected 1 item, got {len(results)}')
        return results[0]

    def open_xml(self, path: Path) -> ET.Element:
        # switch rips yield case-sensitive files
        # but steam rips are all-lowercase
        if not path.exists():
            path = Path(str(path).lower())
        # ElementTree sometimes struggles with shift-jis
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ValueError:
            with path.open('rt', encoding='shift-jis') as stream:
                root = ET.fromstring(stream.read())
        return root

    def get_tag_map(self, factory, tags: list[str], offset: int):
        '''load tag list from flat file, then add ids and names from xml'''
        name_map = {}
        for n, tag in enumerate(tags):
            name_id = n + offset
            name = self.strings.get(name_id)
            if name:
                name_map[tag] = factory(self, n, tag, name, name_id)
        return name_map

    def find_item_or_category(
            self, query: str) -> tuple[Optional[Item], Optional[Category]]:
        query = query.upper()
        item_match = None
        cat_match = None
        # 1st check if the query is an exact tag
        if query in self.items:
            return (self.items[query], None)
        if query in self.categories:
            return (None, self.categories[query])
        for item in self.items.values():
            haystack = item.name.upper()
            if query == haystack:
                return (item, None)
            elif query in haystack and not item_match:
                item_match = item
        for cat in self.categories.values():
            haystack = cat.name.upper()
            if query == haystack:
                return (None, cat)
            elif query in haystack and not cat_match:
                cat_match = cat
        if item_match:
            return (item_match, None)
        return (None, cat_match)

    def find_item(self, query: str) -> Optional[Item]:
        query = query.upper()
        for tag, item in self.items.items():
            if query == tag or query == item.name.upper():
                return item
        for tag, item in self.items.items():
            if query in tag or query in item.name.upper():
                return item

    def find_category(self, query: str) -> Optional[Category]:
        query = query.upper()
        for tag, cat in self.categories.items():
            if query == tag or query == cat.name.upper():
                return cat
        for tag, cat in self.categories.items():
            if query in tag or query in cat.name.upper():
                return cat

    def get_ingredient(self, tag: str) -> Ingredient:
        if tag in self.items:
            return self.items[tag]
        return self.categories[tag]


def xml_to_str(node: ET.Element):
    return ET.tostring(node, encoding='unicode').strip()


def print_map(item: Item) -> None:
    ev_lv = 0
    orig_item = item
    if item.ev_base:
        item = item.ev_base
        ev_lv = 1
    if not item.recipe:
        return
    nodes = []
    connections = []
    min_x = 0
    max_x = 0
    min_y = 0
    max_y = 0
    ingredients = dict()
    for n, tag in enumerate(item.recipe.ingredients):
        ingredients[str(n)] = tag
    mixfield = item.recipe.mixfield
    if not mixfield:
        return
    print(f'mix field for item {orig_item.name} -- {orig_item.tag}:')
    sym_idx = 0
    for idx, ring in mixfield.rings.items():
        if ring.ev_lv > ev_lv:
            continue
        min_x = min(ring.x, min_x)
        max_x = max(ring.x, max_x)
        min_y = min(ring.y, min_y)
        max_y = max(ring.y, max_y)
        symbol = string.printable[sym_idx]
        sym_idx += 1
        nodes.append((ring.x, ring.y, symbol))

        if ring.parent_idx is not None:
            other = mixfield.rings[ring.parent_idx]
            connections.append((ring, other))

        ring_info = {
            'idx': idx,
            'sym': symbol,
            'type': ring.type,
            'elem': ring.element.name,
            'item': ring.ingredient.tag,
        }
        if ring.ev_lv:
            ring_info['ev_lv'] = ring.ev_lv
        if ring.is_essential:
            ring_info['essential'] = 1
        print(ring_info)
    width = (max_x - min_x + 1) * 2
    height = (max_y - min_y + 1) * 2
    canvas = [[' ' for _ in range(width)] for _ in range(height)]
    for x, y, symbol in nodes:
        x = (x - min_x) * 2
        y = (y - min_y) * 2
        canvas[y][x] = symbol
    for a, b in connections:
        dx = b.x - a.x
        dy = b.y - a.y
        x = (a.x - min_x) * 2
        y = (a.y - min_y) * 2
        ch = None
        if dx == 0:
            if dy == -2:
                canvas[y - 1][x] = '|'
                canvas[y - 2][x] = '|'
                canvas[y - 3][x] = '|'
            else:
                canvas[y + 1][x] = '|'
                canvas[y + 2][x] = '|'
                canvas[y + 3][x] = '|'
        else:
            if dx == -1:
                if dy == -1:
                    ch = '\\'
                else:
                    ch = '/'
            else:
                if dy == -1:
                    ch = '/'
                else:
                    ch = '\\'
            assert ch
            canvas[y + dy][x + dx] = ch
    for line in canvas:
        print(''.join(line))
    print()


def json_dump_helper(obj, full=False):
    if not full and hasattr(obj, 'tag'):
        return obj.tag
    elif isinstance(obj, Element):
        return obj.value
    elif isinstance(obj, set):
        return list(obj)
    elif hasattr(obj, 'dump'):
        return obj.dump()
    else:
        dump = {}
        for attr in dir(obj):
            if attr.startswith('_'):
                continue
            if attr == 'db':
                continue
            value = getattr(obj, attr)
            if callable(value):
                continue
            if attr == 'possible_elements':
                value = {k.value: v for k, v in value.items()}
            dump[attr] = value
        return dump


def unpack_type(type_, known, no_tags=False):
    origin = typing.get_origin(type_)
    args = typing.get_args(type_)
    if origin is None:
        # simple type
        if type_ == Database:
            raise ValueError('I can not serialize that')
        elif type_ == int:
            return 'number'
        elif type_ == str:
            return 'string'
        elif type_ == bool:
            return 'boolean'
        elif isinstance(None, type_):
            return 'null'
        elif issubclass(type_, TaggedObject):
            if no_tags:
                if type_ not in known:
                    known[type_] = None
                return type_.__name__
            return 'string'
        elif type_ == Element:
            return 'string'
        else:
            # mark the type as has to be visited
            if type_ not in known:
                known[type_] = None
            return type_.__name__
    elif origin == Union:
        return '(' + ' | '.join(unpack_type(i, known, no_tags)
                                for i in args) + ')'
    elif origin == list:
        assert len(args) == 1, args
        return f'{unpack_type(args[0], known, no_tags)}[]'
    elif origin == dict:
        assert len(args) == 2, args
        # javascript can only use strings as object index
        k = 'string'
        v = unpack_type(args[1], known, no_tags)
        return f'{{[key: {k}]: {v}}}'
    elif origin == tuple:
        return '[' + ', '.join(unpack_type(i, known, no_tags)
                               for i in args) + ']'
    raise ValueError(f'unkown type {type_}')


def create_typescript_interface(cls, known, no_tags=False):
    result = f'export interface {cls.__name__} {{\n'
    for name, type_ in typing.get_type_hints(cls).items():
        # no need for paths in the json
        if type_ == Path:
            continue
        # do not serialize backrefs to the db
        if type_ == Database:
            continue
        type_str = unpack_type(type_, known, no_tags)
        result += f'  {name}: {type_str};\n'
    result += '}\n'
    return result


def create_typescript_interfaces():
    # these are the top level tagged types in the db
    known: dict[type, Optional[str]] = {
    }
    known[Database] = create_typescript_interface(Database, known, True)
    while True:
        changed = False
        for cls, val in list(known.items()):
            if val is None:
                known[cls] = create_typescript_interface(cls, known)
                changed = True
        if not changed:
            break
    # this makes the type checker happy
    strings: list[str] = []
    for val in known.values():
        assert val is not None
        strings.append(val)
    print('// Generated code, do not edit!')
    print('// Use python3 -m atelier_tools dump-ts-types to generate\n')
    print('\n'.join(strings))
