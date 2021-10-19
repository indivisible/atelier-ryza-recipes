#!/usr/bin/env python3

from collections import defaultdict
from typing import Generator, NamedTuple
import heapq

from .ryza_parser import Database, Category


class ConnectionType(NamedTuple):
    # used for deciding which connection to store in cache
    sort: int
    cost: int = 1
    description: str = ''


class Connection:
    BASE_CATEGORY = ConnectionType(0, 0, '(base category)')
    EFFECT_CATEGORY = ConnectionType(1, 0, '(effect category)')
    ESSENCE_CATEGORY = ConnectionType(2, 0, '(essence category)')
    MORPH = ConnectionType(3, 1, '(morph)')
    INGREDIENT = ConnectionType(4, 1, '(named ingredient)')
    CAT_INGREDIENT = ConnectionType(5, 1, '(ingredient)')
    EV_LINK = ConnectionType(6, 1, '(EV-link)')


Path = tuple[str, ...]


class ChainFinder:
    db: Database
    # connection cache, normally Item -> Item connections
    connections: dict[str, dict[str, ConnectionType]]
    # Category -> Item connections
    to_category: dict[str, dict[str, ConnectionType]]
    # Item -> Category connections
    from_category: dict[str, dict[str, ConnectionType]]

    def __init__(self, db: Database):
        self.db = db
        # not a defaultdict, so we can keep track of all item tags with it
        cons = self.connections = {}
        # NOTE: this is basically reversed compared to cons:
        # to_cat[A][B] means a connection B (item) -> A (category)
        to_cat = self.to_category = defaultdict(dict)
        from_cat = self.from_category = defaultdict(dict)

        # build the cache
        def add_con(cons, a: str, b: str, con: ConnectionType):
            if b not in cons[a] or cons[a][b].sort > con.sort:
                cons[a][b] = con

        for tag in db.items.keys():
            cons[tag] = {}

        for tag, item in db.items.items():
            for cat in item.categories:
                add_con(to_cat, cat.tag, tag, Connection.BASE_CATEGORY)
            for cat in item.possible_categories:
                add_con(to_cat, cat.tag, tag, Connection.EFFECT_CATEGORY)
            for child in item.children:
                add_con(cons, tag, child.tag, Connection.MORPH)
            if item.ev_base:
                add_con(cons, item.ev_base.tag, tag, Connection.EV_LINK)
            for ing in item.ingredients:
                if isinstance(ing, Category):
                    add_con(from_cat, ing.tag, tag, Connection.CAT_INGREDIENT)
                else:
                    add_con(cons, ing.tag, tag, Connection.INGREDIENT)
        for tag, cat in db.categories.items():
            to_items = list(from_cat[tag].keys())
            from_items = list(to_cat[tag].keys())
            for a in from_items:
                for b in to_items:
                    con = Connection.CAT_INGREDIENT._replace(
                        description=cat.name)
                    add_con(cons, a, b, con)

    def _find_path_dijkstra(self, start: str,
                            target: str) -> tuple[float, Path]:
        dists: dict[str, float] = defaultdict(lambda: float('inf'))
        dists[start] = 0
        queue = [(0, start, tuple())]
        visited: set[str] = set()

        while queue:
            cost, a, path = heapq.heappop(queue)
            if a in visited:
                continue
            visited.add(a)
            path = path + (a, )
            if a == target:
                return (cost, path)

            for b, con in self.connections[a].items():
                if b in visited:
                    continue
                dist = dists[b]
                new = cost + con.cost
                if new < dist:
                    dists[b] = new
                    heapq.heappush(queue, (new, b, path))
        return (float('inf'), tuple())

    def _find_paths_yen(self,
                        start: str,
                        target: str,
                        limit: int = 10) -> Generator[Path, None, None]:
        best_paths: list[Path] = [self._find_path_dijkstra(start, target)[1]]
        if not best_paths[0]:
            return None
        # FIXME: while generators are cool, we have some very delicate
        # shared state stored in `self`, so it's pretty unsafe
        yield best_paths[0]
        candidates: list[tuple[float, Path]] = []
        candidates_set: set[Path] = set()

        deleted_connections: dict[tuple[str, str], ConnectionType] = {}
        deleted_nodes: dict[str, dict[str, ConnectionType]] = {}

        for _ in range(1, limit):
            # len(...)-1: we don't want to delete the target node
            for i in range(len(best_paths[-1]) - 1):
                spur = best_paths[-1][i]
                root_path = best_paths[-1][:i + 1]

                for path in best_paths:
                    if root_path == path[:i + 1]:
                        # do not go down a path we already visited
                        a = path[i]
                        b = path[i + 1]
                        key = (a, b)
                        if key not in deleted_connections:
                            deleted_connections[key] = self.connections[a][b]
                            del self.connections[a][b]
                for node in root_path[:-1]:
                    # no looping back
                    if node not in deleted_nodes:
                        deleted_nodes[node] = self.connections[node]
                    self.connections[node] = {}

                _, spur_path = self._find_path_dijkstra(spur, target)

                # undelete the disabled nodes
                for node, cons in deleted_nodes.items():
                    self.connections[node] = cons
                deleted_nodes = {}
                for key, cons in deleted_connections.items():
                    a, b = key
                    self.connections[a][b] = cons
                deleted_connections = {}

                if spur_path:
                    path = root_path[:-1] + spur_path
                    if path in candidates_set:
                        continue
                    cost = 0
                    for node_a, node_b in zip(path, path[1:]):
                        cost += self.connections[node_a][node_b].cost
                    heapq.heappush(candidates, (cost, path))
                    candidates_set.add(path)
            if not candidates:
                break
            path = heapq.heappop(candidates)[1]
            candidates_set.remove(path)
            best_paths.append(path)
            yield path

    def print_paths(self, start: str, target: str, limit: int = 10) -> None:
        if start in self.from_category:
            self.connections[start] = self.from_category[start]

        if target in self.to_category:
            self.connections[target] = {}
            for item, con in self.to_category[target].items():
                self.connections[item][target] = con

        paths = self._find_paths_yen(start, target, limit)
        for path in paths:
            parts = []
            prev = None
            for node in path:
                thing = self.db.items.get(node) or self.db.categories[node]
                if prev:
                    desc = self.connections[prev][node].description
                    parts[-1] += ' ' + desc
                parts.append(thing.name)
                prev = node
            print(' -> '.join(parts))

        if start in self.from_category:
            del self.connections[start]

        if target in self.to_category:
            del self.connections[target]
            for item, con in self.to_category[target].items():
                del self.connections[item][target]
