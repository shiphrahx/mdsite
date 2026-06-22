import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { render, firstH1, slugify } from './render.js';
import { loadConfig, makeExcludeMatcher } from './config.js';
import { buildNav, prevNextMap, isIndexFile } from './nav.js';

const MD_EXT = new Set(['.md', '.markdown']);

// Recursively walk a directory, yielding file paths relative to root.
async function walk(root, dir = root, acc = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await walk(root, full, acc);
    } else if (entry.isFile()) {
      acc.push(path.relative(root, full));
    }
  }
  return acc;
}

// Map a source-relative .md path to its clean output URL path (no .html).
// foo/bar.md      -> foo/bar/index.html  (url /foo/bar/)
// foo/index.md    -> foo/index.html      (url /foo/)
// index.md        -> index.html          (url /)
export function outputPathFor(relPath) {
  const parsed = path.parse(relPath);
  const base = parsed.name.toLowerCase();
  const dir = parsed.dir;
  if (base === 'index' || base === 'readme') {
    return path.join(dir, 'index.html');
  }
  return path.join(dir, slugify(parsed.name), 'index.html');
}

// Convert an output html path to a clean URL ("/foo/bar/").
export function urlFor(outPath, base) {
  let url = outPath.replace(/index\.html$/, '').split(path.sep).join('/');
  if (!url.startsWith('/')) url = '/' + url;
  const prefix = base.replace(/\/$/, '');
  return (prefix + url).replace(/\/{2,}/g, '/') || '/';
}

// Minimal Day-1 page shell. Replaced by template engine on Day 3.
function pageShell({ title, body }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
</head>
<body>
<main>
${body}
</main>
</body>
</html>
`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

export async function build(srcDir, opts = {}) {
  const src = path.resolve(srcDir);
  const out = path.resolve(opts.out ?? './dist');
  const base = opts.base ?? '/';

  // Validate source.
  let stat;
  try {
    stat = await fs.stat(src);
  } catch {
    throw new Error(`source folder not found: ${srcDir}`);
  }
  if (!stat.isDirectory()) throw new Error(`source is not a directory: ${srcDir}`);

  const config = await loadConfig(src);
  const isExcluded = makeExcludeMatcher(config.exclude);
  const siteTitle = opts.title || config.title || path.basename(src);

  const all = (await walk(src)).filter((f) => !isExcluded(f));
  const mdFiles = all.filter((f) => MD_EXT.has(path.extname(f).toLowerCase()));
  const assets = all.filter((f) => !MD_EXT.has(path.extname(f).toLowerCase()));

  if (mdFiles.length === 0) {
    throw new Error(`no .md files found in ${srcDir}`);
  }

  if (opts.clean) {
    await fs.rm(out, { recursive: true, force: true });
  }
  await fs.mkdir(out, { recursive: true });

  // Pre-compute clean URL for every source .md path, so links between
  // pages can be rewritten. Keys are normalized forward-slash paths.
  const urlMap = new Map();
  for (const rel of mdFiles) {
    const norm = rel.split(path.sep).join('/');
    urlMap.set(norm, urlFor(outputPathFor(rel), base));
  }

  // Build a per-file link rewriter: resolve a relative href against the
  // current file's dir; if it points at a known .md page, swap in its URL.
  const makeLinkRewrite = (rel) => (href) => {
    // Leave absolute URLs, anchors, mailto, protocol-relative untouched.
    if (/^([a-z]+:)?\/\//i.test(href) || href.startsWith('#') || href.startsWith('mailto:')) {
      return href;
    }
    const [pathPart, hash = ''] = href.split('#');
    if (!/\.(md|markdown)$/i.test(pathPart)) return href;
    const fromDir = path.posix.dirname(rel.split(path.sep).join('/'));
    const target = path.posix.normalize(path.posix.join(fromDir, pathPart));
    const url = urlMap.get(target);
    if (!url) return href; // dangling link — leave as-is
    return hash ? `${url}#${hash}` : url;
  };

  // Pass 1: read, parse front matter, render. Collect page records.
  const pages = [];
  const seenOutputs = new Map();
  for (const rel of mdFiles) {
    const norm = rel.split(path.sep).join('/');
    const raw = await fs.readFile(path.join(src, rel), 'utf8');

    let data = {};
    let content = raw;
    try {
      const parsed = matter(raw);
      data = parsed.data;
      content = parsed.content;
    } catch (err) {
      console.warn(`warn: malformed front matter in ${rel} — ignoring (${err.message})`);
    }

    if (data.draft === true) continue;

    const { html, headings } = render(content, { linkRewrite: makeLinkRewrite(rel) });
    const title = data.title || firstH1(headings) || path.parse(rel).name;

    const outRel = outputPathFor(rel);
    if (seenOutputs.has(outRel)) {
      console.warn(`warn: duplicate output path ${outRel} (from ${seenOutputs.get(outRel)} and ${rel}) — last wins`);
    }
    seenOutputs.set(outRel, rel);

    pages.push({
      rel: norm,
      url: urlMap.get(norm),
      outRel,
      title,
      html,
      headings,
      order: typeof data.order === 'number' ? data.order : null,
      isIndex: isIndexFile(rel),
    });
  }

  // Build nav tree + prev/next from collected pages.
  const { tree, ordered } = buildNav(pages);
  const neighbors = prevNextMap(ordered);

  // Pass 2: write each page with full context (nav + prev/next available).
  for (const page of pages) {
    const { prev, next } = neighbors.get(page.url) ?? { prev: null, next: null };
    const body = pageShell({
      title: page.title,
      body: page.html,
      siteTitle,
      tree,
      headings: page.headings,
      currentUrl: page.url,
      prev,
      next,
      config,
      base,
    });
    const outAbs = path.join(out, page.outRel);
    await fs.mkdir(path.dirname(outAbs), { recursive: true });
    await fs.writeFile(outAbs, body, 'utf8');
  }

  // Copy static assets through verbatim.
  for (const rel of assets) {
    if (rel === 'mdsite.config.json') continue;
    const outAbs = path.join(out, rel);
    await fs.mkdir(path.dirname(outAbs), { recursive: true });
    await fs.copyFile(path.join(src, rel), outAbs);
  }

  console.log(`Built ${pages.length} page(s) → ${path.relative(process.cwd(), out) || out}`);
  return { pageCount: pages.length, out };
}
