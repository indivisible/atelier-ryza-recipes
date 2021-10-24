// Generated code, do not edit!
// Use python3 -m atelier_tools dump-ts-types to generate

export interface Item {
  idx: number;
  tag: string;
  name: string;
  name_id: number;
  description: string;
  level: number;
  price: number;
  categories: string[];
  possible_categories: string[];
  elements: string[];
  possible_elements: {[key: string]: string};
  element_value: number;
  add_element_value: number;
  children: string[];
  parents: string[];
  recipe: (Recipe | null);
  effects: {[key: string]: EffectSpec}[];
  ingredients: (string | string)[];
  essential_ingredients: (string | string)[];
  ev_base: (string | null);
  gathering: (string | null);
  shop_data: (string | null);
  seed: (string | null);
  fixed_potentials: string[];
  forge_effects: ForgeEffect[][];
  ev_effects: {[key: string]: string[]};
}

export interface Category {
  idx: number;
  tag: string;
  name: string;
  name_id: number;
  description: string;
}

export interface Effect {
  idx: number;
  tag: string;
  name: string;
  name_id: number;
  description: string;
  type: string;
  int_value: (number | null);
  category_value: (string | null);
  element_value: (string | null);
}

export interface Potential {
  idx: number;
  tag: string;
  name: string;
  name_id: number;
  description: string;
}

export interface EVEffect {
  idx: number;
  tag: string;
  name: string;
  name_id: number;
  description: string;
  effects: string[];
}

export interface Database {
  game: string;
  lang: string;
  items: {[key: string]: Item};
  categories: {[key: string]: Category};
  effects: {[key: string]: Effect};
  potentials: {[key: string]: Potential};
  elements: {[key: string]: string};
  ev_effects: {[key: string]: EVEffect};
  ring_types: {[key: string]: [string, string]};
}

export interface Recipe {
  item: string;
  available_effects: {[key: string]: string}[];
  ingredients: (string | string)[];
  recipe_category: string;
  make_num: number;
  is_ev_extended: boolean;
  has_data: boolean;
  ev_extend_item: (string | null);
  ev_extend_mat: (string | string | null);
  mixfield: (Mixfield | null);
}

export interface EffectSpec {
  effect: string;
  is_essence: boolean;
}

export interface ForgeEffect {
  forged_effect: string;
  source_effects: string[];
}

export interface Mixfield {
  rings: {[key: string]: MixfieldRing};
}

export interface MixfieldRing {
  type: number;
  is_essential: boolean;
  ev_lv: number;
  element: string;
  ingredient: (string | string);
  x: number;
  y: number;
  parent_idx: (number | null);
  morph_item: (string | null);
  effects: {[key: string]: MixfieldRingValue};
}

export interface MixfieldRingValue {
  item_value: (string | null);
  int_value: number;
  effect_value: (string | null);
  effect_sort_idx: number;
  is_locked: boolean;
}

