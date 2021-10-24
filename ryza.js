/*
 * ATTENTION: The "eval" devtool has been used (maybe by default in mode: "development").
 * This devtool is neither made for production nor for readable output files.
 * It uses "eval()" calls to create a separate source file in the browser devtools.
 * If you are trying to read the output file, select a different devtool (https://webpack.js.org/configuration/devtool/)
 * or disable the default devtool with "devtool: false".
 * If you are looking for production-ready output files, see mode: "production" (https://webpack.js.org/configuration/mode/).
 */
/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./src/chainFinder.ts":
/*!****************************!*\
  !*** ./src/chainFinder.ts ***!
  \****************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"buildChainCache\": () => (/* binding */ buildChainCache),\n/* harmony export */   \"findPaths\": () => (/* binding */ findPaths),\n/* harmony export */   \"logChains\": () => (/* binding */ logChains),\n/* harmony export */   \"describeConnection\": () => (/* binding */ describeConnection)\n/* harmony export */ });\nconst conTypes = [];\nfunction addConnectionType(cost, description) {\n    const sort = conTypes.length;\n    const connection = { sort, cost, description };\n    conTypes.push(connection);\n    return connection;\n}\nconst CON_BASE_CATEGORY = addConnectionType(0, '(base category)');\nconst CON_EFFECT_CATEGORY = addConnectionType(0, '(effect category)');\n// TODO: use this for marking essence-only categories\n//const CON_ESSENCE_CATEGORY = addConnectionType(0, '(essence category)');\nconst CON_MORPH = addConnectionType(1, '(morph)');\nconst CON_INGREDIENT = addConnectionType(1, '(named ingredient)');\nconst CON_CAT_INGREDIENT = addConnectionType(1, '(ingredient)');\nconst CON_EV_LINK = addConnectionType(1, '(EV-link)');\nlet connected;\nlet toCategory;\nlet fromCategory;\nfunction buildChainCache(db) {\n    if (connected)\n        return;\n    connected = {};\n    toCategory = {};\n    fromCategory = {};\n    const addCon = (cons, a, b, type_) => {\n        if (!cons[a][b] || cons[a][b].sort > type_.sort)\n            cons[a][b] = type_;\n    };\n    for (const tag of Object.keys(db.items)) {\n        connected[tag] = {};\n    }\n    for (const tag of Object.keys(db.categories)) {\n        toCategory[tag] = {};\n        fromCategory[tag] = {};\n    }\n    for (const item of Object.values(db.items)) {\n        for (const cat of item.categories) {\n            addCon(toCategory, cat, item.tag, CON_BASE_CATEGORY);\n        }\n        for (const cat of item.possible_categories) {\n            // FIXME: separate essence and normal effect unlocks\n            addCon(toCategory, cat, item.tag, CON_EFFECT_CATEGORY);\n        }\n        for (const child of item.children)\n            addCon(connected, item.tag, child, CON_MORPH);\n        if (item.ev_base)\n            addCon(connected, item.ev_base, item.tag, CON_EV_LINK);\n        for (const ingredient of item.ingredients) {\n            if (db.categories.hasOwnProperty(ingredient))\n                addCon(fromCategory, ingredient, item.tag, CON_INGREDIENT);\n            else\n                addCon(connected, ingredient, item.tag, CON_INGREDIENT);\n        }\n    }\n    for (const [tag, cat] of Object.entries(db.categories)) {\n        const toItems = Object.keys(fromCategory[tag]);\n        const fromItems = Object.keys(toCategory[tag]);\n        for (const a of fromItems) {\n            for (const b of toItems) {\n                const con = { ...CON_CAT_INGREDIENT, description: cat.name };\n                addCon(connected, a, b, con);\n            }\n        }\n    }\n}\nfunction findPathDijkstra(start, target) {\n    const unvisited = new Set(Object.keys(connected));\n    const distances = {};\n    const prev = {};\n    for (const tag of unvisited) {\n        distances[tag] = Infinity;\n        prev[tag] = null;\n    }\n    distances[start] = 0;\n    while (unvisited.size) {\n        let minItem = null;\n        for (const i of unvisited) {\n            if (!minItem || minItem[1] > distances[i])\n                minItem = [i, distances[i]];\n        }\n        let [current, value] = minItem;\n        unvisited.delete(current);\n        if (current == target)\n            break;\n        for (const [next, con] of Object.entries(connected[current])) {\n            if (!unvisited.has(next))\n                continue;\n            const d = value + con.cost;\n            if (d < distances[next]) {\n                distances[next] = d;\n                prev[next] = current;\n            }\n        }\n    }\n    const path = [];\n    let current = target;\n    if (prev[current] || current == start) {\n        while (current) {\n            path.unshift(current);\n            current = prev[current];\n        }\n    }\n    return path;\n}\n// https://en.wikipedia.org/wiki/Yen%27s_algorithm\nfunction findPathsYen(start, target, K = 5) {\n    const bestPaths = [findPathDijkstra(start, target)];\n    if (!bestPaths[0].length)\n        return [];\n    const candidates = [];\n    let deletedNodes = {};\n    let deletedEdges = {};\n    for (let k = 1; k < K; k++) {\n        const lastA = bestPaths[bestPaths.length - 1];\n        for (let i = 0; i < lastA.length - 2; i++) {\n            const spurNode = lastA[i];\n            const rootPath = lastA.slice(0, i + 1);\n            for (const path of bestPaths) {\n                if (rootPath.join() == path.slice(0, i + 1).join()) {\n                    const key = [path[i], path[i + 1]];\n                    if (!deletedEdges.hasOwnProperty(key.toString()))\n                        deletedEdges[key.toString()] = [key, connected[key[0]][key[1]]];\n                    delete connected[key[0]][key[1]];\n                }\n            }\n            for (const node of rootPath.slice(0, -1)) {\n                if (!deletedNodes.hasOwnProperty(node))\n                    deletedNodes[node] = connected[node];\n                connected[node] = {};\n            }\n            const spurPath = findPathDijkstra(spurNode, target);\n            for (const [node, val] of Object.entries(deletedNodes))\n                connected[node] = val;\n            for (const [key, val] of Object.values(deletedEdges))\n                connected[key[0]][key[1]] = val;\n            deletedNodes = {};\n            deletedEdges = {};\n            if (spurPath.length) {\n                const totalPath = rootPath.concat(spurPath.splice(1));\n                const totalPathStr = totalPath.join();\n                let found = false;\n                for (const i of candidates) {\n                    if (totalPathStr == i[1]) {\n                        found = true;\n                        break;\n                    }\n                }\n                if (!found) {\n                    candidates.push([totalPath, totalPathStr]);\n                }\n            }\n        }\n        if (!candidates.length)\n            break;\n        // TODO: a sorted data structure would be a lot better\n        let minCost = Infinity;\n        let minPathIdx = null;\n        for (let i = 0; i < candidates.length; i++) {\n            const p = candidates[i][0];\n            let cost = 0;\n            let current = p[0];\n            for (const next of p.slice(1)) {\n                cost += connected[current][next].cost;\n                current = next;\n            }\n            if (cost < minCost) {\n                minCost = cost;\n                minPathIdx = i;\n            }\n        }\n        bestPaths.push(candidates.splice(minPathIdx, 1)[0][0]);\n    }\n    return bestPaths;\n}\n// find the k shortest chains from start to target\nfunction findPaths(db, start, target, k = 5) {\n    // if that start or target are categories, enable them\n    if (db.categories.hasOwnProperty(start)) {\n        connected[start] = fromCategory[start];\n    }\n    if (db.categories.hasOwnProperty(target)) {\n        // need to add this for the path finder to ever consider the node\n        connected[target] = {};\n        for (const [item, con] of Object.entries(toCategory[target]))\n            connected[item][target] = con;\n    }\n    const results = findPathsYen(start, target, k);\n    // restore the base connection graph\n    if (db.categories.hasOwnProperty(start)) {\n        delete connected[start];\n    }\n    if (db.categories.hasOwnProperty(target)) {\n        delete connected[target];\n        for (const item of Object.keys(toCategory[target]))\n            delete connected[item][target];\n    }\n    return results;\n}\nfunction logChains(db, chains) {\n    console.debug('found:');\n    for (const chain of chains) {\n        console.debug(chain.map(tag => (db.items[tag] || db.categories[tag]).name));\n    }\n}\nfunction describeConnection(a, b) {\n    return connected[a][b].description;\n}\n\n\n//# sourceURL=webpack://atelier_tools_webui/./src/chainFinder.ts?");

