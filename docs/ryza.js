var db;
var itemIndex;
const MAX_RESULTS = 100;
// order and icon classes
const ELEMENTS = {
  'Fire': 'atelier-ryza2-fire',
  'Ice': 'atelier-ryza2-ice',
  'Thunder': 'atelier-ryza2-lightning',
  'Air': 'atelier-ryza2-wind'
};
var popupModal;


// TODO: navigation, better formats, chain finder

function tag(tag, attributes = {}, children = []) {
  const e = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    e.setAttribute(name, value);
  }
  if (!Array.isArray(children)) {
    children = [children];
  }
  appendChildren(e, children);
  return e;
}

function appendChildren(parent, children) {
  if (!Array.isArray(children))
    children = [children];
  for (let child of children) {
    if (!(child instanceof Element)) {
      child = document.createTextNode(child)
    }
    parent.appendChild(child)
  }
  return parent
}

// cache for efficient chain finding
// to- and fromCategory are separate since we only care about categories
// when they are start or end points. Including them mid-chain would pollute
// the k-shortest paths search results
var connected, toCategory, fromCategory;
function buildChainCache() {
  if (connected)
    return;
  const conTypes = {
    BASE_CATEGORY: {cost: 0},
    EFFECT_CATEGORY: {cost: 0},
    ESSENCE_CATEGORY: {cost: 0},
    MORPH: {cost: 1},
    INGREDIENT: {cost: 1},
    CAT_INGREDIENT: {cost: 1},
    EV_LINK: {cost: 1},
  };
  for (const [idx, o] of Object.entries(conTypes).entries()) {
    o[1].name = o[0];
    o[1].sort = idx;
  }
  connected = {};
  toCategory = {};
  fromCategory = {};

  const addCon = (cons, a, b, type) => {
    if (!cons[a][b] || cons[a][b].sort > type.sort)
      cons[a][b] = type;
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
      addCon(toCategory, cat, item.tag, conTypes.BASE_CATEGORY);
    }
    for (const cat of item.possible_categories) {
      // FIXME: separate essence and normal effect unlocks
      addCon(toCategory, cat, item.tag, conTypes.EFFECT_CATEGORY);
    }
    for (const child of item.children)
      addCon(connected, item.tag, child, conTypes.MORPH);
    if (item.ev_base)
      addCon(connected, item.ev_base, item.tag, conTypes.EV_LINK);
    for (const ingredient of item.ingredients){
      if (db.categories.hasOwnProperty(ingredient))
        addCon(fromCategory, ingredient, item.tag, conTypes.INGREDIENT);
      else
        addCon(connected, ingredient, item.tag, conTypes.INGREDIENT);
    }
  }
  for (const cat of Object.keys(db.categories)) {
    const toItems = Object.keys(fromCategory[cat]);
    const fromItems = Object.keys(toCategory[cat]);
    for (const a of fromItems) {
      for (const b of toItems) {
        const con = {...conTypes.CAT_INGREDIENT, category: cat};
        addCon(connected, a, b, con);
      }
    }
  }
}

