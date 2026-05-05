import { defineConfig, devices } from '@playwright/test';
import { defineBddConfig, cucumberReporter } from 'playwright-bdd';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Generate Playwright test files from .feature files into .features-gen/.
// Returns the directory the BDD project's testDir should point at.
// Generated *.feature.spec.js files auto-discover the role-aware `test`
// fixture re-exported by steps/bdd.ts (which wraps support/auth.ts) because
// that file is matched by the `steps` glob below.
const bddTestDir = defineBddConfig({
  features: path.resolve(__dirname, 'features/**/*.feature'),
  steps: [
    path.resolve(__dirname, 'steps/**/*.ts'),
    path.resolve(__dirname, 'support/hooks.ts'),
  ],
  featuresRoot: __dirname,
  outputDir: path.resolve(__dirname, '.features-gen'),
  missingSteps: 'fail-on-gen',
});

const specsTestDir = path.resolve(__dirname, 'specs');

export default defineConfig({
  // Per-project testDir below — top-level testDir intentionally omitted.
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: path.resolve(__dirname, '../../playwright-report'), open: 'never' }],
    cucumberReporter('html', {
      outputFile: path.resolve(__dirname, 'cucumber-report/index.html'),
      externalAttachments: true,
    }),
  ],
  globalSetup: path.resolve(__dirname, 'global-setup.ts'),
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    extraHTTPHeaders: {
      'X-Forwarded-User': 'e2e-admin@test',
      'X-Forwarded-Email': 'e2e-admin@test',
      'X-Forwarded-Role': 'admin',
    },
  },
  projects: [
    // Existing hand-written specs (specs/0N-*.spec.ts) — unchanged behavior.
    { name: 'specs-chromium', testDir: specsTestDir, use: { ...devices['Desktop Chrome'] } },
    { name: 'specs-firefox',  testDir: specsTestDir, use: { ...devices['Desktop Firefox'] } },
    // BDD scenarios generated from features/*.feature.
    { name: 'bdd-chromium',   testDir: bddTestDir,   use: { ...devices['Desktop Chrome'] } },
    { name: 'bdd-firefox',    testDir: bddTestDir,   use: { ...devices['Desktop Firefox'] } },
  ],
});
