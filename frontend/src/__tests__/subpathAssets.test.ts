import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Under a sub-path deploy (served at /voya/) an ABSOLUTE asset path like
 * "/logo.png" bypasses the injected <base href="/voya/"> and requests
 * origin-root "/logo.png" — which the campus proxy (only forwarding /voya/*)
 * never serves. Public assets must be referenced RELATIVELY ("logo.png") so
 * they resolve against <base>. This guards against re-introducing absolute
 * asset paths (the bug: favicon + logo + background were all absolute).
 */

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const INDEX_HTML = path.resolve(SRC, '..', 'index.html');

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const fp = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(fp));
    else if (/\.(ts|tsx|css|html)$/.test(e.name) && !/\.(test|spec)\./.test(e.name)) out.push(fp);
  }
  return out;
}

// src="/x.png" | href="/x.svg" | url(/x.png) — absolute path to a static asset.
const ASSET_RE =
  /(?:(?:src|href)\s*=\s*["']|url\(\s*["']?)(\/[a-zA-Z0-9_/-]+\.(?:png|jpe?g|svg|gif|webp|ico|avif))/gi;

describe('sub-path deploy: static assets must be referenced relatively', () => {
  it('has no absolute /asset paths that would 404 under /voya', () => {
    const bad: string[] = [];
    for (const f of [...walk(SRC), INDEX_HTML]) {
      const src = fs.readFileSync(f, 'utf-8');
      ASSET_RE.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = ASSET_RE.exec(src)) !== null) {
        bad.push(`${path.relative(path.resolve(SRC, '..'), f)}: ${m[1]}`);
      }
    }
    expect(
      bad,
      `Absolute asset paths break under a sub-path deploy — make them relative:\n${bad.join('\n')}`,
    ).toEqual([]);
  });
});
