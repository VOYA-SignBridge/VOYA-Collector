import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Guard against the whole class of bug where the frontend calls an API path the
 * nginx gateway does NOT route to the backend — so the request silently falls
 * through to the SPA (returns index.html) instead of hitting FastAPI.
 *
 * `backendRouted` MIRRORS the gateway's backend `location` blocks in
 * ../../../nginx.conf. If you change routing there, change it here too.
 *
 * The real bug this caught: AdminResourcesPage called bare "/admin/resources"
 * and "/admin/config/ignore-hardware" (not "/api/v1/admin/..."). "/admin" is a
 * frontend SPA route, so those calls returned HTML and the "mute alert" button
 * silently did nothing under the gateway.
 */
function backendRouted(p: string): boolean {
  if (/^\/api\/v1(\/|$)/.test(p)) return true;                       // ^/(api/v1|...)
  if (/^\/health(\/|$)/.test(p)) return true;                        // ^/health(/|$)
  if (/^\/(auth|classes|dataset|inference|jobs)(\/|$)/.test(p)) return true; // bare prefixes
  if (/^\/realtime\/(predict|models|health)$/.test(p)) return true;  // exact ($ anchored)
  if (/^\/upload\/(camera|video)$/.test(p)) return true;             // exact ($ anchored)
  return false;
}

// -- unit cases documenting the routing contract -----------------------------
describe('nginx gateway backend-routing rules', () => {
  it.each([
    ['/api/v1/admin/resources', true],
    ['/api/v1/training/start', true],
    ['/api/v1/tts/speak', true],
    ['/classes/list', true],
    ['/dataset/labels', true],
    ['/health', true],
    ['/health/ready', true],
    ['/jobs/', true],
    ['/inference/classes', true],
    ['/upload/camera', true],
    ['/upload/video', true],
    ['/realtime/predict', true],
    // must be routed to the SPA / would break as an API call:
    ['/admin/resources', false],              // <- the bug we fixed
    ['/admin/config/ignore-hardware', false], // <- the bug we fixed
    ['/training/start', false],               // bare -> must use /api/v1
    ['/tts/speak', false],                    // bare -> must use /api/v1
    ['/upload/video/process', false],         // $ anchor: only camera|video exact
    ['/realtime', false],                     // SPA page, not an API verb
  ])('routes %s -> backend=%s', (p, expected) => {
    expect(backendRouted(p as string)).toBe(expected);
  });
});

// -- the guard: scan every source file's real API calls ----------------------
const SRC_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../');

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const fp = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...sourceFiles(fp));
    else if (/\.(ts|tsx)$/.test(e.name) && !/\.(test|spec)\./.test(e.name)) out.push(fp);
  }
  return out;
}

// client.get/post/put/delete/patch("…"|`…`), fetch(…), new WebSocket/EventSource(…)
const CALL_RE =
  /(?:\.(?:get|post|put|delete|patch)|fetch|WebSocket|EventSource)\s*(?:<[^>]*>)?\s*\(\s*[`"']([^`"'$]*)/g;

describe('every frontend API call is routed to the backend by the gateway', () => {
  const violations: string[] = [];
  for (const file of sourceFiles(SRC_ROOT)) {
    const src = fs.readFileSync(file, 'utf-8');
    CALL_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = CALL_RE.exec(src)) !== null) {
      const p = m[1].trim();
      if (!p.startsWith('/') || p === '/') continue; // skip relative / root
      if (!backendRouted(p)) {
        violations.push(`${path.relative(SRC_ROOT, file)}: ${p}`);
      }
    }
  }

  it('has no API call the gateway would send to the SPA instead of FastAPI', () => {
    expect(
      violations,
      `Uncovered API paths (gateway would route these to the SPA):\n${violations.join('\n')}`,
    ).toEqual([]);
  });
});
