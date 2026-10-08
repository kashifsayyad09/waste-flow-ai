# Design System Inspired by AWS Student Community Day Hyderabad

> Auto-extracted from `https://awsscdhyd.in/` on 2026-10-05

## 1. Visual Theme & Atmosphere

Refined dark mode with muted tones — cinematic and premium.

The hero section leads with "AWS STUDENTCOMMUNITY DAY AWS STUDENTCOMMUNITY DAY" followed by ">for the ones who build".

**Key Characteristics:**
- Jersey 10 as the heading font (custom web font loaded via @font-face)
- Roboto as the body font for all running text
- Heading weight 400, letter-spacing 1.1px
- Dark background (#0b0d12) as the primary canvas
- Primary accent `#ff9900` used for CTAs and brand highlights
- 8 shadow level(s) detected — tinted shadows
- Sharp corners (0-2px) for a precise, technical aesthetic
- Tags: dark, sharp, accented, bold-typography, monospace, sans-serif

## 2. Color Palette & Roles

### Primary
- **Primary Accent** (`#ff9900`) · `--color-primary`: Brand color, CTA backgrounds, link text, interactive highlights.
- **Secondary Accent** (`#f6c899`) · `--color-secondary`: Secondary brand, hover states, complementary highlights.
- **Background** (`#0b0d12`) · `--color-bg`: Page background, primary canvas.
- **Background Secondary** (`#0e131c`) · `--color-bg-secondary`: Cards, surfaces, alternating sections.

### Text
- **Text Primary** (`#f4f7fb`) · `--color-text`: Headings and body text.
- **Text Secondary** (`#999999`) · `--color-text-secondary`: Muted text, captions, placeholders.

### Borders & Surfaces
- **Border** (`#121926`) · `--color-border`: Dividers, outlines, input borders.

### Full Extracted Palette

| # | Hex | CSS Variable | Role | Area | Contrast |
|---|---|---|---|---|---|
| 1 | `#121926` | `--palette-1` | block | large | text-light |
| 2 | `#0e131c` | `--palette-2` | section | large | text-light |
| 3 | `#ff9900` | `--palette-3` | badge | large | text-dark |
| 4 | `#9fe3b6` | `--palette-4` | badge | large | text-dark |
| 5 | `#f2a7c3` | `--palette-5` | text-accent | large | text-dark |
| 6 | `#c4aef2` | `--palette-6` | badge | large | text-dark |
| 7 | `#f6c899` | `--palette-7` | badge | large | text-dark |
| 8 | `#ffffff` | `--palette-8` | button | large | text-dark |
| 9 | `#0b0d12` | `--palette-9` | button | medium | text-light |
| 10 | `#232c40` | `--palette-10` | button | medium | text-light |
| 11 | `#2b3a61` | `--palette-11` | button | medium | text-light |

## 3. Typography Rules

- **Heading Font:** `Jersey 10` (web font)
- **Body Font:** `Roboto` (web font)

### Type Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| H1 | Jersey 10 | 110px | 400 | 101.2px | 1.1px |
| H2 | Jersey 10 | 77.5px | 400 | 72.85px | normal |
| H3 | Jersey 10 | 66px | 400 | 60.72px | normal |
| Body | Roboto | 18.5px | 400 | 29.6px | normal |
| Code | -apple-system | 16px | 400 | 24px | normal |

### Type Scale

| Token | Size | Suggested Usage |
|---|---|---|
| Display | `225px` | headings |
| H1 | `110px` | headings |
| H2 | `100px` | headings |
| H3 | `97.5px` | headings |
| H4 | `96px` | headings |
| Body L | `77.5px` | body / supporting text |
| Body | `70px` | body / supporting text |
| Small | `66px` | body / supporting text |
| XS | `64px` | body / supporting text |
| Caption | `50px` | body / supporting text |

## 4. Component Stylings

### Primary Button

```css
.btn-primary {
  background: #0b0d12;
  color: #f4f7fb;
  border-radius: 0px;
  padding: 12px 20px;
  font-size: 16px;
  font-weight: 400;
  border: 0.724528px solid rgb(244, 247, 251);
  cursor: pointer;
}
```

### Outline Button

```css
.btn-outline {
  background: transparent;
  color: #f4f7fb;
  border-radius: 0px;
  padding: 0px 12px;
  font-size: 17.5px;
  font-weight: 400;
  border: 2.89811px solid rgb(42, 53, 80);
  cursor: pointer;
}
```

### Filled Button

```css
.btn-filled {
  background: #161d2b;
  color: #f4f7fb;
  border-radius: 0px;
  padding: 0px 0px;
  font-size: 16px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Card

```css
.card {
  background: #121926;
  border-radius: 0px;
  padding: 0px;
  box-shadow: rgba(0, 0, 0, 0.5) 8px 8px 0px 0px;
}
```

## 5. Layout Principles

- **Base spacing unit:** `4px` — use multiples (8px, 12px, 16px, etc.)

### Spacing Scale (extracted from real elements)

| Token | Value | Role |
|---|---|---|
| spacing-1 | `4px` | element |
| spacing-2 | `20px` | element |
| spacing-3 | `7px` | element |
| spacing-4 | `6px` | element |
| spacing-5 | `26px` | card |
| spacing-6 | `14px` | element |
| spacing-7 | `18px` | element |
| spacing-8 | `65.2076px` | section |

### Border Radius Scale

| Token | Value | Element |
|---|---|---|

## 6. Depth & Elevation

| Level | Shadow | Usage |
|---|---|---|
| Low | `rgba(0, 0, 0, 0.5) 6px 6px 0px 0px` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0.5) 8px 8px 0px 0px` | Cards, subtle elevation |
| Low | `rgba(255, 255, 255, 0.7) 4px 4px 0px 0px` | Cards, subtle elevation |
| Mid | `rgb(255, 255, 255) 0px 0px 12px 4px` | Dropdowns, popovers |
| Low | `rgb(20, 22, 28) 4px 4px 0px 0px` | Cards, subtle elevation |


## 7. Do's and Don'ts

### Do
- Use `#0b0d12` as the primary background color
- Use `Jersey 10` for all headings and `Roboto` for body text
- Use `#ff9900` as the single dominant accent/CTA color
- Maintain `4px` as the base spacing unit — all gaps should be multiples
- Keep the overall feel dark — use dark surfaces throughout
- Keep corners sharp (0-2px radius) for a precise, technical feel
- Make headlines large and bold — typography is the hero element
- Apply the shadow system for elevation — use the extracted shadow values
- Use weight 400 for headings to match the brand's typographic voice

### Don't
- Don't use colors outside the extracted palette without justification
- Don't substitute Jersey 10/Roboto with generic alternatives
- Don't use irregular spacing — stick to 4px grid
- Don't introduce bright white surfaces — they break the dark palette
- Don't use large border-radius — keep everything crisp and geometric
- Don't use pure black (#000000) for text — use `#f4f7fb` instead
- Don't add decorative elements not present in the original design — no badges, ribbons, banners, or ornaments unless the source site uses them
- Don't invent UI patterns the source site doesn't have — if the original has no NEW badge, don't add one just because a red is in the palette

## 8. Responsive Behavior

| Breakpoint | Width | Notes |
|---|---|---|
| Mobile | < 640px | Single column, stack sections, reduce font sizes ~80% |
| Tablet | 640–1024px | 2-column where appropriate, maintain spacing ratios |
| Desktop | 1024–1440px | Full layout as designed |
| Wide | > 1440px | Max-width container, center content |

- Touch targets: minimum 44×44px on mobile
- Maintain 4px base unit across breakpoints — only scale multipliers

## 9. Agent Prompt Guide

### Quick Color Reference

```
Background:  #0b0d12
Text:        #f4f7fb
Accent:      #ff9900
Secondary:   #f6c899
Border:      #121926
```

### Example Prompts

1. "Build a hero section with a `#0b0d12` background, `Jersey 10` heading in `#f4f7fb`, and a `#ff9900` CTA button with 0px radius."
2. "Create a pricing card using background `#0e131c`, border `#121926`, `Roboto` for text, and 12px padding."
3. "Design a navigation bar — `#0b0d12` background, `#f4f7fb` links, `#ff9900` for active state."
4. "Build a feature grid with 3 columns, 12px gap, each card using the card component style."
5. "Create a footer with `#0e131c` background, `#f4f7fb` text, and 8px padding."

### Iteration Guide

1. Start with layout structure (sections, grid, spacing)
2. Apply colors from the palette — background first, then text, then accents
3. Set typography — font families, sizes from the type scale, weights
4. Add components — buttons, cards, inputs using the specs above
5. Apply border-radius consistently across all elements
6. Add shadows for depth — use the extracted shadow values, not defaults
7. Check responsive behavior — test mobile and tablet layouts
8. Final pass — verify all colors match, spacing is consistent, fonts are correct

## 10. CSS Custom Properties

> 90 custom properties extracted from `:root` / `html` stylesheets.

### Color Variables

| Variable | Value |
|---|---|
| `--bg` | `#f5f2ee` |
| `--bg2` | `#f8f4ef` |
| `--bg3` | `#efe8e0` |
| `--surface` | `#fff` |
| `--panel` | `#f0eafb` |
| `--panel-mint` | `#e6f5eb` |
| `--panel-gold` | `#fdf4e3` |
| `--slot` | `#f1eee9` |
| `--slot2` | `#d7d1c8` |
| `--bar` | `#e3ddd4` |
| `--ink` | `#14161c` |
| `--ink-fill` | `#14161c` |
| `--on-fill` | `#14161c` |
| `--body` | `#33384a` |
| `--muted` | `#464c5c` |
| `--body-gold` | `#2e2a20` |
| `--line` | `#14161c` |
| `--line-soft` | `#14161c2e` |
| `--line-dash` | `#14161c59` |
| `--mint-ink` | `#1f6540` |
| `--violet-ink` | `#55359f` |
| `--pink-ink` | `#962854` |
| `--amber-ink` | `#8f5200` |
| `--gold` | `#a8711a` |
| `--gold2` | `#7f5407` |
| `--gold3` | `#8e5f0c` |
| `--gold4` | `#6e4a05` |
| `--cloud-a` | `#d9cef5` |
| `--cloud-b` | `#e4dbfa` |
| `--cloud-c` | `#ddd3f7` |
| ... | *(36 more)* |

### Spacing Variables

| Variable | Value |
|---|---|
| `--page-max` | `640px` |
| `--radius` | `0` |
| `--hairline` | `1px` |

### Typography Variables

| Variable | Value |
|---|---|
| `--text` | `var(--ink)` |
| `--font-display` | `var(--font-display-face), monospace` |
| `--font-body` | `var(--font-body-face), system-ui, sans-serif` |
| `--font-mono` | `var(--font-mono-face), monospace` |

### Other Variables

| Variable | Value |
|---|---|
| `--lightningcss-light` | `initial` |
| `--h-sh` | `var(--h-sh1)` |
| `--border` | `var(--line)` |
| `--accent-ink` | `var(--on-fill)` |
| `--fmt-keynote` | `var(--mint-fill)` |
| `--fmt-technical` | `var(--orange)` |
| `--fmt-workshop` | `var(--violet-fill)` |
| `--fmt-panel` | `var(--pink-fill)` |
| `--fmt-qa` | `var(--peach)` |
| `--tier-basic` | `var(--mint-fill)` |
| `--tier-premium` | `var(--orange)` |
| `--tier-ultra` | `var(--pink-fill)` |
| `--tier-vip` | `var(--gold-fill)` |
| `--track-ai` | `var(--mint-fill)` |
| `--track-cloud` | `var(--orange)` |
| ... | *(2 more)* |
