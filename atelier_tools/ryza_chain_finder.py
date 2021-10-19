#!/usr/bin/env python3

from typing import Iterable, Optional

from .ryza_parser import Database, Item, Category


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
