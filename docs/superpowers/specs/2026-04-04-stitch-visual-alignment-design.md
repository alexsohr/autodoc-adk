# Design Spec: Stitch Visual Alignment

**Date:** 2026-04-04
**Status:** Approved
**Approach:** Theme-First (Approach A)
**Stitch Project:** "Repo Landing Page" (ID: 17903516435494788863)

## Problem

The React frontend does not match the Stitch design system. 7 gaps identified through side-by-side comparison of Stitch mockup HTML against the current implementation.

## Decisions

- **Icons:** Hybrid — Material Symbols Outlined for navigation/decorative icons (sidebar, metric cards, infrastructure), Salt DS icons for interactive components
- **Sidebar background:** `#1e1e2e` (Stitch `overrideNeutralColor`, matching mockup HTML)
- **Form inputs:** Targeted refactor — replace raw HTML inputs with Salt DS `Input`/`FormField` in RepoListPage and SettingsTab
- **Scope:** Full visual alignment pass across all 7 gaps

## Section 1: Font Loading & Typography

### Changes

**`web/index.html`** — Add `<link>` tags in `<head>`:
- Inter font: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap`
- Material Symbols Outlined: `https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap`

**`web/src/theme/autodoc-theme.css`** — Expand typography scale:
- `--autodoc-display-md`: 2.5rem, 600 weight, -0.02em tracking
- `--autodoc-display-sm`: 2rem, 600 weight, -0.02em tracking
- `--autodoc-headline-sm`: 1.25rem, 600 weight
- `--autodoc-body-lg`: 1rem, 400 weight, 1.6 line-height
- `--autodoc-body-sm`: 0.75rem, 400 weight, 1.5 line-height
- `--autodoc-label-lg`: 0.875rem, 500 weight, 0.05em tracking, uppercase
- `--autodoc-label-sm`: 0.65rem, 500 weight, 0.05em tracking, uppercase

Add base Material Symbols style:
```css
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}
```

## Section 2: Design Token Expansion

### Changes to `web/src/theme/autodoc-theme.css`

**Border-radius scale** (from Stitch Tailwind config):
- `--autodoc-radius-default`: 0.125rem
- `--autodoc-radius-lg`: 0.25rem
- `--autodoc-radius-xl`: 0.5rem
- `--autodoc-radius-full`: 0.75rem
- `--autodoc-radius-pill`: 9999px (badges)

**Spacing scale** (from Stitch `spacingScale: 2`):
- `--autodoc-spacing-xs`: 0.25rem
- `--autodoc-spacing-sm`: 0.5rem
- `--autodoc-spacing-md`: 0.75rem
- `--autodoc-spacing-lg`: 1rem
- `--autodoc-spacing-xl`: 1.5rem
- `--autodoc-spacing-2xl`: 2rem
- `--autodoc-spacing-3xl`: 3rem
- Replace hardcoded `section-gap` (1.5rem → `--autodoc-spacing-xl`) and `page-padding` (1.5rem 2rem → `--autodoc-spacing-xl --autodoc-spacing-2xl`)

**Missing color tokens** (~10 from Stitch `namedColors`):
- `--autodoc-primary-fixed-dim`: #b8c3ff
- `--autodoc-on-primary-fixed`: #001355
- `--autodoc-on-primary-fixed-variant`: #0035bd
- `--autodoc-secondary-fixed`: #dde1ff
- `--autodoc-secondary-fixed-dim`: #b8c3ff
- `--autodoc-on-secondary-fixed`: #06154e
- `--autodoc-on-secondary-fixed-variant`: #36437b
- `--autodoc-tertiary-fixed`: #ffdbc9
- `--autodoc-tertiary-fixed-dim`: #ffb68e
- `--autodoc-on-tertiary-fixed`: #331200
- `--autodoc-on-tertiary-fixed-variant`: #763300
- `--autodoc-surface-tint`: #294fdb
- `--autodoc-surface-bright`: #fcf8ff
- `--autodoc-surface-container-highest`: #e3e0f7

**Glassmorphism tokens** (ensure consistent usage):
- `--autodoc-glass-bg`: rgba(255, 255, 255, 0.85)
- `--autodoc-glass-blur`: blur(20px)
- `--autodoc-glass-opacity`: 0.85
- All CSS files must reference these instead of hardcoded rgba values

## Section 3: Sidebar & TopBar Tokenization

### `web/src/components/layout/Sidebar.css`

Replace hardcoded hex values:
- Background: `#2f2f40` → new `--autodoc-sidebar-bg: #1e1e2e`
- `#ffffff` → `var(--autodoc-inverse-on-surface)`
- `#9898b0` → new `var(--autodoc-sidebar-text-muted)`
- `#6b6b82` → new `var(--autodoc-sidebar-text-dim)`
- `#e0e0ec` → new `var(--autodoc-sidebar-text-hover)`
- `rgba(255, 255, 255, 0.05)` → new `var(--autodoc-sidebar-item-hover-bg)`
- Active nav item: add `border-left: 4px solid` + primary-tinted bg matching Stitch

### `web/src/components/layout/TopBar.css`

