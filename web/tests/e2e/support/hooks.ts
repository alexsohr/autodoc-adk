import { test } from '@playwright/test';
import { Before } from '../steps/bdd';

// Auto-skip any scenario tagged @todo. Mirrors test.skip(...) for Gherkin
// scenarios that document intent but are not yet implemented.
//
// `@known-gap` is a marker tag with NO behavior here — it's documented as a
// convention for scenarios describing accepted gaps in the product (e.g. a
// known limitation we don't intend to fix soon). Adding `@known-gap` to a
// scenario is a signal to readers, not a runtime instruction.
Before({ tags: '@todo' }, async () => {
  test.skip(true, 'Scenario tagged @todo — implementation pending.');
});