/***/ }),

/***/ "./src/main.ts":
/*!*********************!*\
  !*** ./src/main.ts ***!
  \*********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony import */ var _tag__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./tag */ \"./src/tag.ts\");\n/* harmony import */ var _chainFinder__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! ./chainFinder */ \"./src/chainFinder.ts\");\n\n\nlet db = null;\nlet itemIndex;\nconst MAX_RESULTS = 100;\n// order and icon classes\nconst ELEMENTS = {\n    'Fire': 'atelier-ryza2-fire',\n    'Ice': 'atelier-ryza2-ice',\n    'Thunder': 'atelier-ryza2-lightning',\n    'Air': 'atelier-ryza2-wind'\n};\nlet popupModal;\n// TODO: navigation, better formats, chain finder\nfunction renderMixfield(item, recipe, mixfield, ev_lv = 0) {\n    // TODO: proper ring information\n    const scale = 50;\n    // loop radius\n    const radius = 26;\n    // padding for the whole image\n    const padding = 10;\n    const attrs = {\n        'class': 'mixfield rounded mx-auto d-block',\n    };\n    const rings = {};\n    for (const [idx, ring] of Object.entries(mixfield.rings)) {\n        if (ring.ev_lv <= ev_lv)\n            rings[idx] = ring;\n    }\n    // we adjust the viewBox to cover the image, so we don't have to\n    // shift all the coordinates\n    const minX = Math.min(...Object.values(rings).map(ring => ring.x));\n    const maxX = Math.max(...Object.values(rings).map(ring => ring.x));\n    const minY = Math.min(...Object.values(rings).map(ring => ring.y));\n    const maxY = Math.max(...Object.values(rings).map(ring => ring.y));\n    const viewbox = [\n        (minX - 1) * scale - padding,\n        (minY - 1) * scale - padding,\n        (maxX - minX + 2) * scale + padding * 2,\n        (maxY - minY + 2) * scale + padding * 2,\n    ];\n    attrs['viewBox'] = viewbox.join(' ');\n    const svgTag = (name, attrs) => {\n        const e = document.createElementNS('http://www.w3.org/2000/svg', name);\n        for (const [k, v] of Object.entries(attrs))\n            e.setAttribute(k, v.toString());\n        return e;\n    };\n    const svg = svgTag('svg', attrs);\n    // first draw the connections\n    const pathParts = [];\n    for (const ring of Object.values(rings)) {\n        if (ring.parent_idx === null)\n            continue;\n        const parent = rings[ring.parent_idx];\n        const x = ring.x * scale, y = ring.y * scale;\n        const px = parent.x * scale, py = parent.y * scale;\n        pathParts.push(`M${x},${y}L${px},${py}`);\n    }\n    if (pathParts)\n        svg.appendChild(svgTag('path', { 'd': pathParts.join(''), 'class': 'connection' }));\n    // next draw the rings\n    for (const ring of Object.values(rings)) {\n        const cx = ring.x * scale, cy = ring.y * scale;\n        const classes = ['loop', 'loop-type-' + ring.type, 'loop-elem-' + ring.element];\n        if (ring.is_essential)\n            classes.push('loop-essential');\n        svg.appendChild(svgTag('circle', { class: classes.join(' '), cx, cy, r: radius }));\n    }\n    return svg;\n}\nfunction showMixfield(...args) {\n    popup((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('div', { 'class': 'mixfield-container' }, [renderMixfield(...args)]));\n}\nfunction getMixfieldInfo(item) {\n    let target = item;\n    let ev_lv = 0;\n    if (item.ev_base) {\n        target = db.items[item.ev_base];\n        ev_lv = 1;\n    }\n    if (target.recipe && target.recipe.mixfield)\n        return [item, target.recipe, target.recipe.mixfield, ev_lv];\n    return null;\n}\nfunction renderElements(item) {\n    const elems = [];\n    for (const [elem, icon] of Object.entries(ELEMENTS)) {\n        const normal = item['elements'].includes(elem);\n        const optional = item['possible_elements'][elem];\n        const active = normal || optional;\n        const classes = ['elem-icon', 'icon', 'icon-lg'];\n        classes.push(icon);\n        classes.push((active ? 'elem-active' : 'elem-inactive'));\n        const name = db.elements[elem];\n        let liAttrs = { 'title': name };\n        if (!active)\n            liAttrs['title'] = 'No ' + name;\n        if (optional) {\n            liAttrs = { 'class': 'optional', 'title': `${name} (from ${optional} effect)` };\n        }\n        elems.push((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', liAttrs, [(0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('span', { 'class': classes.join(' ') }, [])]));\n    }\n    let elementValue = '' + item['element_value'];\n    if (item['add_element_value'] > 0) {\n        elementValue += '+' + item['add_element_value'];\n    }\n    return [\n        (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('span', {}, [elementValue]),\n        (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'elements' }, elems)\n    ];\n}\nfunction findLowestLevel(item) {\n    let parents = (item.parents || []).map(tag => db.items[tag]);\n    return Math.min(item.level, ...parents.map(findLowestLevel));\n}\nfunction popup(contents) {\n    const body = document.querySelector('#item-popup .modal-body');\n    body.innerHTML = '';\n    body.appendChild(contents);\n    popupModal.show();\n}\nfunction itemPopup(item) {\n    popup(renderItem(item));\n}\nfunction popupThing(tag) {\n    if (db.items[tag]) {\n        itemPopup(db.items[tag]);\n    }\n    else {\n        console.warn(`unknown popup thing: ${tag}`);\n    }\n}\nfunction link(target, popup = true) {\n    const types = {\n        'item': db.items,\n        'category': db.categories,\n        'effect': db.effects,\n        'ev_effect': db.ev_effects,\n    };\n    let type = 'unknown';\n    let value = null;\n    for (const [k, v] of Object.entries(types)) {\n        value = v[target];\n        if (value) {\n            type = k;\n            break;\n        }\n    }\n    if (value === null) {\n        const msg = `Error: ${target} not found!`;\n        throw msg;\n    }\n    const attrs = {\n        'class': `link-${type}`,\n        'data-link-type': type,\n        'data-link-tag': target,\n    };\n    if (value.description)\n        attrs['title'] = value.description;\n    if (type == 'ev_effect')\n        attrs['title'] = value.effects.map(i => db.effects[i].name).join(', ');\n    if (popup && type == 'item') {\n        attrs['href'] = '#';\n        const elem = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('a', attrs, [value.name]);\n        elem.addEventListener('click', e => {\n            e.preventDefault();\n            itemPopup(db.items[target]);\n        });\n        return elem;\n    }\n    else {\n        return (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('span', attrs, [value.name]);\n    }\n}\nfunction renderItem(item) {\n    const elems = [];\n    const miscInfo = [\n        'Lv' + item['level'],\n        'MinLv' + findLowestLevel(item),\n        '$' + item['price'],\n    ].map(i => (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [i]));\n    const heading = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('div', { 'class': 'card-body' }, [\n        (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('h5', { 'class': 'card-title' }, [\n            link(item.tag, false),\n        ]),\n        (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('h6', { 'class': 'card-subtitle muted' }, [\n            item['tag'],\n            (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'misc-info inline-list' }, miscInfo)\n        ]),\n    ]);\n    const addRow = (label, contents) => {\n        elems.push((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('dt', { 'class': 'col-sm-3' }, [label]));\n        elems.push((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('dd', { 'class': 'col-sm-9' }, contents));\n    };\n    const cats = [];\n    const catDefs = [[item.categories, ''], [item.possible_categories, 'optional']];\n    for (const [container, cls] of catDefs) {\n        const attrs = {};\n        if (cls)\n            attrs['class'] = cls;\n        for (const cat of container) {\n            cats.push((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [\n                (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('span', attrs, [db.categories[cat].name])\n            ]));\n        }\n    }\n    addRow('Categories', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list' }, cats));\n    addRow('Elements', renderElements(item));\n    const effects = [];\n    for (const group of Object.values(item.effects)) {\n        const keys = Object.keys(group);\n        if (!keys.length)\n            break;\n        keys.sort((a, b) => parseInt(b) - parseInt(a));\n        const effTag = group[keys[0]].effect;\n        effects.push(db.effects[effTag]);\n    }\n    if (effects.length) {\n        effects.sort((a, b) => a.name_id - b.name_id);\n        const tags = effects.map(i => (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(i.tag)]));\n        addRow('Effects', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list effects' }, tags));\n    }\n    if (item.ingredients.length) {\n        const tags = item.ingredients.map(ingTag => (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(ingTag)]));\n        addRow('Ingredients', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list ingredients' }, tags));\n        const mixfieldParams = getMixfieldInfo(item);\n        if (mixfieldParams) {\n            const mixfieldButton = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('button', { 'class': 'btn btn-primary' }, 'Show');\n            addRow('Loops', mixfieldButton);\n            mixfieldButton.addEventListener('click', () => showMixfield(...mixfieldParams));\n        }\n    }\n    // TODO: handle ev-link relations\n    const parentsList = [];\n    let parents = item['parents'];\n    while (parents && parents.length) {\n        if (parents.length > 1)\n            console.warn(`Too many parents for ${item['tag']}`);\n        const parent = db.items[parents[0]];\n        parentsList.unshift(parent);\n        parents = parent['parents'];\n    }\n    if (parentsList.length) {\n        const tags = parentsList.map(i => (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, link(i.tag)));\n        addRow('Parents', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list parents' }, tags));\n    }\n    const children = item['children'].map(i => (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(i)]));\n    if (children.length) {\n        addRow('Children', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list children' }, children));\n    }\n    if (item.ev_base) {\n        const base = db.items[item.ev_base];\n        const mat = db.items[base.recipe.ev_extend_mat];\n        const items = [base, mat].map(ingredient => {\n            return (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(ingredient.tag)]);\n        });\n        addRow('EV-link from', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list' }, items));\n    }\n    if (item.gathering)\n        addRow('Gather', item.gathering);\n    if (item.shop_data)\n        addRow('Shop', item.shop_data);\n    if (item.seed)\n        addRow('From seed', link(item.seed));\n    const forged = item.forge_effects.map(group => {\n        const last = group[group.length - 1];\n        return (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(last.forged_effect)]);\n    });\n    if (forged.length)\n        addRow('Forging', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list effects' }, forged));\n    const ev_effects = [];\n    for (const effs of Object.values(item.ev_effects)) {\n        for (let idx = effs.length - 1; idx >= 0; idx--) {\n            const eff = effs[idx];\n            const ev_eff = db.ev_effects[eff];\n            if (ev_eff.effects.length)\n                ev_effects.push((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', {}, [link(eff)]));\n            //else\n            //  console.debug('no effects for ev effect:', ev_eff);\n        }\n    }\n    if (ev_effects.length)\n        addRow('EV effects', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('ul', { 'class': 'inline-list' }, ev_effects));\n    const chainOptions = [\"start\"];\n    if (item.recipe || item.ev_base) {\n        chainOptions.push('goal');\n    }\n    const buttons = chainOptions.map(i => {\n        const button = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('button', { 'class': 'btn btn-primary m-1' }, ['Set as ' + i]);\n        button.addEventListener('click', () => setChain(i, item));\n        return button;\n    });\n    addRow('Chain', (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('div', {}, buttons));\n    return (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('div', { 'class': 'card', 'data-tag': item['tag'] }, [\n        heading,\n        (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('dl', { 'class': 'card-body row' }, elems),\n    ]);\n}\nlet chainStart = null, chainGoal = null;\nfunction setChain(startOrGoal, thing) {\n    if (startOrGoal == 'start')\n        chainStart = thing;\n    else\n        chainGoal = thing;\n    updateChainSettings();\n}\nfunction updateChainSettings() {\n    const container = document.getElementById('chain-container');\n    if (chainStart || chainGoal) {\n        container.style.display = 'block';\n    }\n    else {\n        container.style.display = 'none';\n    }\n    const startDiv = document.getElementById('chain-start');\n    const goalDiv = document.getElementById('chain-goal');\n    const ends = [[startDiv, chainStart, 'start'], [goalDiv, chainGoal, 'goal']];\n    for (const [e, value, type] of ends) {\n        if (value) {\n            const itemButton = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('button', { 'class': 'btn btn-primary' }, [value.name]);\n            const removeButton = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('button', { 'class': 'btn btn-danger', 'title': 'Remove' }, ['🗑️']);\n            // FIXME: this only works on items\n            itemButton.addEventListener('click', () => itemPopup(value));\n            removeButton.addEventListener('click', () => {\n                setChain(type, null);\n            });\n            const content = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('div', { 'class': 'btn-group' }, [\n                itemButton,\n                removeButton,\n            ]);\n            e.innerHTML = '';\n            e.appendChild(content);\n        }\n        else {\n            e.innerText = '(none)';\n        }\n    }\n    const goButton = document.getElementById('find-chains-button');\n    if (chainStart && chainGoal)\n        goButton.disabled = false;\n    else\n        goButton.disabled = true;\n}\nfunction renderConnection(a, b) {\n    const arrow = '➡';\n    if (db.categories.hasOwnProperty(a.tag)) {\n        // must be start of chain, it has to be CAT_INGREDIENT\n        return [arrow];\n    }\n    else if (db.categories.hasOwnProperty(b.tag)) {\n        // end of chain, might be of BASE_CATEGORY, EFFECT_CATEGORY, ESSENCE_CATEGORY\n        // FIXME\n        return [arrow];\n    }\n    const label = (0,_chainFinder__WEBPACK_IMPORTED_MODULE_1__.describeConnection)(a.tag, b.tag);\n    return [label, arrow];\n}\nfunction findChains() {\n    if (!chainStart || !chainGoal) {\n        alert('A chain endpoint is missing!');\n        return;\n    }\n    const resultsList = document.getElementById('chain-results');\n    resultsList.innerHTML = '';\n    const chains = (0,_chainFinder__WEBPACK_IMPORTED_MODULE_1__.findPaths)(db, chainStart.tag, chainGoal.tag);\n    if (!chains.length) {\n        resultsList.appendChild((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', { 'class': 'list-group-item text-danger' }, ['No chains found!']));\n    }\n    for (const chain of chains) {\n        const items = [];\n        let prev = null;\n        for (const thingTag of chain) {\n            const thing = db.items[thingTag] || db.categories[thingTag];\n            if (prev) {\n                items.push(...renderConnection(prev, thing));\n            }\n            const button = (0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('button', { 'class': 'btn btn-secondary m-2' }, [thing.name]);\n            items.push(button);\n            button.addEventListener('click', () => popupThing(thingTag));\n            prev = thing;\n        }\n        resultsList.appendChild((0,_tag__WEBPACK_IMPORTED_MODULE_0__.tag)('li', { 'class': 'list-group-item p-2 d-flex flex-wrap align-items-center justify-contents-center' }, items));\n    }\n}\nfunction update() {\n    if (!db)\n        return;\n    console.debug('ready');\n    const resultCountLabel = document.getElementById('result-count');\n    resultCountLabel.innerText = 'Searching...';\n    const getInput = (id) => document.getElementById(id);\n    const nameQuery = getInput('name-input').value.trim().toUpperCase();\n    const effectQuery = getInput('effect-input').value.trim().toUpperCase();\n    let results = [];\n    const resultDiv = document.getElementById('results');\n    const neededElements = [];\n    resultDiv.innerHTML = '';\n    for (const cb of document.querySelectorAll('input.element')) {\n        if (cb.checked) {\n            neededElements.push(cb.value);\n        }\n    }\n    outer_loop: for (const [item, itemHaystacks, effectHaystacks] of itemIndex) {\n        if (nameQuery) {\n            let found = false;\n            for (const haystack of itemHaystacks) {\n                if (haystack.includes(nameQuery)) {\n                    found = true;\n                    break;\n                }\n            }\n            if (!found)\n                continue outer_loop;\n        }\n        if (effectQuery) {\n            let found = false;\n            for (const haystack of effectHaystacks) {\n                if (haystack.includes(effectQuery)) {\n                    found = true;\n                    break;\n                }\n            }\n            if (!found)\n                continue outer_loop;\n        }\n        for (const element of neededElements) {\n            if (!(item.elements.includes(element) || item.possible_elements[element]))\n                continue outer_loop;\n        }\n        results.push(item);\n        resultDiv.appendChild(renderItem(item));\n        if (results.length >= MAX_RESULTS) {\n            console.warn('maximum number of results reached');\n            break;\n        }\n    }\n    if (results.length >= MAX_RESULTS)\n        resultCountLabel.innerText = `${results.length}+ found`;\n    else\n        resultCountLabel.innerText = `${results.length} found`;\n    console.debug(`found ${results.length} items`);\n}\nfunction buildIndex() {\n    itemIndex = [];\n    for (const item of Object.values(db.items)) {\n        const record = [];\n        // item + group index\n        {\n            const strings = [];\n            strings.push(item.name.toUpperCase());\n            strings.push(item.tag);\n            const cats = item.categories.concat(item.possible_categories);\n            for (const catTag of cats) {\n                strings.push(catTag);\n                strings.push(db.categories[catTag].name.toUpperCase());\n            }\n            record.push(strings);\n        }\n        // effect index\n        {\n            const strings = [];\n            for (const group of Object.values(item.effects)) {\n                for (const effSpec of Object.values(group)) {\n                    strings.push(effSpec.effect);\n                    strings.push(db.effects[effSpec.effect].name.toUpperCase());\n                }\n            }\n            for (const group of item.forge_effects) {\n                for (const forgeEffect of group) {\n                    strings.push(forgeEffect.forged_effect);\n                    strings.push(db.effects[forgeEffect.forged_effect].name.toUpperCase());\n                }\n            }\n            for (const group of Object.values(item.ev_effects)) {\n                for (const ev_tag of group) {\n                    strings.push(ev_tag);\n                    const ev_effect = db.ev_effects[ev_tag];\n                    strings.push(ev_effect.name.toUpperCase());\n                    for (const eff_tag of ev_effect.effects) {\n                        strings.push(eff_tag);\n                        strings.push(db.effects[eff_tag].name.toUpperCase());\n                    }\n                }\n            }\n            record.push(strings);\n        }\n        itemIndex.push([item, record[0], record[1]]);\n    }\n}\nfunction gameChanged() {\n    const gameInput = document.getElementById('game-input');\n    db = null;\n    fetch(gameInput.value).then(async (response) => {\n        db = await response.json();\n        if (!db)\n            return;\n        buildIndex();\n        update();\n        (0,_chainFinder__WEBPACK_IMPORTED_MODULE_1__.buildChainCache)(db);\n    });\n}\ndocument.addEventListener('DOMContentLoaded', () => {\n    const gameInput = document.getElementById('game-input');\n    popupModal = new bootstrap.Modal(document.getElementById('item-popup'));\n    gameInput.addEventListener('change', gameChanged);\n    gameChanged();\n    for (const input of document.querySelectorAll('#search-bar input')) {\n        input.addEventListener('input', update);\n    }\n    document.getElementById('find-chains-button').addEventListener('click', findChains);\n    document.getElementById('chain-swap-button').addEventListener('click', () => {\n        [chainGoal, chainStart] = [chainStart, chainGoal];\n        updateChainSettings();\n    });\n    document.getElementById('clear-chains-button').addEventListener('click', () => {\n        document.getElementById('chain-results').innerHTML = '';\n        updateChainSettings();\n    });\n});\n\n\n//# sourceURL=webpack://atelier_tools_webui/./src/main.ts?");

