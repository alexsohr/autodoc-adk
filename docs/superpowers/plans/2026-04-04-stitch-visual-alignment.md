# Stitch Visual Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 7 visual gaps between the Stitch "Repo Landing Page" designs and the React frontend so the app matches the design system.

**Architecture:** Theme-first approach — fix as much as possible through CSS token changes in `autodoc-theme.css` and `index.html`, with targeted component edits for icon swaps and Salt DS form migration. No structural rewrites.

**Tech Stack:** React 19, Salt DS (`@salt-ds/core`, `@salt-ds/icons`), Material Symbols Outlined (Google Fonts), Vite 6, Vitest, Storybook 8

**Spec:** `docs/superpowers/specs/2026-04-04-stitch-visual-alignment-design.md`

---

### Task 1: Font Loading & Material Symbols Base Style

**Files:**
- Modify: `web/index.html`
- Modify: `web/src/theme/autodoc-theme.css`

- [ ] **Step 1: Add Google Fonts links to index.html**

Add Inter (400-800) and Material Symbols Outlined `<link>` tags in the `<head>`, before the viewport meta tag's closing:

```html
<!-- web/index.html — add after line 6 (viewport meta) -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Add Material Symbols base style to theme**

Add after the `:root` block closing brace (after line 91 in `autodoc-theme.css`):

```css
/* ============================================================
   MATERIAL SYMBOLS — base icon style
   ============================================================ */

.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
}
```

- [ ] **Step 3: Verify fonts load**

Run: `cd web && npm run dev`

Open browser, inspect body element. `font-family` should show "Inter" as computed value, not system fallback. Material Symbols should render when you add a test `<span class="material-symbols-outlined">home</span>` in any component.

- [ ] **Step 4: Commit**

```bash
git add web/index.html web/src/theme/autodoc-theme.css
git commit -m "feat(web): load Inter font and Material Symbols from Google Fonts"
```

---

### Task 2: MaterialIcon Helper Component

**Files:**
- Create: `web/src/components/shared/MaterialIcon.tsx`
- Create: `web/src/components/shared/__tests__/MaterialIcon.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/shared/__tests__/MaterialIcon.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MaterialIcon } from "../MaterialIcon";

