import {Database} from "./DBTypes";

interface Connection {
  sort: number;
  cost: number;
  description: string;
}

const conTypes: Connection[] = [];

function addConnectionType(cost: number, description: string) {
  const sort = conTypes.length;
  const connection: Connection = {sort, cost, description};
  conTypes.push(connection);
  return connection;
}

const CON_BASE_CATEGORY = addConnectionType(0, '(base category)');
const CON_EFFECT_CATEGORY = addConnectionType(0, '(effect category)');
// TODO: use this for marking essence-only categories
//const CON_ESSENCE_CATEGORY = addConnectionType(0, '(essence category)');
const CON_MORPH = addConnectionType(1, '(morph)');
const CON_INGREDIENT = addConnectionType(1, '(named ingredient)');
const CON_CAT_INGREDIENT = addConnectionType(1, '(ingredient)');
const CON_EV_LINK = addConnectionType(1, '(EV-link)');

// cache for efficient chain finding
// to- and fromCategory are separate since we only care about categories
// when they are start or end points. Including them mid-chain would pollute
// the k-shortest paths search results
type ConnectionMap = {[key: string]: {[key: string]: Connection}};
let connected: ConnectionMap;
let toCategory: ConnectionMap;
let fromCategory: ConnectionMap;

export function buildChainCache(db: Database) {
  if (connected)
    return;
  connected = {};
  toCategory = {};
  fromCategory = {};

  const addCon = (cons: ConnectionMap, a: string, b: string, type_: Connection) => {
    if (!cons[a][b] || cons[a][b].sort > type_.sort)
      cons[a][b] = type_;
  }

  for (const tag of Object.keys(db.items)) {
    connected[tag] = {}
  }
  for (const tag of Object.keys(db.categories)) {
    toCategory[tag] = {}
    fromCategory[tag] = {}
  }

  for (const item of Object.values(db.items)) {
    for (const cat of item.categories) {
      addCon(toCategory, cat, item.tag, CON_BASE_CATEGORY);
    }
    for (const cat of item.possible_categories) {
      // FIXME: separate essence and normal effect unlocks
      addCon(toCategory, cat, item.tag, CON_EFFECT_CATEGORY);
    }
    for (const child of item.children)
      addCon(connected, item.tag, child, CON_MORPH);
    if (item.ev_base)
      addCon(connected, item.ev_base, item.tag, CON_EV_LINK);
    for (const ingredient of item.ingredients){
      if (db.categories.hasOwnProperty(ingredient))
        addCon(fromCategory, ingredient, item.tag, CON_INGREDIENT);
      else
        addCon(connected, ingredient, item.tag, CON_INGREDIENT);
    }
  }
  for (const [tag, cat] of Object.entries(db.categories)) {
    const toItems = Object.keys(fromCategory[tag]);
    const fromItems = Object.keys(toCategory[tag]);
    for (const a of fromItems) {
      for (const b of toItems) {
        const con = {...CON_CAT_INGREDIENT, description: cat.name};
        addCon(connected, a, b, con);
      }
    }
  }
}

function findPathDijkstra(start: string, target: string): string[] {
  const unvisited = new Set<string>(Object.keys(connected));
  const distances: {[tag: string]: number} = {};
  const prev: {[tag: string]: string | null} = {}
  for (const tag of unvisited) {
    distances[tag] = Infinity;
    prev[tag] = null;
  }
  distances[start] = 0;

  while (unvisited.size) {
    let minItem: [string, number] | null = null;
    for (const i of unvisited) {
      if (!minItem || minItem[1] > distances[i])
        minItem = [i, distances[i]];
    }
    let [current, value] = minItem!;
    unvisited.delete(current);
    if (current == target)
      break;

    for (const [next, con] of Object.entries(connected[current])) {
      if (!unvisited.has(next))
        continue;
      const d = value + con.cost;
      if (d < distances[next]) {
        distances[next] = d;
        prev[next] = current;
      }
    }
  }
  const path = [];
  let current: string | null = target;
  if (prev[current] || current == start) {
    while (current) {
      path.unshift(current);
      current = prev[current];
    }
  }
  return path;
}

// https://en.wikipedia.org/wiki/Yen%27s_algorithm
function findPathsYen(start: string, target: string, K=5) {
  const bestPaths = [findPathDijkstra(start, target)];
  if (!bestPaths[0].length)
    return [];
  const candidates: [string[], string][] = [];
  let deletedNodes: {[node: string]: any} = {};
  let deletedEdges: {[key: string]: any} = {};

  for (let k=1; k < K; k++) {
    const lastA = bestPaths[bestPaths.length-1];
    for (let i=0; i < lastA.length-2; i++) {
      const spurNode = lastA[i];
      const rootPath = lastA.slice(0, i+1);

      for (const path of bestPaths) {
        if (rootPath.join() == path.slice(0, i+1).join()) {
          const key = [path[i], path[i+1]];
          if (!deletedEdges.hasOwnProperty(key.toString()))
            deletedEdges[key.toString()] = [key, connected[key[0]][key[1]]];
          delete connected[key[0]][key[1]];
        }
      }
      for (const node of rootPath.slice(0, -1)) {
        if (!deletedNodes.hasOwnProperty(node))
          deletedNodes[node] = connected[node];
        connected[node] = {};
      }

      const spurPath = findPathDijkstra(spurNode, target);

      for (const [node, val] of Object.entries(deletedNodes))
        connected[node] = val;
      for (const [key, val] of Object.values(deletedEdges))
        connected[key[0]][key[1]] = val;
      deletedNodes = {};
      deletedEdges = {};

      if (spurPath.length){
        const totalPath = rootPath.concat(spurPath.splice(1));
        const totalPathStr = totalPath.join();
        let found = false;
        for (const i of candidates) {
          if (totalPathStr == i[1]) {
            found = true;
            break;
          }
        }
        if (!found) {
          candidates.push([totalPath, totalPathStr]);
        }
      }
    }
    if (!candidates.length)
      break;
    // TODO: a sorted data structure would be a lot better
    let minCost = Infinity;
    let minPathIdx = null;
    for (let i=0; i<candidates.length; i++) {
      const p = candidates[i][0];
      let cost = 0
      let current = p[0];
      for (const next of p.slice(1)) {
        cost += connected[current][next].cost;
        current = next;
      }
      if (cost < minCost) {
        minCost = cost;
        minPathIdx = i;
      }
    }
    bestPaths.push(candidates.splice(minPathIdx!, 1)[0][0]);
  }
  return bestPaths;
}

// find the k shortest chains from start to target
export function findPaths(db: Database, start: string, target: string, k=5) {
  // if that start or target are categories, enable them
  if (db.categories.hasOwnProperty(start)) {
    connected[start] = fromCategory[start];
  }
  if (db.categories.hasOwnProperty(target)) {
    // need to add this for the path finder to ever consider the node
    connected[target] = {}
    for (const [item, con] of Object.entries(toCategory[target]))
      connected[item][target] = con;
  }
  const results = findPathsYen(start, target, k);
  // restore the base connection graph
  if (db.categories.hasOwnProperty(start)) {
    delete connected[start];
  }
  if (db.categories.hasOwnProperty(target)) {
    delete connected[target];
    for (const item of Object.keys(toCategory[target]))
      delete connected[item][target];
  }
  return results;
}

export function logChains(db: Database, chains: string[][]) {
  console.debug('found:')
  for (const chain of chains) {
    console.debug(chain.map(tag => (db.items[tag] || db.categories[tag]).name));
  }
}

export function describeConnection(a: string, b: string): string {
  return connected[a][b].description;
}
