import { createBdd } from 'playwright-bdd';
import { authTest } from '../support/auth';

// Re-export so playwright-bdd codegen (via importTestFrom in playwright.config)
// can pick the role-aware test instance for generated .feature.spec.js files.
export const test = authTest;

// All step files import { Given, When, Then, Step, Before, After } from './bdd'
// so they receive the project's role-aware fixtures
// (page, asAdmin, asDeveloper, asViewer).
export const { Given, When, Then, Step, Before, After } = createBdd(authTest);
