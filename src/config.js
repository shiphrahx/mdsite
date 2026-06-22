import { promises as fs } from 'node:fs';
import path from 'node:path';

const DEFAULTS = {
  title: null,
  description: '',
  theme: 'auto', // "light" | "dark" | "auto"
  footer: '',
  exclude: [],
};

// Load mdsite.config.json from the source root, merged over defaults.
// Missing file -> defaults. Malformed JSON -> warn, use defaults.
export async function loadConfig(srcDir) {
  const file = path.join(srcDir, 'mdsite.config.json');
  let raw;
  try {
    raw = await fs.readFile(file, 'utf8');
  } catch {
    return { ...DEFAULTS };
  }
  try {
    const parsed = JSON.parse(raw);
    return { ...DEFAULTS, ...parsed };
  } catch (err) {
    console.warn(`warn: malformed mdsite.config.json — ignoring (${err.message})`);
    return { ...DEFAULTS };
  }
}

// Compile a single glob pattern into a RegExp.
// Supports ** (any path segments), * (any chars except /), ? (single char).
function globToRegExp(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*') {
      if (glob[i + 1] === '*') {
        // ** matches across path separators
        re += '.*';
        i++;
        if (glob[i + 1] === '/') i++; // swallow trailing slash after **
      } else {
        re += '[^/]*';
      }
    } else if (c === '?') {
      re += '[^/]';
    } else if ('.+^${}()|[]\\'.includes(c)) {
      re += '\\' + c;
    } else if (c === '/') {
      re += '/';
    } else {
      re += c;
    }
  }
  return new RegExp('^' + re + '$');
}

// Build a matcher: returns true if a source-relative path matches any pattern.
export function makeExcludeMatcher(patterns = []) {
  const regexes = patterns.map(globToRegExp);
  return (relPath) => {
    const norm = relPath.split(path.sep).join('/');
    return regexes.some((re) => re.test(norm));
  };
}
