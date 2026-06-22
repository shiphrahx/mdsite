import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

// Slugify a heading's text into a URL-safe id.
export function slugify(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'section';
}

// Build a fresh markdown-it instance with GFM-ish features + highlighting.
function createMd() {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: false,
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          const out = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
          return `<pre class="hljs"><code class="language-${lang}">${out}</code></pre>`;
        } catch { /* fall through */ }
      }
      const escaped = md.utils.escapeHtml(code);
      return `<pre class="hljs"><code>${escaped}</code></pre>`;
    },
  });
  return md;
}

const md = createMd();

// Render markdown to HTML. Returns { html, headings: [{level, text, slug}] }.
// linkRewrite(href) -> rewritten href (or original). Used to map .md links to clean URLs.
export function render(markdown, { linkRewrite } = {}) {
  const env = {};
  const tokens = md.parse(markdown, env);
  const headings = [];
  const slugCounts = new Map();

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];

    // Collect headings + inject slug ids and anchor links.
    if (tok.type === 'heading_open') {
      const level = Number(tok.tag.slice(1));
      const inline = tokens[i + 1];
      const text = inline && inline.type === 'inline' ? inline.content : '';
      let slug = slugify(text);
      // De-dupe slugs within a single page.
      if (slugCounts.has(slug)) {
        const n = slugCounts.get(slug) + 1;
        slugCounts.set(slug, n);
        slug = `${slug}-${n}`;
      } else {
        slugCounts.set(slug, 0);
      }
      tok.attrSet('id', slug);
      headings.push({ level, text, slug });
      // Append a hover anchor inside the heading.
      if (inline) {
        const anchor = new inline.constructor('html_inline', '', 0);
        anchor.content = ` <a class="anchor" href="#${slug}" aria-label="Permalink">#</a>`;
        inline.children = inline.children || [];
        inline.children.push(anchor);
      }
    }

    // Rewrite relative .md links + harden external links.
    if (tok.type === 'inline' && tok.children) {
      for (const child of tok.children) {
        if (child.type === 'link_open') {
          const href = child.attrGet('href');
          if (href && linkRewrite) {
            const rewritten = linkRewrite(href);
            if (rewritten !== href) child.attrSet('href', rewritten);
          }
          if (href && /^https?:\/\//i.test(href)) {
            child.attrSet('rel', 'noopener');
            child.attrSet('target', '_blank');
          }
        }
        // Lazy-load images.
        if (child.type === 'image') {
          child.attrSet('loading', 'lazy');
        }
      }
    }
  }

  const html = md.renderer.render(tokens, md.options, env);
  return { html, headings };
}

// Extract the first H1's text from rendered headings (for title fallback).
export function firstH1(headings) {
  const h1 = headings.find((h) => h.level === 1);
  return h1 ? h1.text : null;
}
