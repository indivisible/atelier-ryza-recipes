#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from enum import Enum
from collections import defaultdict
from pprint import pprint

# tag lists were pulled from `strings <game exe>`

# FIXME: known bug: staltium has ITEM_EFF_CREATE_ATK_5 in xml but not in game?!
# TODO: make codebase unified with ryza1
# TODO: replace the whole dicts + procedural mess with classes

DATA_DIR = 'ryza2_data'


# NOTE: while ryza 2 has renamed thunder to lightning and air to wind
# those are UI-only changes, while these affect XML parsing!
class Element(Enum):
    FIRE = 'Fire'
    ICE = 'Ice'
    THUNDER = 'Thunder'
    AIR = 'Air'


ADD_ELEMENT_EFFECTS = {
    'ITEM_EFF_CREATE_MATERIAL_BOOST_08': Element.FIRE,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_09': Element.ICE,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_10': Element.THUNDER,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_11': Element.AIR,
}

ELEMENT_RANGE_EFFECTS = {
    'ITEM_EFF_CREATE_MATERIAL_BOOST_15': 1,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_16': 2,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_17': 3,
    'ITEM_EFF_CREATE_MATERIAL_BOOST_18': 4,
}


def open_xml(path):
    path = DATA_DIR + '/' + path
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ValueError:
        with open(path, 'rt', encoding='shift-jis') as stream:
            root = ET.fromstring(stream.read())
    return root


def load_strings(path):
    root = open_xml(path)
    strings = {}
    for node in root.iter('str'):
        num_str = node.get('String_No')
        assert num_str, node
        num = int(num_str)
        text = node.get('Text')
        strings[num] = text

    return strings


def get_tag_map(tags_path, strings_path, offset):
    tags = []
    # FIXME: use Path
    with open(DATA_DIR + '/' + tags_path) as stream:
        for line in stream:
            tags.append(line.strip())

    strings = load_strings(strings_path)

    name_map = {}
    for n, tag in enumerate(tags):
        name_id = n + offset
        name = strings.get(name_id)
        if name:
            name_map[tag] = {
                'name': name,
                'tag': tag,
                'idx': n,
                'name_id': name_id,
            }
            # print(f'({n}) {tag}: {name} ({name_id})')

    return name_map


def get_effect_tag_map():
    tags_path = 'effect_tags.txt'
    strings_path = 'saves/text_en/str_item_effect.xml'
    return get_tag_map(tags_path, strings_path, 6881281)


def get_item_map():
    tags_path = 'item_tags.txt'
    strings_path = 'saves/text_en/str_item_name.xml'
    return get_tag_map(tags_path, strings_path, 6750209)


def get_category_map():
    tags_path = 'item_categories.txt'
    strings_path = 'saves/text_en/str_item_category.xml'
    return get_tag_map(tags_path, strings_path, 6815745)


def parse_recipes(items, effects):
    xml_path = 'saves/item/itemrecipedata.xml'
    root = open_xml(xml_path)
    recipe = {}
    item = None
    for node in root.iter('itemRecipeData'):
        item_tag = node.get('ItemTag')
        if item_tag:
            item = items.get(item_tag)
            if item is None:
                # 'reserve' items and some furniture?
                continue
            recipe = {
                'item_tag': item_tag,
                'effects': defaultdict(list),
                'ingredients': [],
                'recipe_category': node.get('RecipeCategory'),
            }
            assert 'recipe' not in item
            item['recipe'] = recipe
        if not item:
            continue
        mat_tag = node.get('MatTag')
        # ensure that effects are in order
        for name, value in sorted(node.attrib.items(), key=lambda e: e[0]):
            if value == 'ITEM_EFF_EFFECT_NONE':
                continue

            if value in ELEMENT_RANGE_EFFECTS:
                ev = ELEMENT_RANGE_EFFECTS[value]
                item['add_element_value'] = max(item['add_element_value'], ev)
            elif value in ADD_ELEMENT_EFFECTS:
                elem = ADD_ELEMENT_EFFECTS[value]
                item['possible_elements'].add(elem)

            if name == 'MassEffect':
                # default effect when no elements reached
                recipe['effects'][mat_tag].insert(0, value)
            elif name.startswith('AddEff'):
                # added effects reachable with high element value
                # FIXME: some of these might not be reachable if not used
                #        in mixfielddata.xml
                recipe['effects'][mat_tag].append(value)
                eff = effects[value]
                if eff['type'] == 'add_category':
                    item['possible_categories'].add(eff['value'])
            elif name == 'MatTag':
                recipe['ingredients'].append(value)


