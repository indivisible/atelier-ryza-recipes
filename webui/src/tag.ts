export type Attrs = {[key: string]: string};
export type TagChild = Element | string;
export type TagChildren = TagChild[] | TagChild;

export function tag(tag: string, attributes: Attrs = {}, children: TagChildren = []): HTMLElement {
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

export function appendChildren(parent: HTMLElement, children: TagChildren) {
  if (!Array.isArray(children))
    children = [children];
  for (let child of children) {
    if (!(child instanceof Element))
      parent.appendChild(document.createTextNode(child));
    else
      parent.appendChild(child);
  }
  return parent
}
