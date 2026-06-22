import path from 'node:path';

// Given a flat list of page records, build a nested nav tree mirroring the
// folder structure, plus a flat ordered list for prev/next.
//
// page record: { rel, url, title, order, isIndex }
//   rel     - source-relative path, forward-slash normalized
//   url     - clean output URL
//   title   - resolved page title
//   order   - front-matter order (number) or null
//   isIndex - true for index.md / readme.md (the folder's landing page)
//
// Returns { tree, ordered }.
//   tree    - { name, url, title, children: [], pages: [] } folder nodes
//   ordered - flat array of pages in nav order (for prev/next)

function sortPages(a, b) {
  const ao = a.order, bo = b.order;
  if (ao != null && bo != null && ao !== bo) return ao - bo;
  if (ao != null && bo == null) return -1;
  if (ao == null && bo != null) return 1;
  return a.title.localeCompare(b.title, undefined, { sensitivity: 'base' });
}

function sortFolders(a, b) {
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
}

export function buildNav(pages) {
  const root = { name: '', url: null, title: null, children: new Map(), pages: [] };

  for (const page of pages) {
    const segments = page.rel.split('/');
    const dirSegments = segments.slice(0, -1);

    let node = root;
    for (const seg of dirSegments) {
      if (!node.children.has(seg)) {
        node.children.set(seg, { name: seg, url: null, title: seg, children: new Map(), pages: [] });
      }
      node = node.children.get(seg);
    }

    if (page.isIndex) {
      // Index page represents the folder itself: set its url/title.
      node.url = page.url;
      node.title = page.title;
    } else {
      node.pages.push(page);
    }
  }

  // Recursively materialize Maps into sorted arrays.
  function finalize(node) {
    const children = [...node.children.values()].map(finalize).sort(sortFolders);
    const pages = node.pages.slice().sort(sortPages);
    return { name: node.name, url: node.url, title: node.title, children, pages };
  }
  const tree = finalize(root);

  // Flatten for prev/next: depth-first, folder landing page first, then its
  // pages, then its subfolders.
  const ordered = [];
  function flatten(node) {
    // Folder landing page (or root home page) comes first.
    if (node.url) {
      ordered.push({ url: node.url, title: node.title });
    }
    for (const page of node.pages) {
      ordered.push({ url: page.url, title: page.title });
    }
    for (const child of node.children) {
      flatten(child);
    }
  }
  flatten(tree);

  return { tree, ordered };
}

// Compute prev/next neighbors for each url from the ordered list.
export function prevNextMap(ordered) {
  const map = new Map();
  for (let i = 0; i < ordered.length; i++) {
    map.set(ordered[i].url, {
      prev: i > 0 ? ordered[i - 1] : null,
      next: i < ordered.length - 1 ? ordered[i + 1] : null,
    });
  }
  return map;
}

// Is this source-relative path an index/landing page for its folder?
export function isIndexFile(rel) {
  const base = path.parse(rel).name.toLowerCase();
  return base === 'index' || base === 'readme';
}