def with_name_id(items, name_id):
    results = [item for item in items.values() if item['name_id'] == name_id]
    if len(results) != 1:
        raise ValueError('expected 1 item, got {}'.format(len(results)))
    return results[0]


def parse_items(items):
    xml_path = 'saves/item/itemdata_no.xml'
    root = open_xml(xml_path)
    for item in items.values():
        item['categories'] = set()
        item['children'] = set()
        item['parents'] = set()
        item['possible_categories'] = set()
        item['elements'] = set()
        item['possible_elements'] = set()
        item['element_value'] = 0
        item['add_element_value'] = 0
    for node in root.iter('itemData'):
        name_id = node.get('nameID')
        if name_id is None:
            continue
        name_id = int(name_id)
        try:
            item = with_name_id(items, name_id)
        except ValueError:
            kind = node.get('kindTag')
            assert kind == 'ITEM_KIND_BOOK'
            continue
        item['element_value'] = int(node.get('elemValue', 0))
        for elem in Element:
            attr = 'elem' + elem.value
            if node.get(attr) is not None:
                item['elements'].add(elem)
        for name, value in node.attrib.items():
            if name.startswith('cat_'):
                item['categories'].add(value)


def parse_effects(effects):
    xml_path = '/saves/item/item_effect_no.xml'
    root = open_xml(xml_path)
    for node in root.iter('item_effect'):
        name_id = node.get('nameID')
        if name_id is None:
            continue
        name_id = int(name_id)
        eff = with_name_id(effects, name_id)
        # effects can ACT on multiple stats
        # actTag_[0-9] tells which actions it will do, and min_ and max_ attrs
        # are the ranges for the actions
        # the whole thing looks pretty complicated for not much
        # interesting data
        eff['type'] = 'unknown effect'
        act_tag_0 = node.get('actTag_0')
        act_tag_1 = node.get('actTag_1')
        min_1 = node.get('min_1_0')
        max_1 = node.get('max_1_0')
        # FIXME: this is pretty dodgy
        if act_tag_0 == 'ACT_MIX_ADD_CATEGORY':
            assert act_tag_1 == 'ACT_NONE'
            assert min_1 == max_1
            eff['type'] = 'add_category'
            eff['value'] = min_1


def is_ingredient_of(ingredient, target):
    recipe = target.get('recipe')
    if not recipe:
        return False
    if ingredient['tag'] in recipe['ingredients']:
        return True
    cats = ingredient['categories'].union(ingredient['possible_categories'])
    for cat in cats:
        if cat in recipe['ingredients']:
            return True
    return False


def is_directly_reachable(item_a, item_b):
    if item_b['tag'] in item_a['children']:
        return True
    return is_ingredient_of(item_a, item_b)


def explain_connection(categories, item_a, item_b):
    connections = []
    if item_b['tag'] in item_a['children']:
        connections.append('derivative')
    recipe = item_b.get('recipe')
    if item_a['tag'] in recipe['ingredients']:
        connections.append('named ingredient')
    category_descriptions = [('categories', ''), ('possible_categories', '*')]
    for key, suffix in category_descriptions:
        cats = item_a[key]
        for cat in cats:
            if cat in recipe['ingredients']:
                cat_name = categories[cat]['name'].strip('()')
                connections.append(f'{cat_name}{suffix}')
    return ', '.join(connections)


