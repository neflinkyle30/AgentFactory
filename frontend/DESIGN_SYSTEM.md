# Agent Factory — Design System (Blueprint Industrial)

Blueprint Industrial design system for the Agent Factory OSS dashboard.
Inspired by technical documentation, engineering schematics, and blueprints.
Hallmark-compliant: refuses to look AI-generated.

---

## Core Philosophy

> "If you were documenting a spacecraft, what would the manual look like?"

Blueprint Industrial treats the UI as **technical documentation**. Every screen is a
schematic. Every component is a labeled specification. The aesthetic is precise,
monospace, grid-anchored, and intentionally cold — like an engineer's notebook.

---

## Anti-Patterns Enforced

Hallmark's five AI tells, solved the Blueprint way.

### AP-01: The Purple-Gradient Hero
**Our fix**: Single cyan accent (#4A9FD8). Blueprint grid background (#F0F4F8).
No gradients anywhere. Flat, technical color fields.

### AP-02: Inter as Display
**Our fix**: **IBM Plex Mono** exclusively — display, body, labels, data, code.
One font family, four weights. Zero serif, zero sans-serif. The monospace
constraint IS the personality.

### AP-03: Centered Everything
**Our fix**: Left-biased layout anchored to a 240px sidebar. Grid lines every
40px create implicit alignment. Asymmetric by default.

### AP-04: The Icon-Tile Feature Card
**Our fix**: No cards with icons. Data is presented as rows in a specification
table. Status is indicated by monospace symbols (● ✓ ✗ ◌). Information density
over decoration.

### AP-05: The AI Nav
**Our fix**: 240px sidebar with uppercase monospace labels, cyan left-border
indicator on active item. The sidebar reads as a document index, not a marketing
nav.

---

## Typography

### Font
| Role | Font | Weights |
|------|------|---------|
| **Everything** | IBM Plex Mono | 400 (regular), 500 (medium), 600 (semibold), 700 (bold) |

No second font. The constraint is the identity.

### Type Scale
| Token | Size | Usage |
|-------|------|-------|
| `text-xs` | 11px / 0.6875rem | Annotations, FIG labels, edge marks |
| `text-sm` | 12px / 0.75rem | Table content, form input text, button labels |
| `text-base` | 13px / 0.8125rem | Body, nav items |
| `text-lg` | 14px / 0.875rem | Emphasized body |
| `text-xl` | 16px / 1rem | Section headings |
| `text-2xl` | 18px / 1.125rem | Card titles |
| `text-3xl` | 24px / 1.5rem | Page subtitles |
| `text-4xl` | 28px / 1.75rem | Page titles |

### Letter Spacing
| Token | Value | Usage |
|-------|-------|-------|
| `tracking-mono-label` | 0.075em | Form labels, column headers |
| `tracking-mono-wide` | 0.125em | Navigation items, button text, uppercase labels |

---

## Color Palette

### Primary
| Token | Hex | Usage |
|-------|-----|-------|
| `--color-primary` | `#1A1A1A` | Primary text, primary buttons |
| `--color-primary-hover` | `#333333` | Button hover state |

### Accent
| Token | Hex | Usage |
|-------|-----|-------|
| `--color-cyan-accent` | `#4A9FD8` | Links, active states, edge marks, focus rings |
| `--color-cyan-accent-hover` | `#3A8BC2` | Hover state |

### Status
| Token | Hex | Meaning |
|-------|-----|---------|
| `--color-success` | `#22A65E` | Completed, passed |
| `--color-danger` | `#B91C1C` | Failed, rejected |
| `--color-warning` | `#D4A017` | Bounced, warning |
| `--color-info` | `#4A9FD8` | Active, in progress |

### Blueprint Surfaces
| Token | Hex | Usage |
|-------|-----|-------|
| `--blueprint-bg` | `#F0F4F8` | Page background |
| `--blueprint-grid` | `#D4E0EC` | Grid lines (0.5px) |
| `--blueprint-grid-strong` | `#C8D6E5` | Major grid lines (1px) |
| `--bg-elevated` | `#FFFFFF` | Cards, table rows, panels |
| `--bg-sidebar` | `#E8EEF4` | Sidebar background |
| `--bg-code` | `#0F172A` | Code/output panels |

### Text
| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#1A1A1A` | Body text, headings |
| `--text-secondary` | `#666666` | Secondary text, metadata |
| `--text-tertiary` | `#999999` | Placeholders, disabled, FIG annotations |
| `--text-inverse` | `#FFFFFF` | Text on dark/black backgrounds |

---

## Spacing

×4 scale. All spacing must be a multiple of 4px.

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Tight gaps |
| `space-2` | 8px | Inline gaps |
| `space-3` | 12px | Form gaps |
| `space-4` | 16px | Standard padding |
| `space-6` | 24px | Section gaps |
| `space-8` | 32px | Page padding |
| `space-12` | 48px | Large sections |
| `space-16` | 64px | Hero spacing |

---

## Layout

### Grid System
Blueprint pages use a **40px grid** as visual texture, not strict layout
constraint. Grid lines are rendered at 0.5px opacity on the page background.
Major lines at 120px intervals are 1px.

### Sidebar
- Width: 240px (CSS: `var(--sidebar-width)`)
- Background: `var(--bg-sidebar)` (#E8EEF4)
- Content area fills remaining width
- Border-right: 1px `var(--blueprint-grid)` separating from content

### Content Area
- Max width: 1200px
- Padding: 32px horizontal

---

## Border Radius

**All border radius: 0px.** No exceptions. Sharp corners throughout — cards,
buttons, inputs, badges, panels. The sharp-corner constraint reinforces the
technical/utilitarian aesthetic.

---

## Shadows

**No shadows.** Flat design. Depth is communicated through borders, grid lines,
and color contrast — never elevation.

---

## Motion

- `ease-out-expo`: `cubic-bezier(0.16, 1, 0.3, 1)`
- `duration-fast`: 100ms (hover, focus)
- `duration-normal`: 150ms (transitions)
- `duration-slow`: 300ms (page transitions)
- Always respect `prefers-reduced-motion: reduce`

---

## Component Guidelines

### Status Indicators
Use monospace symbols + color, never icon+text badges:
- `● ACTIVE` — cyan (#4A9FD8)
- `✓ DONE` — green (#22A65E)
- `✗ FAILED` — red (#B91C1C)
- `◌ QUEUED` — gray (#999999)

### Buttons
- **Primary**: Black background (#1A1A1A), white text, uppercase, 0px radius
- **Secondary**: Transparent, black border, black text
- **Ghost**: No border, secondary text, darkens on hover
- All buttons use IBM Plex Mono, letter-spacing 0.125em

### Form Inputs
- White background, 1px `var(--border-default)` border
- IBM Plex Mono, 12px
- Placeholder: `var(--text-tertiary)`
- Focus: border turns cyan (#4A9FD8)
- No border radius

### Cards / Panels
- White background, 1px border, no radius
- Padding: 24px
- No shadows

### Tables
- Alternating white / transparent row backgrounds
- Row separators: 0.5px `var(--border-subtle)` lines
- Column headers: uppercase, 9px, letter-spacing 0.125em, `var(--text-tertiary)`
- Content: IBM Plex Mono, 12px, `var(--text-primary)`

### Pipeline Stepper
- Horizontal line with circles at each phase
- Completed: green fill, checkmark
- Active: cyan fill, phase letter
- Pending: light fill, gray border, gray letter
- Labels below each circle: uppercase monospace

### Edge Marks & Annotations
- Cyan vertical line on content edge as measurement mark
- Small tick marks at row boundaries
- Corner marks (cyan L-shapes) at section boundaries
- FIG annotations: small gray monospace text referencing screen/section numbers

---

## Voice & Copy

- **Tool-centric, not marketing**. This is documentation, not a sales page.
- **Precise**. Use exact numbers and technical terms.
- **No emoji**. No exclamation marks in UI copy.
- **UPPERCASE for labels**. Sentence case for descriptions.
- **No superlatives**. "Pipeline Run Schedule", not "Amazing Pipeline Dashboard".
