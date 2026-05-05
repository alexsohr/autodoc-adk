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

function load(): SeedManifest {
  return JSON.parse(readFileSync(MANIFEST_PATH, 'utf8')) as SeedManifest;
}

const _data = load();
export const REPOS = _data.repos;
export const JOBS = _data.jobs;

export type SeedRepoKey = keyof typeof REPOS;

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