- `rgba(255, 255, 255, 0.85)` → `var(--autodoc-glass-bg)`
- Hardcoded backdrop-filter → `var(--autodoc-glass-blur)`

### `web/src/components/layout/ContextSearch.css`

- `rgba(255, 255, 255, 0.8)` → glass tokens
- Hardcoded box-shadow → `var(--autodoc-shadow-ambient)`

### `web/src/components/layout/Sidebar.tsx`

Replace Salt DS icons with Material Symbols for navigation:
- `HomeIcon` → `home`
- `DashboardIcon` → `work_history`
- `RunReportIcon` → `monitoring`
- `BarChartIcon` → `bar_chart`
- `StorageIcon` → `storage`
- Brand icon SVG → `auto_awesome`

## Section 4: Input/Form Refactor

### `web/src/theme/autodoc-theme.css`

Override Salt DS input tokens:
- `--salt-input-background`: `var(--autodoc-surface-container-high)` (tonal bg, not white)
- `--salt-input-borderColor`: `transparent` (no border — "no-line" rule)
- `--salt-input-borderColor-active`: `var(--autodoc-primary)` (2px primary bottom-bar on focus)

### `web/src/pages/RepoListPage.tsx`

- Replace raw `<input>` in "Add Repository" dialog with Salt DS `Input`
- Replace raw `<textarea>` with Salt DS `Input` multiline
- Wrap fields in `FormField` + `FormFieldLabel`
- Remove inline `style={}` for input styling

### `web/src/pages/tabs/SettingsTab.tsx`

- Same pattern: raw form elements → Salt DS `Input` + `FormField`
- Remove inline border/background styles

## Section 5: Metric Cards, CTA Buttons & Status Badges

### `web/src/components/shared/MetricCard.tsx`

- Add optional `icon` prop (Material Symbol name string)
- Render icon in tinted container: `--autodoc-primary-fixed` bg, `--autodoc-primary` color
- Remove any `1px border` styling
- Use `--autodoc-surface-container-low` bg + `--autodoc-shadow-ambient` shadow

### `web/src/theme/autodoc-theme.css` (CTA buttons)

- `--salt-actionable-cta-background`: `linear-gradient(135deg, var(--autodoc-primary), var(--autodoc-primary-container))`
- `--salt-actionable-cta-background-hover`: same gradient with 10% lightened stops (e.g., `#3a5ee0` → `#5678f5`)

### `web/src/components/shared/StatusBadge.tsx`

Update color mapping to Stitch functional tokens:
- Success: `--autodoc-secondary-fixed` bg / `--autodoc-on-secondary-fixed-variant` text
- Warning: `--autodoc-tertiary-fixed` bg / `--autodoc-on-tertiary-fixed-variant` text
- Error: `--autodoc-error-container` bg / `--autodoc-on-error-container` text

### MaterialIcon helper

Add a small helper component (in shared or utils):
```tsx
export const MaterialIcon = ({ name, size }: { name: string; size?: number }) => (
  <span className="material-symbols-outlined" style={size ? { fontSize: size } : undefined}>
    {name}
  </span>
);
```

### Pages using Material Symbols

- `OverviewTab.tsx` — metric card icons: `description`, `high_quality`, `layers`, `schedule`
- `SystemHealthPage.tsx` — infrastructure icons: `api`, `hub`, `database`, `engineering`

## Section 6: Storybook Theming

### New file: `web/.storybook/preview.ts`

- Import `@salt-ds/core/css/salt-core.css`
- Import `../src/theme/autodoc-theme.css`
- Import `../src/index.css`
- Decorator wrapping all stories in `<SaltProvider mode="light">`

### `web/.storybook/main.ts`

- Verify Vite config is picked up for path alias (`@/` → `src/`) resolution

## Files Changed Summary

| File | Change Type |
|------|-------------|
| `web/index.html` | Edit (add font links) |
| `web/src/theme/autodoc-theme.css` | Edit (tokens, typography, Salt overrides) |
| `web/src/components/layout/Sidebar.css` | Edit (tokenize colors) |
| `web/src/components/layout/Sidebar.tsx` | Edit (Material Symbols icons) |
| `web/src/components/layout/TopBar.css` | Edit (glass tokens) |
| `web/src/components/layout/ContextSearch.css` | Edit (glass tokens) |
| `web/src/components/shared/MetricCard.tsx` | Edit (icon prop, tonal styling) |
| `web/src/components/shared/StatusBadge.tsx` | Edit (Stitch functional token colors) |
| `web/src/pages/RepoListPage.tsx` | Edit (Salt DS Input/FormField) |
| `web/src/pages/tabs/SettingsTab.tsx` | Edit (Salt DS Input/FormField) |
| `web/src/pages/tabs/OverviewTab.tsx` | Edit (Material Symbol metric icons) |
| `web/src/pages/admin/SystemHealthPage.tsx` | Edit (Material Symbol infra icons) |
| `web/src/components/shared/MaterialIcon.tsx` | New (helper component) |
| `web/.storybook/preview.ts` | New (theme decorator) |

## Out of Scope

- Dark mode support (hardcoded light mode stays)
- Creating a shared FormInput wrapper component (Salt DS Input + theme handles it)
- Rewriting component HTML structure to match Stitch markup
- Adding new pages or features