describe("MaterialIcon", () => {
  it("renders a span with the correct icon name", () => {
    render(<MaterialIcon name="home" />);
    const icon = screen.getByText("home");
    expect(icon).toBeDefined();
    expect(icon.className).toContain("material-symbols-outlined");
  });

  it("applies custom size via fontSize", () => {
    render(<MaterialIcon name="settings" size={20} />);
    const icon = screen.getByText("settings");
    expect(icon.style.fontSize).toBe("20px");
  });

  it("does not set fontSize when size is omitted", () => {
    render(<MaterialIcon name="search" />);
    const icon = screen.getByText("search");
    expect(icon.style.fontSize).toBe("");
  });

  it("passes through className", () => {
    render(<MaterialIcon name="folder" className="custom-class" />);
    const icon = screen.getByText("folder");
    expect(icon.className).toContain("material-symbols-outlined");
    expect(icon.className).toContain("custom-class");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/shared/__tests__/MaterialIcon.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// web/src/components/shared/MaterialIcon.tsx
interface MaterialIconProps {
  name: string;
  size?: number;
  className?: string;
}

export function MaterialIcon({ name, size, className }: MaterialIconProps) {
  const classes = ["material-symbols-outlined", className].filter(Boolean).join(" ");
  return (
    <span className={classes} style={size ? { fontSize: `${size}px` } : undefined}>
      {name}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/shared/__tests__/MaterialIcon.test.tsx`

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/shared/MaterialIcon.tsx web/src/components/shared/__tests__/MaterialIcon.test.tsx
git commit -m "feat(web): add MaterialIcon helper component for hybrid icon system"
```

---

### Task 3: Design Token Expansion

**Files:**
- Modify: `web/src/theme/autodoc-theme.css`

- [ ] **Step 1: Add missing color tokens**

Add these 4 missing tokens inside the `:root` block, after the existing secondary tokens (after line 34):

```css
  --autodoc-on-secondary-fixed: #06154e;
  --autodoc-on-secondary-fixed-variant: #36437b;
```

And after the existing tertiary tokens (after line 40):

```css
  --autodoc-on-tertiary-fixed: #331200;
  --autodoc-on-tertiary-fixed-variant: #763300;
```

- [ ] **Step 2: Add sidebar-specific tokens**

Add inside `:root`, after the inverse tokens (after line 75):

```css
  /* Sidebar — uses Stitch overrideNeutralColor */
  --autodoc-sidebar-bg: #1e1e2e;
  --autodoc-sidebar-text-muted: #9898b0;
  --autodoc-sidebar-text-dim: #6b6b82;
  --autodoc-sidebar-text-hover: #e0e0ec;
  --autodoc-sidebar-item-hover-bg: rgba(255, 255, 255, 0.05);
  --autodoc-sidebar-item-active-bg: rgba(59, 130, 246, 0.2);
  --autodoc-sidebar-item-active-border: #3b82f6;
```

- [ ] **Step 3: Add glassmorphism combined token**

Add inside `:root`, after the existing glass tokens (after line 87):

```css
  --autodoc-glass-bg: rgba(255, 255, 255, 0.85);
```

- [ ] **Step 4: Add border-radius scale**

Add a new section after the gradient CTA section (after line 91), before the Salt DS overrides:

```css
/* ============================================================
   BORDER RADIUS SCALE — from Stitch Tailwind config
   ============================================================ */
:root {
  --autodoc-radius-default: 0.125rem;
  --autodoc-radius-lg: 0.25rem;
  --autodoc-radius-xl: 0.5rem;
  --autodoc-radius-full: 0.75rem;
  --autodoc-radius-pill: 9999px;
}
```

- [ ] **Step 5: Add spacing scale**

Add immediately after the border-radius section:

```css
/* ============================================================
   SPACING SCALE — from Stitch spacingScale: 2
   ============================================================ */
:root {
  --autodoc-spacing-xs: 0.25rem;
  --autodoc-spacing-sm: 0.5rem;
  --autodoc-spacing-md: 0.75rem;
  --autodoc-spacing-lg: 1rem;
  --autodoc-spacing-xl: 1.5rem;
  --autodoc-spacing-2xl: 2rem;
  --autodoc-spacing-3xl: 3rem;
}
```

- [ ] **Step 6: Expand typography scale**

Add new classes after the existing `.autodoc-label-md` rule (after line 250):

```css
.autodoc-display-md {
  font-size: 2.5rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.autodoc-display-sm {
  font-size: 2rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.autodoc-headline-sm {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.35;
}

.autodoc-body-lg {
  font-size: 1rem;
  font-weight: 400;
  line-height: 1.6;
}

.autodoc-body-sm {
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.5;
}

.autodoc-label-lg {
  font-size: 0.875rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.autodoc-label-sm {
  font-size: 0.65rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

- [ ] **Step 7: Update spacing helpers to use scale tokens**

Replace the existing spacing helpers (lines 317-323):

```css
.autodoc-section-gap {
  margin-bottom: var(--autodoc-spacing-xl);
}

.autodoc-page-padding {
  padding: var(--autodoc-spacing-xl) var(--autodoc-spacing-2xl);
}
```

- [ ] **Step 8: Commit**

```bash
git add web/src/theme/autodoc-theme.css
git commit -m "feat(web): expand design tokens — colors, radius, spacing, typography scale"
```

---

### Task 4: Sidebar Tokenization

**Files:**
- Modify: `web/src/components/layout/Sidebar.css`
- Modify: `web/src/components/layout/Sidebar.tsx`
- Modify: `web/src/theme/autodoc-theme.css` (sidebar theme section)

- [ ] **Step 1: Update sidebar theme section**

In `autodoc-theme.css`, replace the sidebar section (lines 185-194):

```css
.autodoc-sidebar {
  background-color: var(--autodoc-sidebar-bg);
  color: var(--autodoc-inverse-on-surface);
}

.autodoc-sidebar-item--active {
  background-color: var(--autodoc-sidebar-item-active-bg);
  color: #bfdbfe;
  border-left: 4px solid var(--autodoc-sidebar-item-active-border);
  border-radius: var(--autodoc-radius-xl);
}
```

- [ ] **Step 2: Tokenize Sidebar.css hardcoded colors**

In `Sidebar.css`, replace every hardcoded hex color and rgba value:

- `color: #ffffff` → `color: var(--autodoc-inverse-on-surface)`
- `color: #9898b0` → `color: var(--autodoc-sidebar-text-muted)`
- `color: #6b6b82` → `color: var(--autodoc-sidebar-text-dim)`
- `color: #e0e0ec` → `color: var(--autodoc-sidebar-text-hover)`
- `background-color: rgba(255, 255, 255, 0.05)` → `background-color: var(--autodoc-sidebar-item-hover-bg)`
- `background-color: rgba(255, 255, 255, 0.08)` → `background-color: var(--autodoc-sidebar-item-hover-bg)`

Use `replace_all` where the same value appears multiple times.

- [ ] **Step 3: Replace Salt DS icons with Material Symbols in Sidebar.tsx**

Replace the icon imports:

```tsx
// REMOVE these imports:
// import {
//   HomeIcon,
//   DashboardIcon,
//   RunReportIcon,
//   BarChartIcon,
//   StorageIcon,
//   PinIcon,
//   ChevronLeftIcon,
//   ChevronRightIcon,
// } from "@salt-ds/icons";

// ADD:
import { ChevronLeftIcon, ChevronRightIcon } from "@salt-ds/icons";
import { MaterialIcon } from "../shared/MaterialIcon";
```

Keep `ChevronLeftIcon` and `ChevronRightIcon` from Salt DS (interactive toggle button — hybrid approach).

Update the mainNav and adminNav arrays to use MaterialIcon:

```tsx
const mainNav = [
  { label: "Repositories", icon: <MaterialIcon name="folder" size={20} />, path: "/" },
];

const adminNav = [
  { label: "System Health", icon: <MaterialIcon name="monitoring" size={20} />, path: "/admin/health" },
  { label: "All Jobs", icon: <MaterialIcon name="work_history" size={20} />, path: "/admin/jobs" },
  { label: "Usage & Costs", icon: <MaterialIcon name="bar_chart" size={20} />, path: "/admin/costs" },
  { label: "MCP Servers", icon: <MaterialIcon name="storage" size={20} />, path: "/admin/mcp" },
];
```

Update the brand icon to use MaterialIcon:

```tsx
<div className="sidebar__brand-icon">
  <MaterialIcon name="auto_awesome" size={18} />
</div>
```

Update pinned repos icon:

```tsx
{/* Replace PinIcon with MaterialIcon */}
<MaterialIcon name="push_pin" size={16} />
```

- [ ] **Step 4: Verify sidebar renders correctly**

Run: `cd web && npm run dev`

Check sidebar: dark background should be `#1e1e2e`, icons should be Material Symbols style, active item should have left blue border, colors should use CSS variables.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/layout/Sidebar.css web/src/components/layout/Sidebar.tsx web/src/theme/autodoc-theme.css
git commit -m "feat(web): tokenize sidebar colors and swap to Material Symbols icons"
```

---

### Task 5: TopBar & ContextSearch Glass Tokenization

**Files:**
- Modify: `web/src/components/layout/TopBar.css`
- Modify: `web/src/components/layout/ContextSearch.css`

- [ ] **Step 1: Replace hardcoded glass values in TopBar.css**

Replace:
```css
/* OLD */
background-color: rgba(255, 255, 255, 0.85);
backdrop-filter: blur(20px);
```

With:
```css
/* NEW */
background-color: var(--autodoc-glass-bg);
backdrop-filter: blur(var(--autodoc-glass-blur));
-webkit-backdrop-filter: blur(var(--autodoc-glass-blur));
```

- [ ] **Step 2: Replace hardcoded glass values in ContextSearch.css**

Replace:
```css
/* OLD */
background-color: rgba(255, 255, 255, 0.8);
backdrop-filter: blur(16px);
```

With:
```css
/* NEW */
background-color: var(--autodoc-glass-bg);
backdrop-filter: blur(var(--autodoc-glass-blur));
-webkit-backdrop-filter: blur(var(--autodoc-glass-blur));
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/layout/TopBar.css web/src/components/layout/ContextSearch.css
git commit -m "feat(web): use glass tokens in TopBar and ContextSearch CSS"
```

---

### Task 6: Input Theme Overrides & RepoListPage Form Refactor

**Files:**
- Modify: `web/src/theme/autodoc-theme.css`
- Modify: `web/src/pages/RepoListPage.tsx`

- [ ] **Step 1: Strengthen Salt DS input overrides in theme**

In `autodoc-theme.css`, replace the existing input section (lines 308-311):

```css
/* ============================================================
   12. INPUT FIELDS — tonal bg, no border, bottom-bar focus
   ============================================================ */

.salt-provider [class*="saltInput"] {
  background-color: var(--autodoc-surface-container-high);
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: var(--autodoc-radius-xl) var(--autodoc-radius-xl) 0 0;
  transition: border-color 200ms ease-out;
}

.salt-provider [class*="saltInput"]:focus-within {
  border-bottom-color: var(--autodoc-primary);
}

.salt-provider [class*="saltFormField"] {
  background-color: transparent;
}
```

- [ ] **Step 2: Update RepoListPage imports**

Add Salt DS form imports in `RepoListPage.tsx`:

```tsx
import {
  Button,
  Dialog,
  DialogHeader,
  DialogContent,
  DialogActions,
  Input,
  FormField,
  FormFieldLabel,
} from "@salt-ds/core";
```

- [ ] **Step 3: Replace raw inputs in AddRepoDialog**

Find the "Add Repository" dialog form fields in `RepoListPage.tsx`. Replace each raw `<input>` with Salt DS components. For example:

```tsx
{/* Repository URL field — replace raw <input> */}
<FormField>
  <FormFieldLabel>Repository URL</FormFieldLabel>
  <Input
    value={repoUrl}
    onChange={(event) => setRepoUrl(event.target.value)}
    placeholder="https://github.com/org/repo"
  />
</FormField>

{/* Name field */}
<FormField>
  <FormFieldLabel>Name</FormFieldLabel>
  <Input
    value={repoName}
    onChange={(event) => setRepoName(event.target.value)}
    placeholder="my-repo"
  />
</FormField>

{/* Default Branch field */}
<FormField>
  <FormFieldLabel>Default Branch</FormFieldLabel>
  <Input
    value={defaultBranch}
    onChange={(event) => setDefaultBranch(event.target.value)}
    placeholder="main"
  />
</FormField>

{/* Description — use Input with a style override for textarea behavior */}
<FormField>
  <FormFieldLabel>Description</FormFieldLabel>
  <Input
    value={description}
    onChange={(event) => setDescription(event.target.value)}
    placeholder="Brief description of the repository"
  />
</FormField>
```

Remove inline `style={}` on these inputs — the theme CSS handles all styling.

- [ ] **Step 4: Remove inline input styles**

Search for any `style={{ ... border: "1px solid" ... }}` or `style={{ ... backgroundColor: "white" ... }}` on form inputs in RepoListPage.tsx and remove them. The Salt DS theme overrides handle the correct appearance.

- [ ] **Step 5: Verify form renders**

Run: `cd web && npm run dev`

Navigate to the repo list page, click "Add Repo". Inputs should have tinted `#e8e6fc` background, no border, 2px primary bottom-bar on focus.

- [ ] **Step 6: Commit**

```bash
git add web/src/theme/autodoc-theme.css web/src/pages/RepoListPage.tsx
git commit -m "feat(web): refactor RepoListPage forms to Salt DS Input with tonal styling"
```

---

### Task 7: SettingsTab Form Refactor

**Files:**
- Modify: `web/src/pages/tabs/SettingsTab.tsx`

- [ ] **Step 1: Add Salt DS form imports**

```tsx
import { Button, Input, FormField, FormFieldLabel } from "@salt-ds/core";
```

- [ ] **Step 2: Replace raw form elements**

Find each raw `<input>` and `<textarea>` in SettingsTab.tsx. Replace with Salt DS equivalents:

For text inputs:
```tsx
<FormField>
  <FormFieldLabel>{label}</FormFieldLabel>
  <Input
    value={value}
    onChange={(event) => setValue(event.target.value)}
    placeholder={placeholder}
  />
</FormField>
```

For read-only fields (like Repository URL):
```tsx
<FormField>
  <FormFieldLabel>Repository URL</FormFieldLabel>
  <Input value={repoUrl} readOnly />
</FormField>
```

- [ ] **Step 3: Remove inline input styles**

Remove shared `inputStyle` objects and any inline `style={}` on form elements. The theme handles it.

- [ ] **Step 4: Clean up hardcoded danger zone colors**

Replace `rgba(186, 26, 26, 0.06)` with `var(--autodoc-error-container)` at reduced opacity:

```tsx
style={{ background: "color-mix(in srgb, var(--autodoc-error-container) 30%, transparent)" }}
```

Or define a token `--autodoc-danger-bg` in the theme if multiple places use it.

- [ ] **Step 5: Verify settings page**

Run: `cd web && npm run dev`

Navigate to a repo → Settings tab. All form fields should use Salt DS styling with tonal backgrounds.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/tabs/SettingsTab.tsx
git commit -m "feat(web): refactor SettingsTab forms to Salt DS Input components"
```

---

### Task 8: StatusBadge Stitch Functional Tokens

**Files:**
- Modify: `web/src/theme/autodoc-theme.css`

- [ ] **Step 1: Update badge color rules**

In `autodoc-theme.css`, replace the badge color rules (lines 267-290):

```css
.autodoc-badge--success {
  background-color: var(--autodoc-secondary-fixed);
  color: var(--autodoc-on-secondary-fixed-variant);
}

.autodoc-badge--warning {
  background-color: var(--autodoc-tertiary-fixed);
  color: var(--autodoc-on-tertiary-fixed-variant);
}

.autodoc-badge--error {
  background-color: var(--autodoc-error-container);
  color: var(--autodoc-on-error-container);
}

.autodoc-badge--info {
  background-color: var(--autodoc-info-bg);
  color: var(--autodoc-info);
}

.autodoc-badge--neutral {
  background-color: var(--autodoc-surface-container-high);
  color: var(--autodoc-on-surface-variant);
}
```

Note: success now uses `secondary-fixed` (blue-tinted) per the Stitch spec instead of the custom green `success-bg`. Warning uses `tertiary-fixed` (warm orange-tinted) instead of custom `warning-bg`. Error and info/neutral stay the same.

- [ ] **Step 2: Verify badge appearance**

Run: `cd web && npm run dev`

Check any page with status badges. Success badges should be light blue (#dde1ff bg), warning should be warm peach (#ffdbc9 bg), error should be light red (#ffdad6 bg).

- [ ] **Step 3: Commit**

```bash
git add web/src/theme/autodoc-theme.css
git commit -m "feat(web): update status badges to use Stitch functional color tokens"
```

---

### Task 9: MetricCard Icon Enhancement

**Files:**
- Modify: `web/src/components/shared/MetricCard.tsx`
- Create: `web/src/components/shared/__tests__/MetricCard.test.tsx`

- [ ] **Step 1: Write failing test for icon prop**

```tsx
// web/src/components/shared/__tests__/MetricCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SaltProvider } from "@salt-ds/core";
import { MetricCard } from "../MetricCard";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SaltProvider mode="light">{children}</SaltProvider>
);

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Doc Pages" value="24" />, { wrapper });
    expect(screen.getByText("Doc Pages")).toBeDefined();
    expect(screen.getByText("24")).toBeDefined();
  });

  it("renders icon when provided", () => {
    render(<MetricCard label="Doc Pages" value="24" icon="description" />, { wrapper });
    const icon = screen.getByText("description");
    expect(icon).toBeDefined();
    expect(icon.className).toContain("material-symbols-outlined");
  });

  it("does not render icon container when icon is omitted", () => {
    const { container } = render(<MetricCard label="Score" value="8.2" />, { wrapper });
    expect(container.querySelector(".material-symbols-outlined")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/components/shared/__tests__/MetricCard.test.tsx`

Expected: FAIL — icon prop not accepted or icon not rendered.

- [ ] **Step 3: Update MetricCard component**

Update `MetricCard.tsx` to accept an optional `icon` prop:

```tsx
import { Card } from "@salt-ds/core";
import { MaterialIcon } from "./MaterialIcon";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: string;
  subtitle?: string;
  icon?: string;
}

export function MetricCard({ label, value, delta, subtitle, icon }: MetricCardProps) {
  return (
    <Card
      style={{
        padding: "var(--autodoc-spacing-lg)",
        background: "var(--autodoc-surface-container-low)",
        boxShadow: "var(--autodoc-shadow-ambient)",
        borderRadius: "var(--autodoc-radius-xl)",
      }}
    >
      {icon && (
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "var(--autodoc-radius-xl)",
            background: "var(--autodoc-primary-fixed)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "var(--autodoc-spacing-sm)",
          }}
        >
          <MaterialIcon name={icon} size={20} />
        </div>
      )}
      <div className="autodoc-label-md" style={{ color: "var(--autodoc-on-surface-variant)" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "0.25rem" }}>
        {value}
      </div>
      {delta && (
        <div
          style={{
            fontSize: "0.75rem",
            color: delta.startsWith("+") || delta.startsWith("↑")
              ? "var(--autodoc-success)"
              : "var(--autodoc-error)",
            marginTop: "0.25rem",
          }}
        >
          {delta}
        </div>
      )}
      {subtitle && (
        <div style={{ fontSize: "0.75rem", color: "var(--autodoc-on-surface-variant)", marginTop: "0.25rem" }}>
          {subtitle}
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run src/components/shared/__tests__/MetricCard.test.tsx`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/shared/MetricCard.tsx web/src/components/shared/__tests__/MetricCard.test.tsx
git commit -m "feat(web): add icon prop to MetricCard with tinted container"
```

---

### Task 10: OverviewTab & SystemHealthPage Material Icons

**Files:**
- Modify: `web/src/pages/tabs/OverviewTab.tsx`
- Modify: `web/src/pages/admin/SystemHealthPage.tsx`

- [ ] **Step 1: Add MaterialIcon import to OverviewTab**

```tsx
import { MaterialIcon } from "@/components/shared/MaterialIcon";
```

- [ ] **Step 2: Add icons to MetricCard usage in OverviewTab**

Find the MetricCard instances in OverviewTab.tsx and add icon props:

```tsx
<MetricCard label="Doc Pages" value={docPages} icon="description" delta={pagesDelta} />
<MetricCard label="Quality Score" value={qualityScore} icon="high_quality" delta={qualityDelta} />
<MetricCard label="Scopes" value={scopeCount} icon="layers" subtitle={scopeSubtitle} />
<MetricCard label="Last Sync" value={lastSync} icon="schedule" subtitle={syncSubtitle} />
```

- [ ] **Step 3: Add MaterialIcon import to SystemHealthPage**

```tsx
import { MaterialIcon } from "@/components/shared/MaterialIcon";
```

- [ ] **Step 4: Replace inline SVG icons in SystemHealthPage metric cards**

Find the `MetricCardWithStatus` component in SystemHealthPage.tsx. Replace its inline SVG icon rendering with MaterialIcon:

```tsx
{/* Replace inline SVG with MaterialIcon */}
<div style={{
  width: 40,
  height: 40,
  borderRadius: "var(--autodoc-radius-xl)",
  background: "rgba(38, 77, 217, 0.1)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}}>
  <MaterialIcon name={iconName} size={24} />
</div>
```

Map the 4 infrastructure metric cards to Material Symbol names:
- API Cluster → `api`
- Prefect Server → `hub`
- PostgreSQL → `database`
- Active Workers → `engineering`

- [ ] **Step 5: Replace hardcoded `rgba(38, 77, 217, 0.1)` with token**

Use `color-mix(in srgb, var(--autodoc-primary) 10%, transparent)` instead of hardcoded rgba.

- [ ] **Step 6: Verify pages**

Run: `cd web && npm run dev`

Check Overview tab — metric cards should show Material Symbol icons in blue tinted containers. Check System Health — infrastructure cards should show Material Symbol icons.

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/tabs/OverviewTab.tsx web/src/pages/admin/SystemHealthPage.tsx
git commit -m "feat(web): add Material Symbol icons to metric cards on Overview and SystemHealth pages"
```

---

### Task 11: Storybook Theming

**Files:**
- Create: `web/.storybook/preview.tsx`

- [ ] **Step 1: Create preview.tsx with Salt DS provider**

```tsx
// web/.storybook/preview.tsx
import type { Preview } from "@storybook/react";
import { SaltProvider } from "@salt-ds/core";
import React from "react";

import "@salt-ds/theme/index.css";
import "../src/theme/autodoc-theme.css";
import "../src/index.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <SaltProvider mode="light">
        <div style={{ padding: "1rem", background: "var(--autodoc-surface)" }}>
          <Story />
        </div>
      </SaltProvider>
    ),
  ],
};

export default preview;
```

- [ ] **Step 2: Verify Storybook builds**

Run: `cd web && npx storybook build`

Expected: Build succeeds with no errors. Stories now render with Inter font, Stitch colors, and Salt DS theme.

- [ ] **Step 3: Commit**

```bash
git add web/.storybook/preview.tsx
git commit -m "feat(web): add Storybook preview with Salt DS theme wrapper"
```

---

### Task 12: Build Verification & Visual Spot-Check

**Files:** None (verification only)

- [ ] **Step 1: Run frontend tests**

Run: `cd web && npm test`

Expected: All tests pass (existing + new MaterialIcon and MetricCard tests).

- [ ] **Step 2: Run production build**

Run: `cd web && npm run build`

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Run lint**

Run: `cd web && npx tsc --noEmit`

Expected: No type errors.

- [ ] **Step 4: Visual spot-check key pages**

Run: `cd web && npm run dev`

Check these pages against the Stitch design reference files in `web/.design-reference/`:

1. **Repo Landing Page** — Inter font loaded, sidebar dark (#1e1e2e), Material Symbol nav icons, gradient CTA button on "Add Repo"
2. **Repo Overview Tab** — MetricCards with icons, tonal card backgrounds, status badges with Stitch functional colors
3. **System Health** — Material Symbol infrastructure icons, tonal layering, gradient CTA on auto-scale section
4. **Settings Tab** — Salt DS Input components with tonal backgrounds, no 1px borders

- [ ] **Step 5: Final commit if any fixes needed**

If the visual spot-check reveals minor issues, fix and commit:

```bash
git add -A
git commit -m "fix(web): visual alignment polish from spot-check"
```
