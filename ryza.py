#!/usr/bin/env python3

from __future__ import annotations

from typing import Generator, Iterable, Optional, TypeVar, Union
import xml.etree.ElementTree as ET
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from itertools import count
import string
import csv

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

# TODO: these MIGHT be listed in the string table
KNOWN_RING_TYPES = {
    0: 'Effect 1',
    1: 'Effect 2',
    2: 'Effect 3',
    3: 'Effect 4',
    4: 'Quality',
    5: 'Trait unlocks',
    6: 'Recipe morph',
    7: 'Item Level -',
    8: 'CC -',
    11: 'ATK +',
    12: 'DEF +',
    13: 'SPD +',
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
    type_str: Optional[str] = None
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
        self.type_str = KNOWN_RING_TYPES.get(self.type)
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

        for idx, node in self.find_reachable_rings(fielddata).items():
            self.rings[idx] = MixfieldRing(recipe, node)

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
    level: int = 0
    price: int = 0

    categories: list[Category]
    possible_categories: list[Category]
    elements: list[Element]
    possible_elements: dict[Element, str]
    element_value: int = 0
    add_element_value: int = 0

    children: list[Item]
    parents: list[Item]

    recipe: Optional[Recipe]
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

    def parse_itemdata(self, node: ET.Element):
        self.recipe = None
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

    data_dir: Path

    def __init__(self, game: str, lang: str = 'en'):
        self.game = game
        self.lang = lang
        self.data_dir = Path(f'{game}_data')
        self.items = {}
        self.categories = {}
        self.effects = {}
        self.elements = {}
        self.potentials = {}

        self.strings = self.load_strings()
        # first load basic data: tags and names
        # these magic offsets are the same for ryza 1 & 2
        init_data = [
            ('items', Item, 'name', 6750209),
            ('categories', Category, 'category', 6815745),
            ('effects', Effect, 'effect', 6881281),
            ('potentials', Potential, 'potential', 6946817),
            ('potentials', Potential, 'potential', 6946817),
            ('ev_effects', EVEffect, 'ev_eff', 7208961),
        ]
        for attr, factory, key, offset in init_data:
            tags_path = f'item_{key}_tags.txt'
            val = self.get_tag_map(factory, tags_path, offset)
            setattr(self, attr, val)

        self.parse_effects()
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

    def parse_appear_ev_effect(self):
        xml_path = self.data_dir / 'saves/item/item_appear_ev_effect.xml'
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
        xml_path = self.data_dir / 'saves/item/item_ev_effect_no.xml'
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
            path_part = f'saves/weaponforge/{eq_type}forgeeffecttable.xml'
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
        xml_path = self.data_dir / 'saves/item/item_status.xml'
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
        str_path = f'saves/text_{self.lang}/strcombineall.xml'
        stringmap = {}
        root = self.open_xml(Path(self.data_dir / str_path))
        for node in root.iter('str'):
            text = node.attrib['Text'].strip(' \r\t\u200b')
            stringmap[int(node.attrib['String_No'])] = text
        return stringmap

    def dump(self):
        dump = {}
        for field in ['items', 'effects', 'categories', 'ev_effects']:
            dump[field] = {
                k: json_dump_helper(v, True)
                for k, v in getattr(self, field).items()
            }
        dump['elements'] = {k.value: v for k, v in self.elements.items()}
        return dump

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
                    # print(f'unknown item {name!r}')
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
        xml_path = self.data_dir / 'saves/mix/mixfielddata.xml'
        root = self.open_xml(xml_path)

        for fd in root.iter('FieldData'):
            fd_tag = fd.get('tag', '')
            item = self.items[fd_tag]
            assert item.recipe
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
        xml_path = self.data_dir / 'saves/item/itemrecipedata.xml'
        root = self.open_xml(xml_path)
        item = None
        recipe = []

        def parse_current_recipe():
            nonlocal recipe, item
            if not recipe:
                return
            assert item
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
            recipe.append(node)
        parse_current_recipe()

    def parse_items(self):
        xml_path = self.data_dir / 'saves/item/itemdata_no.xml'
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
                assert kind == 'ITEM_KIND_BOOK'
                continue
            item.parse_itemdata(node)

    def parse_effects(self):
        xml_path = self.data_dir / 'saves/item/item_effect_no.xml'
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
        # ElementTree sometimes struggles with shift-jis
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ValueError:
            with path.open('rt', encoding='shift-jis') as stream:
                root = ET.fromstring(stream.read())
        return root

    def get_tag_map(self, factory, tags_path, offset: int):
        '''load tag list from flat file, then add ids and names from xml'''
        tags_path = self.data_dir / tags_path
        tags = []
        with tags_path.open() as stream:
            for line in stream:
                tags.append(line.strip())

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


def is_ingredient_of(ingredient: Item, target: Item):
    if ingredient in target.ingredients:
        return True
    cats = ingredient.categories + ingredient.possible_categories
    for cat in cats:
        if cat in target.ingredients:
            return True
    return False


def is_directly_reachable(item_a: Item, item_b: Item):
    if item_b in item_a.children:
        return True
    return is_ingredient_of(item_a, item_b)


def explain_connection(item_a: Item, item_b: Item):
    connections = []
    if item_b in item_a.children:
        connections.append('derivative')
    if item_a in item_b.ingredients:
        connections.append('named ingredient')
    category_descriptions = [(item_a.categories, ''),
                             (item_a.possible_categories, '*')]
    for cats, suffix in category_descriptions:
        for cat in cats:
            if cat in item_b.ingredients:
                cat_name = cat.name.strip('()')
                connections.append(f'{cat_name}{suffix}')
    return ', '.join(connections)


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


def find_routes_from_category(db: Database,
                              source: Category,
                              target_item: Optional[Item] = None,
                              target_category: Optional[Category] = None,
                              limit: int = 5):
    assert target_item or target_category
    assert not (target_item and target_category)

    if target_item:
        if source in target_item.ingredients:
            yield [target_item]
            return

    for item in db.items.values():
        if source in item.ingredients:
            yield from find_routes(db, item, target_item, target_category,
                                   set(), limit)


# FIXME: replace this horrible thing with Yen's algorithm
def find_routes(db: Database,
                this_item: Item,
                target_item: Optional[Item] = None,
                target_category: Optional[Category] = None,
                visited: Optional[set[str]] = None,
                limit: int = 5):
    assert target_item or target_category
    assert not (target_item and target_category)
    # FIXME: maybe reimplement this?
    # disabled = this_item.get('disabled')
    # if disabled:
    #     return None
    if visited is None:
        visited = set()
    visited.add(this_item.tag)

    if target_item:
        if is_directly_reachable(this_item, target_item):
            yield [this_item, target_item]
            return
    else:
        assert target_category
        if target_category in this_item.categories or \
           target_category in this_item.possible_categories:
            yield [this_item]
            return

    limit -= 1
    if limit <= 0:
        return None

    for tag, item in db.items.items():
        if tag in visited:
            continue
        if is_directly_reachable(this_item, item):
            chains = find_routes(db, item, target_item, target_category,
                                 visited.copy(), limit)
            for chain in chains:
                yield [this_item] + chain


def describe_chain(chain: list[Item]):
    prev = None
    desc = ''
    for item in chain:
        name = item.name
        if not prev:
            desc = name
        else:
            desc += f' ({explain_connection(prev, item)}) -> {name}'
        prev = item
    return desc


def print_best_chains(chains: Iterable[list[Item]],
                      limit: int = 3,
                      prefix: str = ''):
    scored_chains = [(len(chain), chain) for chain in chains]
    scored_chains.sort(key=lambda i: i[0])
    min_score = None
    for num, (score, chain) in enumerate(scored_chains):
        if (num + 1) >= limit:
            if min_score is None:
                min_score = score
            if score > min_score:
                break
        print(prefix + describe_chain(chain))


def format_effects(item, effects):
    recipe = item.get('recipe')
    if not recipe:
        return None
    names = []
    for group in recipe['effects'].values():
        eff = group[-1]
        name = effects[eff]['name']
        names.append(name)
    names.sort()
    return ', '.join(names)


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
            if attr.startswith('__'):
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


def main():
    import argparse

    main_parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    main_parser.add_argument('--game',
                             type=str,
                             default='ryza2',
                             help='game to use (ryza1 or ryza2)')
    main_parser.add_argument('--lang',
                             type=str,
                             default='en',
                             help='2 letter language code')
    main_parser.add_argument('-v', '--verbose', action='store_true')
    subparsers = main_parser.add_subparsers(dest='command')

    item_info_parser = subparsers.add_parser('items', help='item info')
    item_info_parser.add_argument('item_names', nargs='*', type=str.lower)

    item_chain_parser = subparsers.add_parser('chain', help='find craft chain')
    item_chain_parser.add_argument('source',
                                   type=str.lower,
                                   help='category or item to start chain from')
    item_chain_parser.add_argument('target',
                                   type=str.lower,
                                   help='category or item to chain to')

    recipe_find_parser = subparsers.add_parser('category',
                                               help='find recipe for category')
    recipe_find_parser.add_argument('category', type=str.lower)

    subparsers.add_parser('dump-effects', help='dump effect names')
    subparsers.add_parser('dump-categories', help='dump category names')

    dump_json = subparsers.add_parser('dump-json', help='dump effect names')
    dump_json.add_argument('dump_file', type=argparse.FileType('w'))

    args = main_parser.parse_args()

    db = Database(args.game, lang=args.lang)
    # db = Database(Path('ryza1_data'))

    # TODO: re-add this option?
    # late game powerful items can mess up early game chain searches
    # disabled = [
    #     # 'red stone',
    #     # 'Philosopher\'s Stone',
    #     # 'Crystal Element',
    #     # 'Holy Nut',
    # ]

    if args.command == 'items':
        if not args.item_names:
            for item in db.items.values():
                item.print(args.verbose)
        else:
            seen = set()
            for q in args.item_names:
                for item in db.find_items(q):
                    if item.tag in seen:
                        continue
                    item.print(args.verbose)
                    seen.add(item.tag)
    elif args.command == 'chain':
        source_item, source_cat = db.find_item_or_category(args.source)
        if not (source_item or source_cat):
            print(f'{args.source} not found!')
            return 1
        assert not (source_item and source_cat)

        target_item, target_cat = db.find_item_or_category(args.target)
        if not (target_item or target_cat):
            print(f'{args.target} not found!')
            return 1
        assert not (target_item and target_cat)
        source = source_item or source_cat
        assert source
        target = target_item or target_cat
        assert target
        print(f'Finding craft chain from {source.name} to {target.name}...')
        if source_cat:
            chains = find_routes_from_category(db, source_cat, target_item,
                                               target_cat)
            print_best_chains(chains, prefix=f'{source_cat.name} -> ')
        else:
            assert source_item
            chains = find_routes(db, source_item, target_item, target_cat)
            print_best_chains(chains)
    elif args.command == 'dump-effects':
        for eff in db.effects.values():
            # FIXME: dump some useful effect data?
            print(f'{eff.tag} -- {eff.name} : {eff.description}')
    elif args.command == 'dump-categories':
        for cat in db.categories.values():
            print(f'{cat.tag} -- {cat.name}')
    elif args.command == 'dump-json':
        # FIXME
        import json
        json.dump(db.dump(), args.dump_file, default=json_dump_helper)
    else:
        raise ValueError(f'unkown command {args.command}')


if __name__ == '__main__':
    main()
