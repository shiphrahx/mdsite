import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { render, firstH1, slugify } from './render.js';

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

  const all = await walk(src);
  const mdFiles = all.filter((f) => MD_EXT.has(path.extname(f).toLowerCase()));
  const assets = all.filter((f) => !MD_EXT.has(path.extname(f).toLowerCase()));

  if (mdFiles.length === 0) {
    throw new Error(`no .md files found in ${srcDir}`);
  }

  if (opts.clean) {
    await fs.rm(out, { recursive: true, force: true });
  }
  await fs.mkdir(out, { recursive: true });

  const seenOutputs = new Map();
  let pageCount = 0;

  // Render markdown pages.
  for (const rel of mdFiles) {
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

    const { html, headings } = render(content);
    const title = data.title || firstH1(headings) || path.parse(rel).name;

    const outRel = outputPathFor(rel);
    if (seenOutputs.has(outRel)) {
      console.warn(`warn: duplicate output path ${outRel} (from ${seenOutputs.get(outRel)} and ${rel}) — last wins`);
    }
    seenOutputs.set(outRel, rel);

    const outAbs = path.join(out, outRel);
    await fs.mkdir(path.dirname(outAbs), { recursive: true });
    await fs.writeFile(outAbs, pageShell({ title, body: html }), 'utf8');
    pageCount++;
  }

  // Copy static assets through verbatim.
  for (const rel of assets) {
    if (rel === 'mdsite.config.json') continue;
    const outAbs = path.join(out, rel);
    await fs.mkdir(path.dirname(outAbs), { recursive: true });
    await fs.copyFile(path.join(src, rel), outAbs);
  }

  console.log(`Built ${pageCount} page(s) → ${path.relative(process.cwd(), out) || out}`);
  void base; // base wiring lands on Day 2
  return { pageCount, out };
}