def add_connections(items):
    # FIXME: parse the rings into the recipe:
    #  for eg staltium has a mod tier that's not reachable (not on rings)
    xml_path = 'saves/mix/mixfielddata.xml'
    root = open_xml(xml_path)
    for fd in root.iter('FieldData'):
        fd_tag = fd.get('tag')
        item = items[fd_tag]
        for ring in fd.iter('Ring'):
            # some docs:
            # Ring/@type:
            #  0: start ring?
            #  1: effect unlock: v: AddEff idx for material, e: element target
            #  4: v=+quality
            #  5: v=+trait slots
            #  6: change recipe
            # Ring/@restrict ="2" => use ingredient idx 2 (0 indexed)
            # Ring/@ex_material ="<item_tag>" => use special ingredient
            #                                (for child recipes, @type=6)
            # Ring/@elem: element idx: 0: Fire, 1: Ice, 2: Thunder, 3: Air
            # for type="0" and type="1":
            # Ring/Param/v[0-9]: use material's AddEff[0-9] effect when
            #                    element overfill reaches e[0-9]
            #   so <Param v0="0">
            typ = ring.get('type')
            if typ == '6':
                for param in ring.iter('Param'):
                    # strip 'ITEM_RECIPE_' prefix
                    child = param.attrib['v0'][12:]
                    item['children'].add(child)
                    items[child]['parents'].add(fd_tag)


def find_routes(items,
                this_item,
                target_item=None,
                target_category=None,
                visited=None,
                limit=5):
    assert target_item or target_category
    assert not (target_item and target_category)
    disabled = this_item.get('disabled')
    if disabled:
        return None
    if visited is None:
        visited = set()
    visited.add(this_item['tag'])

    if target_item:
        if is_directly_reachable(this_item, target_item):
            yield [this_item, target_item]
            return
    else:
        if target_category['tag'] in this_item['categories'] or \
           target_category['tag'] in this_item['possible_categories']:
            yield [this_item]
            return

    limit -= 1
    if limit <= 0:
        return None

    for tag, item in items.items():
        if tag in visited:
            continue
        if is_directly_reachable(this_item, item):
            chains = find_routes(items, item, target_item, target_category,
                                 visited.copy(), limit)
            for chain in chains:
                yield [this_item] + chain


def describe_chain(categories, chain):
    prev = None
    desc = ''
    for item in chain:
        name = item['name']
        if not prev:
            desc = name
        else:
            desc += ' ({}) -> {}'.format(
                explain_connection(categories, prev, item), name)
        prev = item
    return desc


def print_best_chains(categories, chains, limit=3, indent=''):
    scored_chains = [(len(chain), chain) for chain in chains]
    scored_chains.sort(key=lambda i: i[0])
    min_score = None
    for num, (score, chain) in enumerate(scored_chains):
        if (num + 1) >= limit:
            if min_score is None:
                min_score = score
            if score > min_score:
                break
        # print(indent + ' -> '.join(i['name'] for i in chain))
        print(indent + describe_chain(categories, chain))


def find_item(items, name):
    name = name.lower()
    for item in items.values():
        if item['name'].lower() == name:
            return item
        elif item['tag'].lower() == name:
            return item
    raise KeyError(f'item {name!r} not found')


def find_category(categories, name):
    name = name.lower().strip('()')
    for cat in categories.values():
        if cat['name'].lower().strip('()') == name:
            return cat
    raise KeyError(f'category {name!r} not found')


def disable_items(items, to_disable):
    for name in to_disable:
        item = find_item(items, name)
        item['disabled'] = True


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


