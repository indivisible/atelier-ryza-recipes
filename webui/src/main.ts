import {Category, Database, EVEffect, Item, Mixfield, MixfieldRing, Recipe} from './DBTypes';
import {tag, Attrs, TagChildren} from './tag';
import {buildChainCache, describeConnection, findPaths} from './chainFinder';

type Maybe<T> = T | null;

let db: Maybe<Database> = null;
let itemIndex: [Item, string[], string[]][];
const MAX_RESULTS = 100;
// order and icon classes
const ELEMENTS = {
  'Fire': 'atelier-ryza2-fire',
  'Ice': 'atelier-ryza2-ice',
  'Thunder': 'atelier-ryza2-lightning',
  'Air': 'atelier-ryza2-wind'
};
let popupModal: bootstrap.Modal;


// TODO: navigation, better formats, chain finder



function renderMixfield(item: Item, recipe: Recipe, mixfield: Mixfield, ev_lv=0) {
  // TODO: proper ring information
  const scale = 50;
  // loop radius
  const radius = 26;
  // padding for the whole image
  const padding = 10;
  const attrs: Attrs = {
    'class': 'mixfield rounded mx-auto d-block',
  };
  const rings: {[idx: string]: MixfieldRing} = {};
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

  const svgTag = (name: string, attrs: {[key: string]: string | number}) => {
    const e = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (const [k, v] of Object.entries(attrs))
      e.setAttribute(k, v.toString());
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

function showMixfield(...args: Parameters<typeof renderMixfield>) {
  popup(tag('div', {'class': 'mixfield-container'}, [renderMixfield(...args)]));
}

function getMixfieldInfo(item: Item): [Item, Recipe, Mixfield, number] | null {
  let target = item;
  let ev_lv = 0;
  if (item.ev_base) {
    target = db!.items[item.ev_base];
    ev_lv = 1;
  }
  if (target.recipe && target.recipe.mixfield)
    return [item, target.recipe, target.recipe.mixfield, ev_lv];
  return null;
}

function renderElements(item: Item) {
  const elems = [];
  for (const [elem, icon] of Object.entries(ELEMENTS)) {
    const normal = item['elements'].includes(elem);
    const optional = item['possible_elements'][elem];
    const active = normal || optional;
    const classes = ['elem-icon', 'icon', 'icon-lg'];
    classes.push(icon);
    classes.push((active ? 'elem-active' : 'elem-inactive'));
    const name = db!.elements[elem];
    let liAttrs: Attrs = {'title': name};
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

function findLowestLevel(item: Item): number {
  const parents = (item.parents || []).map(tag => db!.items[tag]);
  return Math.min(item.level, ...parents.map(findLowestLevel));
}

function popup(contents: Element) {
  const body = document.querySelector('#item-popup .modal-body')!;
  body.innerHTML = '';
  body.appendChild(contents);
  popupModal.show();
}

function itemPopup(item: Item) {
  popup(renderItem(item));
}

function popupThing(tag: string) {
  if (db!.items[tag]) {
    itemPopup(db!.items[tag]);
  } else {
    console.warn(`unknown popup thing: ${tag}`);
  }
}

function link(target: string, popup=true) {
  const types = {
    'item': db!.items,
    'category': db!.categories,
    'effect': db!.effects,
    'ev_effect': db!.ev_effects,
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
  if (value === null) {
    const msg = `Error: ${target} not found!`;
    throw msg;
  }
  const attrs: Attrs = {
    'class': `link-${type}`,
    'data-link-type': type,
    'data-link-tag': target,
  };
  if (value.description)
    attrs['title'] = value.description;
  if (type == 'ev_effect')
    attrs['title'] = (value as EVEffect).effects.map(i => db!.effects[i].name).join(', ');
  if (popup && type == 'item') {
    attrs['href'] = '#';
    const elem = tag('a', attrs, [value.name]);
    elem.addEventListener('click', e => {
      e.preventDefault();
      itemPopup(db!.items[target]);
    });
    return elem;
  }else {
    return tag('span', attrs, [value.name]);
  }
}

function renderItem(item: Item) {
  const elems: Element[] = [];
  const miscInfo = [
    'Lv' + item['level'],
    'MinLv' + findLowestLevel(item),
    '$' + item['price'],
  ].map(i => tag('li', {}, [i]));
  const heading = tag('div', {'class': 'card-body'}, [
    tag('h5', {'class': 'card-title'}, [
      link(item.tag, false),
    ]),
    tag('h6', {'class': 'card-subtitle muted'}, [
      item['tag'],
      tag('ul', {'class': 'misc-info inline-list'}, miscInfo)
    ]),
  ]);
  const addRow = (label: string, contents: TagChildren) => {
    elems.push(tag('dt', {'class': 'col-sm-3'}, [label]));
    elems.push(tag('dd', {'class': 'col-sm-9'}, contents));
  };

  const cats = [];
  const catDefs: [string[], string][] = [[item.categories, ''], [item.possible_categories, 'optional']];
  for (const [container, cls] of catDefs) {
    const attrs: Attrs = {};
    if (cls)
      attrs['class'] = cls;
    for (const cat of container) {
      cats.push(tag('li', {}, [
        tag('span', attrs, [db!.categories[cat].name])
      ]));
    }
  }
  addRow('Categories', tag('ul', {'class': 'inline-list'}, cats));

  addRow('Elements', renderElements(item));

  const effects = [];
  for (const group of Object.values(item.effects)) {
    const keys = Object.keys(group);
    if (!keys.length)
      break;
    keys.sort((a, b) => parseInt(b)-parseInt(a));
    const effTag = group[keys[0]].effect;
    effects.push(db!.effects[effTag]);
  }
  if (effects.length) {
    effects.sort((a, b) => a.name_id - b.name_id);
    const tags = effects.map(i => tag('li', {}, [link(i.tag)]));
    addRow('Effects', tag('ul', {'class': 'inline-list effects'}, tags));
  }
  if (item.ingredients.length) {
    const tags = item.ingredients.map(ingTag => tag('li', {}, [link(ingTag)]));
    addRow('Ingredients', tag('ul', {'class': 'inline-list ingredients'}, tags));
    const mixfieldParams = getMixfieldInfo(item);
    if (mixfieldParams) {
      const mixfieldButton = tag('button', {'class': 'btn btn-primary'}, 'Show');
      addRow('Loops', mixfieldButton);
      mixfieldButton.addEventListener('click', () => showMixfield(...mixfieldParams));
    }
  }

  // TODO: handle ev-link relations
  const parentsList = [];
  let parents = item['parents'];
  while (parents && parents.length) {
    if (parents.length > 1)
      console.warn(`Too many parents for ${item['tag']}`);
    const parent = db!.items[parents[0]];
    parentsList.unshift(parent);
    parents = parent['parents'];
  }
  if (parentsList.length) {
    const tags = parentsList.map(i => tag('li', {}, link(i.tag)));
    addRow('Parents', tag('ul', {'class': 'inline-list parents'}, tags));
  }

  const children = item['children'].map(i => tag('li', {}, [link(i)]));
  if (children.length) {
    addRow('Children', tag('ul', {'class': 'inline-list children'}, children));
  }

  if (item.ev_base) {
    const base = db!.items[item.ev_base];
    const mat = db!.items[base.recipe!.ev_extend_mat!];
    const items = [base, mat].map(ingredient => {
      return tag('li', {}, [link(ingredient.tag)])
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
  if (forged.length)
    addRow('Forging', tag('ul', {'class': 'inline-list effects'}, forged))

  const ev_effects: Element[] = [];

  for (const effs of Object.values(item.ev_effects)) {
    for (let idx = effs.length - 1; idx >= 0; idx--) {
      const eff = effs[idx];
      const ev_eff = db!.ev_effects[eff];
      if (ev_eff.effects.length)
        ev_effects.push(tag('li', {}, [link(eff)]));
      //else
      //  console.debug('no effects for ev effect:', ev_eff);
    }
  }
  if (ev_effects.length)
    addRow('EV effects', tag('ul', {'class': 'inline-list'}, ev_effects));

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

type ChainItem = Item | Category;
let chainStart: Maybe<ChainItem> = null, chainGoal: Maybe<ChainItem> = null;
function setChain(startOrGoal: string, thing: Maybe<ChainItem>) {
  if (startOrGoal == 'start')
    chainStart = thing;
  else
    chainGoal = thing;
  updateChainSettings();
}

function updateChainSettings() {
  const container = document.getElementById('chain-container')!;
  if (chainStart || chainGoal) {
    container.style.display = 'block';
  } else {
    container.style.display = 'none';
  }
  const startDiv = document.getElementById('chain-start')!;
  const goalDiv = document.getElementById('chain-goal')!;
  const ends: [HTMLElement, Maybe<ChainItem>, string][] = [[startDiv, chainStart, 'start'], [goalDiv, chainGoal, 'goal']];
  for (const [e, value, type] of ends) {
    if (value) {
      const itemButton = tag('button', {'class': 'btn btn-primary'}, [value.name]);
      const removeButton = tag('button', {'class': 'btn btn-danger', 'title': 'Remove'}, ['🗑️']);
      // FIXME: this only works on items
      itemButton.addEventListener('click', () => itemPopup(value as Item));
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
  const goButton = document.getElementById('find-chains-button') as HTMLButtonElement;
  if (chainStart && chainGoal)
    goButton.disabled = false;
  else
    goButton.disabled = true;
}

function renderConnection(a: ChainItem, b: ChainItem) {
  const arrow = '➡';
  if (db!.categories.hasOwnProperty(a.tag)) {
    // must be start of chain, it has to be CAT_INGREDIENT
    return [arrow];
  } else if (db!.categories.hasOwnProperty(b.tag)) {
    // end of chain, might be of BASE_CATEGORY, EFFECT_CATEGORY, ESSENCE_CATEGORY
    // FIXME
    return [arrow];
  }
  const label = describeConnection(a.tag, b.tag);
  return [label, arrow];
}

function findChains() {
  if (!chainStart || !chainGoal) {
    alert('A chain endpoint is missing!')
    return;
  }
  const resultsList = document.getElementById('chain-results')!;
  resultsList.innerHTML = '';
  const chains = findPaths(db!, chainStart.tag, chainGoal.tag);
  if (!chains.length) {
    resultsList.appendChild(tag('li', {'class': 'list-group-item text-danger'}, ['No chains found!']));
  }
  for (const chain of chains) {
    const items = [];
    let prev = null;
    for (const thingTag of chain) {
      const thing = db!.items[thingTag] || db!.categories[thingTag];
      if (prev) {
        items.push(...renderConnection(prev, thing));
      }
      const button = tag('button', {'class': 'btn btn-secondary m-2'}, [thing.name]);
      items.push(button);
      button.addEventListener('click', () => popupThing(thingTag))
      prev = thing;
    }
    resultsList.appendChild(tag('li', {'class': 'list-group-item p-2 d-flex flex-wrap align-items-center justify-contents-center'}, items));
  }
}

function update() {
  if (!db)
    return;
  console.debug('ready');
  const resultCountLabel = document.getElementById('result-count')!;
  resultCountLabel.innerText = 'Searching...';
  const getInput = (id: string) => document.getElementById(id) as HTMLInputElement;
  const nameQuery = getInput('name-input').value.trim().toUpperCase();
  const effectQuery = getInput('effect-input').value.trim().toUpperCase();
  const results = [];
  const resultDiv = document.getElementById('results')!;
  const neededElements = [];
  resultDiv.innerHTML = '';
  for (const cb of document.querySelectorAll('input.element') as NodeListOf<HTMLInputElement>) {
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
      if (!(item.elements.includes(element) || item.possible_elements[element]))
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
  for (const item of Object.values(db!.items)) {
    const record: string[][] = [];
    // item + group index
    {
      const strings = [];
      strings.push(item.name.toUpperCase());
      strings.push(item.tag);
      const cats = item.categories.concat(item.possible_categories)
      for (const catTag of cats) {
        strings.push(catTag);
        strings.push(db!.categories[catTag].name.toUpperCase());
      }
      record.push(strings);
    }
    // effect index
    {
      const strings = [];
      for (const group of Object.values(item.effects)) {
        for (const effSpec of Object.values(group)) {
          strings.push(effSpec.effect);
          strings.push(db!.effects[effSpec.effect].name.toUpperCase());
        }
      }
      for (const group of item.forge_effects) {
        for (const forgeEffect of group) {
          strings.push(forgeEffect.forged_effect);
          strings.push(db!.effects[forgeEffect.forged_effect].name.toUpperCase());
        }
      }
      for (const group of Object.values(item.ev_effects)) {
        for (const ev_tag of group) {
          strings.push(ev_tag);
          const ev_effect = db!.ev_effects[ev_tag];
          strings.push(ev_effect.name.toUpperCase());
          for (const eff_tag of ev_effect.effects) {
            strings.push(eff_tag);
            strings.push(db!.effects[eff_tag].name.toUpperCase());
          }
        }
      }
      record.push(strings);
    }
    itemIndex.push([item, record[0], record[1]]);
  }
}

function gameChanged() {
  const gameInput = document.getElementById('game-input') as HTMLInputElement;
  db = null;
  fetch(gameInput.value).then(async response => {
    db = await response.json();
    if (!db)
      return;
    buildIndex();
    update();
    buildChainCache(db);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const gameInput = document.getElementById('game-input')!;
  popupModal = new bootstrap.Modal(document.getElementById('item-popup')!);
  gameInput.addEventListener('change', gameChanged);
  gameChanged();
  for (const input of document.querySelectorAll('#search-bar input')) {
    input.addEventListener('input', update);
  }
  document.getElementById('find-chains-button')!.addEventListener('click', findChains);
  document.getElementById('chain-swap-button')!.addEventListener('click', () => {
    [chainGoal, chainStart] = [chainStart, chainGoal];
    updateChainSettings();
  });
  document.getElementById('clear-chains-button')!.addEventListener('click', () => {
    document.getElementById('chain-results')!.innerHTML = '';
    updateChainSettings();
  });
});