/***/ }),

/***/ "./src/tag.ts":
/*!********************!*\
  !*** ./src/tag.ts ***!
  \********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"tag\": () => (/* binding */ tag),\n/* harmony export */   \"appendChildren\": () => (/* binding */ appendChildren)\n/* harmony export */ });\nfunction tag(tag, attributes = {}, children = []) {\n    const e = document.createElement(tag);\n    for (const [name, value] of Object.entries(attributes)) {\n        e.setAttribute(name, value);\n    }\n    if (!Array.isArray(children)) {\n        children = [children];\n    }\n    appendChildren(e, children);\n    return e;\n}\nfunction appendChildren(parent, children) {\n    if (!Array.isArray(children))\n        children = [children];\n    for (let child of children) {\n        if (!(child instanceof Element))\n            parent.appendChild(document.createTextNode(child));\n        else\n            parent.appendChild(child);\n    }\n    return parent;\n}\n\n\n//# sourceURL=webpack://atelier_tools_webui/./src/tag.ts?");

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId](module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	/* webpack/runtime/define property getters */
/******/ 	(() => {
/******/ 		// define getter functions for harmony exports
/******/ 		__webpack_require__.d = (exports, definition) => {
/******/ 			for(var key in definition) {
/******/ 				if(__webpack_require__.o(definition, key) && !__webpack_require__.o(exports, key)) {
/******/ 					Object.defineProperty(exports, key, { enumerable: true, get: definition[key] });
/******/ 				}
/******/ 			}
/******/ 		};
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/hasOwnProperty shorthand */
/******/ 	(() => {
/******/ 		__webpack_require__.o = (obj, prop) => (Object.prototype.hasOwnProperty.call(obj, prop))
/******/ 	})();
/******/ 	
/******/ 	/* webpack/runtime/make namespace object */
/******/ 	(() => {
/******/ 		// define __esModule on exports
/******/ 		__webpack_require__.r = (exports) => {
/******/ 			if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 				Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 			}
/******/ 			Object.defineProperty(exports, '__esModule', { value: true });
/******/ 		};
/******/ 	})();
/******/ 	
/************************************************************************/
/******/ 	
/******/ 	// startup
/******/ 	// Load entry module and return exports
/******/ 	// This entry module can't be inlined because the eval devtool is used.
/******/ 	var __webpack_exports__ = __webpack_require__("./src/main.ts");
/******/ 	
/******/ })()
;