import { Then, When } from './bdd';

// ─────────────────────────────────────────────────────────────────────────────
// PTS-3.4 — MCP Servers full page
//
// Scenario is tagged @todo + @known-gap and is auto-skipped at runtime by
// support/hooks.ts. Placeholder step bodies exist only to satisfy
// playwright-bdd's `missingSteps: 'fail-on-gen'` codegen contract.
//
// Two known gaps from docs/ui/00-index.md § Known Gaps are referenced inline
// in the .feature file:
//   - "MCP total_calls — Always 0, not tracked server-side" (00-index.md:136)
//   - "MCP integration URLs — Hardcoded to http://localhost:8080/mcp"
//     (00-index.md:145)
//
// These will be replaced with real implementations when the @todo tag is
// dropped and the McpPage PO is extended (subtitle, endpoint URL + copy
// button, available tools list, summary metric cards, integration code-snippet
// matching, security context sections).
// ─────────────────────────────────────────────────────────────────────────────

When('I open the MCP Servers page', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Servers heading is visible', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Servers subtitle is visible', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Server Status card is visible with a status badge', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Server Status card shows the endpoint URL with a copy button', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  // @known-gap: MCP integration URLs hardcoded to http://localhost:8080/mcp
  // (00-index.md:145).
  await Promise.resolve();
});

Then('the MCP Server Status card shows the available tools list', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP summary metric card {string} is visible', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.4
  // @known-gap: "Total Calls" always renders "0" — server-side tracking not
  // implemented (00-index.md:136).
  await Promise.resolve();
});

Then('the MCP Agent Integration Guide tab {string} is visible', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

When('I click the MCP Agent Integration Guide tab {string}', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Agent Integration Guide shows the matching code snippet', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('the MCP Security Context section {string} is visible', async ({}, _name: string) => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});

Then('no console errors were logged during MCP Servers page load', async () => {
  // @todo: implemented in per-area PR for PTS-3.4
  await Promise.resolve();
});
