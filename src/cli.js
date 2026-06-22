#!/usr/bin/env node
import { build } from './build.js';

const HELP = `mdsite <command> [options]

Commands:
  build <srcDir>        Build a site from a folder of .md files
  serve <srcDir>        Build, then serve locally + live-reload on file change
  init [dir]            Create a sample content folder + mdsite.config.json

Options:
  -o, --out <dir>       Output directory (default: ./dist)
  -t, --title <string>  Site title (default: from config or folder name)
  --clean               Wipe the output dir before building
  --base <path>         Base URL path for hosting in a subfolder (default: /)
  -h, --help            Show help

Examples:
  mdsite build ./docs --out ./public --clean
  mdsite serve ./notes
  mdsite init my-site
`;

// Minimal arg parser. Returns { _: positional[], ...flags }.
function parseArgs(argv) {
  const out = { _: [] };
  const aliases = { o: 'out', t: 'title', h: 'help' };
  const boolFlags = new Set(['clean', 'help']);
  for (let i = 0; i < argv.length; i++) {
    let arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      if (boolFlags.has(key)) { out[key] = true; continue; }
      out[key] = argv[++i];
    } else if (arg.startsWith('-') && arg.length > 1) {
      const key = aliases[arg.slice(1)] ?? arg.slice(1);
      if (boolFlags.has(key)) { out[key] = true; continue; }
      out[key] = argv[++i];
    } else {
      out._.push(arg);
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const command = args._[0];

  if (args.help || !command) {
    console.log(HELP);
    process.exit(command ? 0 : (args.help ? 0 : 1));
  }

  const opts = {
    out: args.out ?? './dist',
    title: args.title,
    clean: Boolean(args.clean),
    base: args.base ?? '/',
  };

  switch (command) {
    case 'build': {
      const srcDir = args._[1];
      if (!srcDir) { console.error('Error: build requires <srcDir>'); process.exit(1); }
      await build(srcDir, opts);
      break;
    }
    case 'serve': {
      const { serve } = await import('./serve.js');
      const srcDir = args._[1];
      if (!srcDir) { console.error('Error: serve requires <srcDir>'); process.exit(1); }
      await serve(srcDir, opts);
      break;
    }
    case 'init': {
      const { init } = await import('./init.js');
      await init(args._[1] ?? '.');
      break;
    }
    default:
      console.error(`Error: unknown command "${command}"\n`);
      console.log(HELP);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
