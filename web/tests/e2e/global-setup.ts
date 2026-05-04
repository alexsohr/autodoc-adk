import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? 'http://localhost:8080';
const REPO_ROOT = path.resolve(__dirname, '../../..');
const MANIFEST = path.resolve(__dirname, '.seed-data.json');

async function waitForHealth(timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown = null;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${API_BASE}/health`);
      if (r.ok) return;
      lastErr = new Error(`health returned ${r.status}`);
    } catch (e) {
      lastErr = e;
    }
    await new Promise(r => setTimeout(r, 1_000));
  }
  throw new Error(
    `API not ready at ${API_BASE}/health after ${timeoutMs}ms. ` +
    `Is 'make dev-up' + 'AUTODOC_E2E=1 make api' running? Last error: ${String(lastErr)}`
  );
}

async function resetSeededRows(): Promise<void> {
  const r = await fetch(`${API_BASE}/_e2e/reset`, { method: 'POST' });
  if (!r.ok) {
    throw new Error(
      `_e2e/reset returned ${r.status}. Is the API running with AUTODOC_E2E=1?`
    );
  }
}

function runSeed(): void {
  const result = spawnSync('uv', ['run', 'python', '-m', 'tests.e2e_seed.seed_playwright'], {
    cwd: REPO_ROOT,
    env: { ...process.env, AUTODOC_E2E: '1' },
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    throw new Error(`seed_playwright exited with status ${result.status}`);
  }
}

function validateManifest(): void {
  if (!existsSync(MANIFEST)) {
    throw new Error(`Seed manifest not written: ${MANIFEST}`);
  }
  const data = JSON.parse(readFileSync(MANIFEST, 'utf8'));
  for (const slug of ['digitalClock', 'debugRepo', 'dbg2'] as const) {
    if (!data?.repos?.[slug]?.id) {
      throw new Error(`Manifest missing repos.${slug}.id`);
    }
  }
}

export default async function globalSetup(): Promise<void> {
  await waitForHealth();
  await resetSeededRows();
  runSeed();
  validateManifest();
}