function findPathDijkstra(start, target) {
  const unvisited = new Set(Object.keys(connected));
  const distances = {};
  const prev = {}
  for (const tag of unvisited) {
    distances[tag] = Infinity;
    prev[tag] = null;
  }
  distances[start] = 0;

  while (unvisited.size) {
    let minItem = null;
    for (const i of unvisited) {
      if (minItem == null || minItem[1] > distances[i])
        minItem = [i, distances[i]];
    }
    let [current, value] = minItem;
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
  let current = target;
  if (prev[current] || current == start) {
    while (current) {
      path.unshift(current);
      current = prev[current];
    }
  }
  return path;
}

// https://en.wikipedia.org/wiki/Yen%27s_algorithm
function findPathsYen(start, target, K=5) {
  const a = [findPathDijkstra(start, target)];
  if (!a[0].length)
    return [];
  const b = [];
  let deletedNodes = {};
  const del = node => {
    if (!deletedNodes.hasOwnProperty(node))
      deletedNodes[node] = connected[node];
    connected[node] = {};
  }

  for (let k=1; k < K; k++) {
    lastA = a[a.length-1];
    for (let i=0; i < lastA.length-2; i++) {
      const spurNode = lastA[i];
      const rootPath = lastA.slice(0, i+1);

      for (const path of a) {
        if (rootPath.join() == path.slice(0, i+1).join()) {
          del([path[i+1]])
        }
      }
      for (const node of rootPath.slice(0, -1)) {
        del(node);
      }
      const spurPath = findPathDijkstra(spurNode, target);
      if (spurPath.length){
        const totalPath = rootPath.concat(spurPath.splice(1));
        const totalPathStr = totalPath.join();
        let found = false;
        for (const i of b) {
          if (totalPathStr == i[1]) {
            found = true;
            break;
          }
        }
        if (!found) {
          b.push([totalPath, totalPathStr]);
        }
      }

      for (const [node, val] of Object.entries(deletedNodes)) {
        connected[node] = val;
      }
      deletedNodes = {};
    }
    if (!b.length)
      break;
    // TODO: a sorted data structure would be a lot better
    let minCost = Infinity;
    let minPathIdx = null;
    for (let i=0; i<b.length; i++) {
      const p = b[i][0];
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
    a.push(b.splice(minPathIdx, 1)[0][0]);
  }
  return a;
}

// find the k shortest chains from start to target
function findPaths(start, target, k=5) {
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

function logChains(chains) {
  console.debug('found:')
  for (const chain of chains) {
    console.debug(chain.map(tag => (db.items[tag] || db.categories[tag]).name));
  }
}

function renderMixfield(item, recipe, mixfield, ev_lv=0) {
  // TODO: proper ring information
  const scale = 50;
  // loop radius
  const radius = 26;
  // padding for the whole image
  const padding = 10;
  const attrs = {
    'class': 'mixfield rounded mx-auto d-block',
  };
  const rings = {};
  for (const [idx, ring] of Object.entries(mixfield.rings)) {
    if (ring.ev_lv <= ev_lv)
      rings[idx] = ring;
  }
  // we adjust the viewBox to cover the image, so we don't have to
  // shift all the coordinates
  const minX = Math.min(...Object.values(rings).map(ring => ring.x));
  const maxX = Math.max(...Object.values(rings).map(ring => ring.x));
  const minY = Math.min(...Object.values(rings).map(ring => ring.y));
  const maxY = Math.max(...Object.values(rings).map(ring => ring.y));
  const viewbox = [
    (minX-1) * scale - padding,
    (minY-1) * scale - padding,
    (maxX - minX + 2) * scale + padding*2,
    (maxY - minY + 2) * scale + padding*2,
  ];
  attrs['viewBox'] = viewbox.join(' ')

  const svgTag = (name, attrs) => {
    const e = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const [k, v] of Object.entries(attrs))
      e.setAttribute(k, v);
    return e;
  }

  const svg = svgTag('svg', attrs);

  // first draw the connections
  const pathParts = [];
  for (const ring of Object.values(rings)) {
    if (ring.parent_idx === null)
      continue;
    const parent = rings[ring.parent_idx];
    const x = ring.x * scale, y = ring.y * scale;
    const px = parent.x * scale, py = parent.y * scale;
    pathParts.push(`M${x},${y}L${px},${py}`);
  }
  if (pathParts)
    svg.appendChild(svgTag('path', {'d': pathParts.join(''), 'class': 'connection'}));
  // next draw the rings
  for (const ring of Object.values(rings)){
    const cx = ring.x * scale, cy = ring.y * scale;
    const classes = ['loop', 'loop-type-' + ring.type, 'loop-elem-' + ring.element];
    if (ring.is_essential)
      classes.push('loop-essential');
    svg.appendChild(svgTag('circle', {class: classes.join(' '), cx, cy, r: radius}));
  }
  return svg;
}

function showMixfield(...args) {
  popup(tag('div', {'class': 'mixfield-container'}, [renderMixfield(...args)]));
}

function getMixfieldInfo(item) {
  let target = item;
  let ev_lv = 0;
  if (item.ev_base) {
    target = db.items[item.ev_base];
    ev_lv = 1;
  }
  if (target.recipe && target.recipe.mixfield)
    return [item, target.recipe, target.recipe.mixfield, ev_lv];
}

function renderElements(item) {
  const elems = [];
  for (const [elem, icon] of Object.entries(ELEMENTS)) {
    const normal = item['elements'].includes(elem);
    const optional = item['possible_elements'][elem];
    const active = normal || optional;
    const classes = ['elem-icon', 'icon', 'icon-lg'];
    classes.push(icon);
    classes.push((active ? 'elem-active' : 'elem-inactive'));
    const name = db['elements'][elem];
    let liAttrs = {'title': name};
    if (!active)
      liAttrs['title'] = 'No ' + name;
    if (optional) {
      liAttrs = {'class': 'optional', 'title': `${name} (from ${optional} effect)`};
    }
    elems.push(tag('li', liAttrs, [tag('span', {'class': classes.join(' ')}, [])]));
  }
  let elementValue = '' + item['element_value'];
  if (item['add_element_value'] > 0) {
    elementValue += '+' + item['add_element_value'];
  }
  return [
    tag('span', {}, [elementValue]),
    tag('ul', {'class': 'elements'}, elems)
  ];
}

function findLowestLevel(item) {
  let parents = (item['parents'] || []).map(tag => db['items'][tag]);
  return Math.min(item['level'], ...parents.map(findLowestLevel));
}

function popup(contents) {
  const body = document.querySelector('#item-popup .modal-body');
  body.innerHTML = '';
  body.appendChild(contents);
  popupModal.show();
}

function itemPopup(item) {
  console.debug(item);
  popup(renderItem(item));
}

function link(target, popup=true) {
  if (target.tag)
    target = target.tag;
  const types = {
    'item': db.items,
    'category': db.categories,
    'effect': db.effects,
  };
  let type = 'unknown';
  let value = null;
  for (const [k, v] of Object.entries(types)) {
    value = v[target];
    if (value) {
      type = k;
      break;
    }
  }
  const attrs = {
    'class': `link-${type}`,
    'data-link-type': type,
    'data-link-tag': target,
  };
  if (value.description)
    attrs['title'] = value.description;
  if (popup && type == 'item') {
    attrs['href'] = '#';
    const elem = tag('a', attrs, [value.name]);
    elem.addEventListener('click', e => {
      e.preventDefault();
      itemPopup(db.items[target]);
    });
    return elem;
  }else {
    return tag('span', attrs, [value.name]);
  }
}

function renderItem(item) {
  const elems = [];
  const miscInfo = [
    'Lv' + item['level'],
    'MinLv' + findLowestLevel(item),
    '$' + item['price'],
  ].map(i => tag('li', {}, [i]));
  const heading = tag('div', {'class': 'card-body'}, [
    tag('h5', {'class': 'card-title'}, [
      link(item, false),
    ]),
    tag('h6', {'class': 'card-subtitle muted'}, [
      item['tag'],
      tag('ul', {'class': 'misc-info inline-list'}, miscInfo)
    ]),
  ]);
  const addRow = (label, contents) => {
    elems.push(tag('dt', {'class': 'col-sm-3'}, [label]));
    elems.push(tag('dd', {'class': 'col-sm-9'}, contents));
  };

  const cats = [];
  for (const [key, cls] of [['categories'], ['possible_categories', 'optional']]) {
    const attrs = {};
    if (cls)
      attrs['class'] = cls;
    for (const cat of item[key]) {
      cats.push(tag('li', {}, [
        tag('span', attrs, [db['categories'][cat]['name']])
      ]));
    }
  }
  addRow('Categories', tag('ul', {'class': 'inline-list'}, cats));

  addRow('Elements', renderElements(item));

  const effects = [];
  for (const group of Object.values(item['effects'])) {
    const keys = Object.keys(group)
    if (!keys.length)
      break;
    keys.sort((a, b) => b-a);
    const effTag = group[keys[0]]['effect'];
    effects.push(db['effects'][effTag]);
  }
  if (effects.length) {
    effects.sort((a, b) => a.name_id < b.name_id);
    const tags = effects.map(i => tag('li', {}, [link(i)]));
    addRow('Effects', tag('ul', {'class': 'inline-list effects'}, tags));
  }
  ingredients = item['ingredients'];
  if (ingredients.length) {
    const tags = ingredients.map(ingTag => tag('li', {}, [link(ingTag)]));
    addRow('Ingredients', tag('ul', {'class': 'inline-list ingredients'}, tags));
    const mixfieldParams = getMixfieldInfo(item);
    if (mixfieldParams) {
      const mixfieldButton = tag('button', {'class': 'btn btn-primary'}, 'Show');
      addRow('Loops', mixfieldButton);
      mixfieldButton.addEventListener('click', () => showMixfield(...mixfieldParams));
      // elems.push(tag('div', {'class': 'col-sm-12'}, [renderMixfield(item)]))
    }
  }

  // TODO: handle ev-link relations
  const parentsList = [];
  let parents = item['parents'];
  while (parents && parents.length) {
    if (parents.length > 1)
      console.warn(`Too many parents for ${item['tag']}`);
    const parent = db['items'][parents[0]];
    parentsList.unshift(parent);
    parents = parent['parents'];
  }
  if (parentsList.length) {
    const tags = parentsList.map(i => tag('li', {}, link(i)));
    addRow('Parents', tag('ul', {'class': 'inline-list parents'}, tags));
  }

  const children = item['children'].map(i => tag('li', {}, [link(i)]));
  if (children.length) {
    addRow('Children', tag('ul', {'class': 'inline-list children'}, children));
  }

  if (item.ev_base) {
    const base = db.items[item.ev_base];
    const mat = db.items[base.recipe.ev_extend_mat];
    const items = [base, mat].map(ingredient => {
      return tag('li', {}, [link(ingredient)])
    });
    addRow('EV-link from', tag('ul', {'class': 'inline-list'}, items));
  }

  if (item.gathering)
    addRow('Gather', item.gathering);
  if (item.shop_data)
    addRow('Shop', item.shop_data);
  if (item.seed)
    addRow('From seed', link(item.seed));
  const forged = item.forge_effects.map(group => {
    const last = group[group.length-1];
    return tag('li', {}, [link(last.forged_effect)]);
  });
  if (forged)
    addRow('Forging', tag('ul', {'class': 'inline-list effects'}, forged))

  const chainOptions = ["start"];
  if (item.recipe || item.ev_base) {
    chainOptions.push('goal')
  }
  const buttons = chainOptions.map(i => {
    const button = tag('button', {'class': 'btn btn-primary m-1'}, ['Set as ' + i]);
    button.addEventListener('click', () => setChain(i, item));
    return button;
  });
  addRow('Chain', tag('div', {}, buttons))

  return tag('div', {'class': 'card', 'data-tag': item['tag']}, [
    heading,
    tag('dl', {'class': 'card-body row'}, elems),
  ]);
}

var chainStart, chainGoal;
function setChain(startOrGoal, thing) {
  if (startOrGoal == 'start')
    chainStart = thing;
  else
    chainGoal = thing;
  updateChainSettings();
}

function updateChainSettings() {
  const container = document.getElementById('chain-container')
  if (chainStart || chainGoal) {
    container.style.display = 'block';
  } else {
    container.style.display = 'none';
  }
  const startDiv = document.getElementById('chain-start');
  const goalDiv = document.getElementById('chain-goal');
  for (const [e, value, type] of [[startDiv, chainStart, 'start'], [goalDiv, chainGoal, 'goal']]) {
    if (value) {
      const itemButton = tag('button', {'class': 'btn btn-primary'}, [value.name]);
      const removeButton = tag('button', {'class': 'btn btn-danger', 'title': 'Remove'}, ['🗑️']);
      itemButton.addEventListener('click', () => itemPopup(value));
      removeButton.addEventListener('click', () => {
        setChain(type, null);
      });
      const content = tag('div', {'class': 'btn-group'}, [
        itemButton,
        removeButton,
      ]);
      e.innerHTML = '';
      e.appendChild(content);
    } else {
      e.innerText = '(none)';
    }
  }
  const goButton = document.getElementById('find-chains-button');
  if (chainStart && chainGoal)
    goButton.disabled = false;
  else
    goButton.disabled = true;
}

function renderConnection(a, b) {
  const arrow = '➡';
  if (db.categories.hasOwnProperty(a.tag)) {
    // must be start of chain, it has to be CAT_INGREDIENT
    return [arrow];
  } else if (db.categories.hasOwnProperty(b.tag)) {
    // end of chain, might be of BASE_CATEGORY, EFFECT_CATEGORY, ESSENCE_CATEGORY
    // FIXME
    return [arrow];
  }
  console.debug(a.tag, b.tag)
  const con = connected[a.tag][b.tag];
  switch (con.name) {
    case 'MORPH':
      return [' (recipe morph) ', arrow];
    case 'INGREDIENT':
      return [arrow];
    case 'CAT_INGREDIENT':
      const cat = db.categories[con.category];
      return [cat.name, arrow];
    case 'EV_LINK':
      return [' (EV-link) ', arrow];
    default:
      console.warn(`unhandled connection type ${con.type}!`);
  }
  return [arrow];
}

function findChains() {
  if (!chainStart || !chainGoal) {
    alert('A chain endpoint is missing!')
    return;
  }
  const resultsList = document.getElementById('chain-results');
  resultsList.innerHTML = '';
  const chains = findPaths(chainStart.tag, chainGoal.tag);
  console.debug(chains);
  if (!chains.length) {
    resultsList.appendChild(tag('li', {'class': 'list-group-item text-danger'}, ['No chains found!']));
  }
  for (const chain of chains) {
    console.debug(chain.join(' > '));
    const items = [];
    let prev = null;
    for (const thingTag of chain) {
      const thing = db.items[thingTag] || db.categories[thingTag];
      if (prev) {
        items.push(...renderConnection(prev, thing));
      }
      items.push(tag('button', {'class': 'btn btn-secondary m-2'}, [thing.name]));
      prev = thing;
    }
    resultsList.appendChild(tag('li', {'class': 'list-group-item p-2 d-flex flex-wrap align-items-center justify-contents-center'}, items));
  }
}

function update() {
  if (!db)
    return;
  console.debug('ready');
  const resultCountLabel = document.getElementById('result-count');
  resultCountLabel.innerText = 'Searching...';
  const nameQuery = document.getElementById('name-input').value.trim().toUpperCase();
  const effectQuery = document.getElementById('effect-input').value.trim().toUpperCase();
  let results = [];
  const resultDiv = document.getElementById('results');
  const neededElements = [];
  resultDiv.innerHTML = '';
  for (const cb of document.querySelectorAll('input.element')) {
    if (cb.checked) {
      neededElements.push(cb.value);
    }
  }
  outer_loop: for (const [item, itemHaystacks, effectHaystacks] of itemIndex) {
    if (nameQuery) {
      let found = false;
      for (const haystack of itemHaystacks) {
        if (haystack.includes(nameQuery)) {
          found = true;
          break;
        }
      }
      if (!found)
        continue outer_loop;
    }
    if (effectQuery) {
      let found = false;
      for (const haystack of effectHaystacks) {
        if (haystack.includes(effectQuery)) {
          found = true;
          break;
        }
      }
      if (!found)
        continue outer_loop;
    }
    for (const element of neededElements) {
      if (!(item['elements'].includes(element) || item['possible_elements'][element]))
        continue outer_loop;
    }
    results.push(item);
    resultDiv.appendChild(renderItem(item));
    if (results.length >= MAX_RESULTS) {
      console.warn('maximum number of results reached');
      break;
    }
  }
  if (results.length >= MAX_RESULTS)
    resultCountLabel.innerText = `${results.length}+ found`;
  else
    resultCountLabel.innerText = `${results.length} found`;
  console.debug(`found ${results.length} items`);
}

function buildIndex() {
  itemIndex = [];
  for (const item of Object.values(db.items)) {
    const record = [item];
    // item + group index
    {
      const strings = [];
      strings.push(item['name'].toUpperCase());
      strings.push(item['tag']);
      const cats = item['categories'].concat(item['possible_categories'])
      for (const catTag of cats) {
        strings.push(catTag);
        strings.push(db['categories'][catTag]['name'].toUpperCase());
      }
      record.push(strings);
    }
    // effect index
    {
      const strings = [];
      for (const group of Object.values(item['effects'])) {
        for (const effSpec of Object.values(group)) {
          strings.push(effSpec.effect);
          strings.push(db.effects[effSpec.effect].name.toUpperCase());
        }
      }
      for (const group of item.forge_effects) {
        for (const forgeEffect of group) {
          strings.push(forgeEffect.forged_effect);
          strings.push(db.effects[forgeEffect.forged_effect].name.toUpperCase());
        }
      }
      record.push(strings);
    }
    itemIndex.push(record);
  }
  effectIndex = [];
  for (const item of Object.values(db.items)) {
    const strings = [];
    for (const group of Object.values(item['effects'])) {
      for (const effSpec of Object.values(group)) {
        strings.push(effSpec.effect);
        strings.push(db.effects[effSpec.effect].name);
      }
    }
    for (const group of item.forge_effects) {
      for (const forgeEffect of group) {
        strings.push(forgeEffect.forged_effect);
        strings.push(db.effects[forgeEffect.forged_effect].name);
      }
    }
    effectIndex.push(strings);
  }
}

function gameChanged() {
  const gameInput = document.getElementById('game-input');
  db = null;
  fetch(gameInput.value).then(async response => {
    db = await response.json();
    buildIndex();
    update();
    buildChainCache();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const gameInput = document.getElementById('game-input');
  popupModal = new bootstrap.Modal(document.getElementById('item-popup'));
  gameInput.addEventListener('change', gameChanged)
  gameChanged();
  for (const input of document.querySelectorAll('#search-bar input')) {
    input.addEventListener('input', update);
  }
  document.getElementById('find-chains-button').addEventListener('click', findChains);
  document.getElementById('chain-swap-button').addEventListener('click', () => {
    [chainGoal, chainStart] = [chainStart, chainGoal];
    updateChainSettings();
  });
  document.getElementById('clear-chains-button').addEventListener('click', () => {
    document.getElementById('chain-results').innerHTML = '';
    updateChainSettings();
  });
});