def print_item(item, items, effects, categories):
    print(item['name'] + ' -- ' + item['tag'])

    cats = []
    for cat_tag in item['categories']:
        cats.append(categories[cat_tag]['name'])
    for cat_tag in item['possible_categories']:
        cats.append(categories[cat_tag]['name'] + '*')
    cats_str = ', '.join(cats) or '(none)'
    print(f'  Categories: {cats_str}')

    elems = []
    for elem in item['elements']:
        elems.append(elem.value)
    for elem in item['possible_elements']:
        elems.append(elem.value + '*')
    elems_str = ', '.join(elems) or '(none)'
    elem_range = str(item['element_value'])
    if item['add_element_value'] > 0:
        elem_range += f"+{item['add_element_value']}"
    print(f'  Elements: {elem_range} {elems_str}')

    effects_str = format_effects(item, effects)
    if effects_str:
        print(f'  Effects: {effects_str}')

    recipe = item.get('recipe')
    if recipe:
        ingredients = []
        for tag in recipe['ingredients']:
            ingredient = items.get(tag) or categories.get(tag)
            assert ingredient
            ingredients.append(ingredient['name'])
        print('  Ingredients: ' + ', '.join(ingredients))

    resolved_parents = []
    parents = item['parents']
    while parents:
        if len(parents) > 1:
            print(f'!!WARNING: got multiple parents: {parents}')
        parent = items[parents.pop()]
        resolved_parents.insert(0, parent['name'])
        parents = parent['parents']
    parents_str = ' -> '.join(resolved_parents)
    if parents_str:
        print(f'  Parents: {parents_str}')
    children = ', '.join(items[tag]['name'] for tag in item['children'])
    if children:
        print(f'  Children: {children}')
    print()


def main():
    import argparse

    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('-v', '--verbose', action='store_true')
    subparsers = main_parser.add_subparsers(dest='command')

    item_info_parser = subparsers.add_parser('items', help='item info')
    item_info_parser.add_argument('item_names', nargs='*', type=str.lower)

    item_chain_parser = subparsers.add_parser('chain', help='find craft chain')
    item_chain_parser.add_argument('source', type=str.lower)
    item_chain_parser.add_argument('target', type=str.lower)

    recipe_find_parser = subparsers.add_parser('category',
                                               help='find recipe for category')
    recipe_find_parser.add_argument('category', type=str.lower)

    subparsers.add_parser('dump-effects', help='dump effect names')

    args = main_parser.parse_args()

    # late game powerful items can mess up early game chain searches
    disabled = [
        # 'red stone',
        # 'Philosopher\'s Stone',
        # 'Crystal Element',
        # 'Holy Nut',
    ]
    effects = get_effect_tag_map()
    categories = get_category_map()
    parse_effects(effects)
    items = get_item_map()
    parse_items(items)
    parse_recipes(items, effects)
    add_connections(items)
    disable_items(items, disabled)

    if args.command == 'items':
        for item_tag, item in items.items():
            if args.item_names:
                lower_tag = item_tag.lower()
                lower_name = item['name'].lower()
                for search_string in args.item_names:
                    if search_string in lower_tag or\
                            search_string in lower_name:
                        break
                else:
                    continue
            print_item(item, items, effects, categories)
            if args.verbose:
                pprint(item)
                print()
    elif args.command == 'chain':
        source = find_item(items, args.source)
        try:
            target_item = find_item(items, args.target)
        except KeyError:
            target_item = None
        try:
            target_cat = find_category(categories, args.target)
        except KeyError:
            target_cat = None
        if not target_item and not target_cat:
            raise (KeyError(f'{args.target} not found!'))
        if target_item and target_cat:
            print('Warning: both item and category found:')
            print(target_item['name'])
            print(target_cat['name'])
            print()
            target_cat = None
        target = target_item or target_cat
        assert target
        target_name = target['name']
        print(f'Finding craft chain from {source["name"]} to {target_name}...')
        chains = find_routes(items, source, target_item, target_cat)
        print_best_chains(categories, chains)
    elif args.command == 'category':
        cat = find_category(categories, args.category)['tag']
        print('Search for category', cat)
        for item in items.values():
            if not item.get('recipe'):
                continue
            if cat in item['categories'] or cat in item['possible_categories']:
                print_item(item, items, effects, categories)
    elif args.command == 'dump-effects':
        for eff in effects.values():
            print(f'{eff["tag"]} -- {eff["name"]}')
    else:
        raise ValueError(f'unkown command {args.command}')


if __name__ == '__main__':
    main()
