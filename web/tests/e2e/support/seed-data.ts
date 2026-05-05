import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export type SeedRepo = {
  id: string;
  fullName: string;
  name: string;
  provider: string;
};

export type SeedManifest = {
  repos: {
    digitalClock: SeedRepo;
    debugRepo: SeedRepo;
    dbg2: SeedRepo;
    healthy: SeedRepo;
    running: SeedRepo;
    failed: SeedRepo;
    pending: SeedRepo;
  };
  jobs: {
    completedJobId: string;
  };
};

const MANIFEST_PATH = path.resolve(__dirname, '..', '.seed-data.json');

// Lazy load: the manifest is written by globalSetup AFTER this module is
// imported by step files. bddgen codegen imports step files (and therefore
// this module) before globalSetup runs, so a synchronous file read at module
// scope crashes CI with ENOENT. Defer the read until first property access.
let _data: SeedManifest | null = null;
function load(): SeedManifest {
  if (_data === null) {
    _data = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8')) as SeedManifest;
  }
  return _data;
}

export const REPOS = new Proxy({} as SeedManifest['repos'], {
  get: (_t, prop: string) => load().repos[prop as keyof SeedManifest['repos']],
  has: (_t, prop: string) => prop in load().repos,
  ownKeys: () => Object.keys(load().repos),
  getOwnPropertyDescriptor: (_t, prop: string) => ({
    value: load().repos[prop as keyof SeedManifest['repos']],
    enumerable: true,
    configurable: true,
  }),
});

export const JOBS = new Proxy({} as SeedManifest['jobs'], {
  get: (_t, prop: string) => load().jobs[prop as keyof SeedManifest['jobs']],
});

export type SeedRepoKey = keyof SeedManifest['repos'];

// Scenarios reference repositories by symbolic seed name (e.g. "digitalClock"),
// not by their displayed `name`. This helper resolves the symbolic name to the
// seed record so step text stays stable when displayed names or generated IDs
// change.
export function resolveSeedRepo(symbolic: string): SeedRepo {
  if (!(symbolic in REPOS)) {
    throw new Error(
      `Unknown seed repo "${symbolic}". Known keys: ${Object.keys(REPOS).join(', ')}`,
    );
  }
  return REPOS[symbolic as SeedRepoKey];
}
