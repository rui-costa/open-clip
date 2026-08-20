# Design System: Impeccable Brutalist

This document codifies the design language and implementation patterns for the studio interface. It is a living document intended to guide all future UI developments to maintain the defined bold, brutalist aesthetic.

**Source of truth**: `frontend/src/index.css`. The values below mirror what ships. When the two disagree, the stylesheet wins and this document is the thing that needs fixing.

## Philosophy: Utility-First Brutalism

The interface is a high-performance tool for content creators.

- **Bold Visual Hierarchy**: Use scale and high-contrast weight to establish priority.
- **Raw Utility**: No decorative fluff. Every element serves a functional purpose.
- **Intentional Brutalism**: Harsh lines (4px borders), high-contrast palettes, and raw geometric forms prioritize speed and clarity.

Brutalism here is a visual stance, not an excuse for an inaccessible interface. Where the two appear to conflict, contrast wins — see [Accessibility Floor](#accessibility-floor).

## Foundation

### Colors

Neutrals are tinted rather than pure. `#000000` and `#FFFFFF` are deliberately not used as page background or body text; they read as harsher than the brutalist forms need and cause halation against 4px borders.

Every colour that carries text is chosen to clear 4.5:1 against the surface it sits on, in **both** themes. Three tokens fork per theme because a single value cannot do that.

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--bg` | `#F9F9F9` | `#121212` | Page surface |
| `--bg-secondary` | `#EDEDED` | `#1E1E1E` | Recessed panels |
| `--text` | `#121212` | `#F9F9F9` | Body |
| `--text-muted` | `#6B6B6B` | `#A0A0A0` | 5.06:1 / 7.16:1 on `--bg` |
| `--accent` | `#C42F00` | `#FF7A52` | 5.31:1 / 7.28:1. Active execution states |
| `--success` | `#00FF41` | `#00CC33` | Fill only — pair with `--on-success` |
| `--on-success` | `#121212` | `#121212` | Does not track `--bg`; green needs dark text in both themes |
| `--error` | `#D40000` | `#FF4D4D` | 5.25:1 / 5.73:1 |
| `--border-color` | `var(--text)` | `#FFFFFF` | |

**On the accent.** The brand orange is `#C42F00`, darkened from the `#FF3E00` this document specified for years. `#FF3E00` is 3.36:1 on `--bg` and was never usable for text or as a fill behind `--bg` text — it failed WCAG AA everywhere it was applied. The dark-theme value lifts to `#FF7A52` for the same reason in reverse.

**Foreground pairing.** `--accent` and `--error` are both used as fills behind `var(--bg)` text; that pairing is contrast-checked and correct. `--success` is the exception — it takes `--on-success`, because a dark foreground is required on green in both themes. Do not use `var(--bg)` on a success fill.

**Accent and error are adjacent hues.** Orange-red `#C42F00` and red `#D40000` sit next to each other in the pipeline step row (running vs. failed). Because of that, **status must never be conveyed by fill colour alone** — every status surface also carries a text label. See `statusLabel()` in `PipelineController.tsx`.

### Typography

- **Primary Font**: Helvetica Neue / Arial (system sans-serif)
- **Scales** (as implemented, fluid via `clamp()`):
  - `h1`: `clamp(3rem, 10vw, 6rem)`, 900 weight, `-0.04em` tracking, uppercase
  - `h2`: `clamp(2rem, 5vw, 3rem)`, 900 weight, `-0.02em` tracking, uppercase
  - `.wordmark`: `clamp(2rem, 5vw, 4rem)` — looks like a title but is not one; it repeats on every route and must not compete with the page `h1`
  - Body: `1rem`
  - Labels: `0.65rem`–`0.9rem`, 900 weight, uppercase, `0.05em` tracking

Pages may set a smaller `h1` inline where the page heading shares a row with controls.

### Spacing

A compact rhythm. These are the shipped values:

- `--space-xs`: `0.125rem`
- `--space-sm`: `0.25rem`
- `--space-md`: `0.75rem`
- `--space-lg`: `1rem`
- `--space-xl`: `2rem`

Do not hard-code `1rem` / `0.5rem` / `4px` in component styles. Every literal spacing value in a component is a token that failed to get used.

## Patterns

### Containers & Borders

- **Borders**: use the `--border` token (`var(--border-width) solid var(--border-color)`), not a literal `4px solid var(--text)`. The literal diverges in dark theme, where `--border-color` is `#FFFFFF` but `--text` is `#F9F9F9`.
- **Radius**: zero, everywhere. No `border-radius` on any control, including native `<select>`.
- **Containers**: flat, edge-to-edge layouts. **No nested cards** — a bordered block inside a bordered block is the one composition this system rules out. Separate flat regions with a single rule (`borderTop: var(--border)`) instead.
- **Shadows**: no soft or drop shadows, ever. Hard offset shadows (`4px 4px 0px var(--border-color)`) are permitted in two places only: hover states conveying interactivity, and modal elevation above a scrim. No blur, no `backdrop-filter`.

### Layout

Reflowing layouts live in `index.css`, because inline styles cannot express media or container queries. Use the existing classes rather than re-typing them inline:

- `.card-grid` — `auto-fill`, 300px track minimum
- `.split-grid` — `auto-fit`, 320px track minimum
- `.social-grid` — `auto-fit`, 180px track minimum
- `.project-layout` / `__main` / `__aside` — the project page's two-column split, sticky aside above 900px

Every grid track minimum is wrapped in `min(Npx, 100%)`. This is what stops a fixed minimum from overflowing a viewport narrower than the minimum, and it is the reason to use the class instead of an inline `minmax(300px, 1fr)`.

### Buttons & Interactivity

Use the `Button` component (`components/Button.tsx`). Variants: `primary`, `ghost`, `danger`. Sizes: `sm`, `md`, `lg`.

- **Base**: transparent background, `var(--border)`, `var(--text)`, uppercase, 900 weight.
- **Hover**: invert to `--btn-hover-bg` / `--btn-hover-text`, plus `translate(2px, 2px)`.
- **Active**: `translate(4px, 4px)`.
- **Disabled**: `opacity: 0.55` and `not-allowed`, from the base `button:disabled` rule. Do not write it inline — components that did drifted to their own values, and the same `0.5` reads differently on a filled button than on a ghost one. Hover and active are suppressed for disabled buttons, so a dead control never promises a press it will not accept.
- **Hierarchy matters.** Not every button is `primary`. Secondary and tertiary actions take `ghost`; destructive actions take `danger`.
- **Say why it is disabled.** A disabled button's label — or its tooltip, where the control is an icon — is where the reason lives: "This clip is being uploaded, which re-cuts it", not a bare greyed-out re-render arrow.

### Status Indicators

Use the `.status-badge` class. It fixes the geometry (2px border, `0.65rem`, 900 weight, uppercase, `0.05em` tracking) so every state pill in the app reads as the same object. Colour is passed in by the caller, since what a state *means* is the caller's business:

```jsx
<span className="status-badge" style={{ background: 'var(--success)', color: 'var(--on-success)' }}>
  Rendered
</span>
```

Accent for active execution states (transcribing, rendering, uploading). Always pair the colour with a text label.

### Motion

- **Easing**: `--ease-out-quart` (`cubic-bezier(0.25, 1, 0.5, 1)`). Real objects decelerate; nothing overshoots.
- **Duration**: 200ms for state transitions, 300–400ms for entrances.
- **No bounce or elastic easing.** It reads as dated. `nudge` replaced an earlier three-stage `bounce` for exactly this reason.
- **Animate `transform` and `opacity` only.** Never `width`, `height`, `top`, or `left`.
- **`prefers-reduced-motion: reduce` is honoured globally** in `index.css`. Indefinite animations (`sheen` during a pipeline step, `pulse` during generation) are the ones that matter most to suppress.

### Accessibility Floor

Non-negotiable, and checked at review:

- **Contrast**: 4.5:1 for text, 3:1 for non-text and focus indicators, in both themes.
- **Touch targets**: 44×44px minimum for anything interactive.
- **Focus**: `:focus-visible` is a 4px `--accent` outline at 3px offset, defined globally. Do not remove it or override it per-component.
- **Status is never colour-only**: pair every colour-coded state with text.
- **Opacity is not a styling tool on text.** Fading a label over a coloured fill is how a contrast-checked colour silently stops passing.

## Enforcement

See `frontend/src/INTERACTION_GUIDELINES.md` for the interaction rules that gate code review (no `window.alert` / `confirm` / `prompt`; all confirmations are in-UI, keyboard accessible, ARIA-labelled).
