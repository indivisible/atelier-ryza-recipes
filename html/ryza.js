var db;
var itemIndex;
const MAX_RESULTS = 100;
const ELEMENTS = ['Fire', 'Ice', 'Thunder', 'Air'];
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

function renderElements(item) {
  const elems = [];
  for (const elem of ELEMENTS) {
    const normal = item['elements'].includes(elem);
    const optional = item['possible_elements'][elem];
    const active = normal || optional;
    const classes = ['elem-icon'];
    classes.push('elem-' + elem.toLowerCase());
    classes.push((active ? 'elem-active' : 'elem-inactive'));
    const name = db['elements'][elem];
    let liAttrs = {'title': name};
    if (!active)
      liAttrs['title'] = 'No ' + name;
    if (optional) {
      liAttrs = {'class': 'optional', 'title': `${name} (from ${optional} effect)`};
    }
    elems.push(tag('li', liAttrs, [tag('span', {'class': classes.join(' ')}, [tag('span', {}, [name])])]));
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

function itemPopup(e) {
  e.preventDefault();
  const item = db.items[e.target.dataset.linkTag];
  console.log(item);
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
    elem.addEventListener('click', itemPopup);
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

  return tag('div', {'class': 'card', 'data-tag': item['tag']}, [
    heading,
    tag('dl', {'class': 'card-body row'}, elems),
  ]);
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
  outer_loop: for (const [item, haystacks] of itemIndex) {
    if (nameQuery) {
      let found = false;
      for (const haystack of haystacks) {
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
      group_loop: for (const group of Object.values(item['effects'])) {
        for (const effSpec of Object.values(group)) {
          if (effSpec.effect.includes(effectQuery)) {
            found = true;
            break group_loop;
          }
          const effName = db['effects'][effSpec.effect]['name'].toUpperCase();
          if (effName.includes(effectQuery)) {
            found = true;
            break group_loop;
          }
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
  for (const item of Object.values(db['items'])) {
    const strings = [];
    strings.push(item['name'].toUpperCase());
    strings.push(item['tag']);
    const cats = item['categories'].concat(item['possible_categories'])
    for (const catTag of cats) {
      strings.push(catTag);
      strings.push(db['categories'][catTag]['name'].toUpperCase());
    }
    itemIndex.push([item, strings]);
  }
}

function gameChanged() {
  const gameInput = document.getElementById('game-input');
  db = null;
  fetch(gameInput.value).then(async response => {
    db = await response.json();
    buildIndex();
    update();
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
});
