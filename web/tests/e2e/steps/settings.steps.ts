import { Then, When } from './bdd';
import { REPOS, type SeedRepo } from '../support/seed-data';

// ─────────────────────────────────────────────────────────────────────────────
// Seed lookup helper
//
// PTS-2.7 placeholders don't reference a repo today, but the helper is kept
// here for symmetry with other steps files so future Settings scenarios can
// resolve symbolic seed names without a refactor. Three local copies (here,
// in workspace.steps.ts, in docs.steps.ts) are intentional for this PR; lifting
// to a shared support module is a follow-up.
// ─────────────────────────────────────────────────────────────────────────────
type SeedKey = keyof typeof REPOS;

function resolveSeedRepo(symbolic: string): SeedRepo {
  if (!(symbolic in REPOS)) {
    throw new Error(
      `Unknown seed repo "${symbolic}". Known keys: ${Object.keys(REPOS).join(', ')}`,
    );
  }
  return REPOS[symbolic as SeedKey];
}

// ─────────────────────────────────────────────────────────────────────────────
// PTS-2.7 — Placeholder steps (Settings tab sub-navigation)
//
// PTS-2.7 is tagged @todo and skipped at runtime by support/hooks.ts.
// playwright-bdd codegen requires every step in every scenario to have a
// definition, even when the scenario will be skipped — so each placeholder
// below resolves immediately. They will be replaced with real implementations
// in the per-scenario PR that removes the @todo tag.
// See features/README.md § Authoring a new feature.
//
// When implementing, point assertions at the SettingsTab PO locators
// (subTab(name), generalSection, dangerZone). Add testids as needed for the
// per-sub-tab content panels (Branches table, Webhooks fields, AutoDoc YAML
// editor) and the active-state attribute on the secondary nav buttons.
// ─────────────────────────────────────────────────────────────────────────────

Then('the Settings sub-tab {string} is visible', async ({}, _name: string) => {
  // @todo: implement when PTS-2.7 is wired up — SettingsTab.subTab(name) visible.
  await Promise.resolve();
});

When('I click the Settings sub-tab {string}', async ({}, _name: string) => {
  // @todo: implement when PTS-2.7 is wired up — SettingsTab.subTab(name).click().
  await Promise.resolve();
});

Then(
  'the Settings sub-tab {string} is marked active',
  async ({}, _name: string) => {
    // @todo: implement when PTS-2.7 is wired up — assert the clicked sub-tab
    //        carries the [active] attribute (per 00-index.md observation:
    //        "sub-tab set to [active]"). May require an `aria-current` or
    //        `data-active` source-side hook.
    await Promise.resolve();
  },
);

Then(
  'the Settings General panel shows repository info fields and a schedule toggle',
  async () => {
    // @todo: implement when PTS-2.7 is wired up — assert
    //        SettingsTab.generalSection contains URL/Provider read-only
    //        fields plus the "Enable scheduled generation" checkbox.
    await Promise.resolve();
  },
);

Then(
  'the Settings Branches panel shows a branch mapping table',
  async () => {
    // @todo: implement when PTS-2.7 is wired up — needs a Branches panel
    //        testid in source + PO locator.
    await Promise.resolve();
  },
);

Then(
  'the Settings Webhooks panel shows the webhook URL and secret',
  async () => {
    // @todo: implement when PTS-2.7 is wired up — needs Webhooks panel
    //        testid in source + PO locator.
    await Promise.resolve();
  },
);

Then(
  'the Settings AutoDoc Config panel shows the YAML editor',
  async () => {
    // @todo: implement when PTS-2.7 is wired up — needs AutoDoc Config panel
    //        testid + a stable handle on the YAML editor textarea.
    await Promise.resolve();
  },
);

Then(
  'the Settings Danger Zone panel shows delete actions with confirmation',
  async () => {
    // @todo: implement when PTS-2.7 is wired up — assert SettingsTab.dangerZone
    //        contains a delete-repo trigger and a confirmation control.
    await Promise.resolve();
  },
);

void resolveSeedRepo;
