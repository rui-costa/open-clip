# Design System: Impeccable Brutalist

This document codifies the design language and implementation patterns for the studio interface. It is a living document intended to guide all future UI developments to maintain the defined bold, brutalist aesthetic.

## Philosophy: Utility-First Brutalism
The interface is a high-performance tool for content creators.
- **Bold Visual Hierarchy**: Use scale and high-contrast weight to establish priority.
- **Raw Utility**: No decorative fluff. Every element serves a functional purpose.
- **Intentional Brutalism**: Harsh lines (4px borders), high-contrast palettes, and raw geometric forms prioritize speed and clarity.

## Foundation

### Colors
Use OKLCH or standard hex variables. Maintain extreme high contrast.
- `--bg`: `#FFFFFF` / `#000000`
- `--text`: `#000000` / `#FFFFFF`
- `--accent`: `#FF3E00` (Used for primary actions and status alerts)
- `--error`: `#FF0000`

### Typography
- **Primary Font**: Helvetica Neue / Arial (System sans-serif)
- **Scales**:
  - H1: 8rem, 900 weight, -0.08em tracking (Title/Header)
  - H2: 3rem, 900 weight, Uppercase (Section headings)
  - Body: 1rem (Standard)
  - Labels: 0.75rem - 0.9rem, 900 weight, Uppercase

### Spacing
Uses a consistent rhythm derived from `--space-` variables:
- `--space-sm`: 0.5rem
- `--space-md`: 1rem
- `--space-lg`: 2rem
- `--space-xl`: 4rem

## Patterns

### Containers & Borders
- **Borders**: All primary UI borders must use `4px solid var(--text)`.
- **Containers**: Flat, edge-to-edge layouts are preferred over nested cards.
- **Shadows**: NO drop shadows or soft shadows are permitted in any component by default. Hard shadows (neo-brutalist) are only permitted as hover state indicators to convey interactivity.

### Buttons & Interactivity
- **Button style**: `background: transparent; border: var(--border); color: var(--text); padding: var(--space-sm) var(--space-md); text-transform: uppercase;`.
- **Hover**: Invert colors (`background: var(--text); color: var(--bg);`).
- **Interaction**: No soft transitions. Use abrupt changes to convey raw, machine-like speed.

### Status Indicators
- Use a `.status-badge` class for state communication.
- Accent color (`--accent`) for active execution states (transcribing/uploading).
