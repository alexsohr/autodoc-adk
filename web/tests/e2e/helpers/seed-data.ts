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
