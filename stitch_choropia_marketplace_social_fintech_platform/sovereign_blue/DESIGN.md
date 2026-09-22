---
name: Sovereign Blue
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#44474c'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#75777d'
  outline-variant: '#c5c6cd'
  surface-tint: '#525f75'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#0e1c2f'
  on-primary-container: '#77849c'
  inverse-primary: '#bac7e1'
  secondary: '#426086'
  on-secondary: '#ffffff'
  secondary-container: '#b3d1fd'
  on-secondary-container: '#3b5a7f'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#00174b'
  on-tertiary-container: '#497cff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3fe'
  primary-fixed-dim: '#bac7e1'
  on-primary-fixed: '#0e1c2f'
  on-primary-fixed-variant: '#3a475c'
  secondary-fixed: '#d3e4ff'
  secondary-fixed-dim: '#aac9f4'
  on-secondary-fixed: '#001c38'
  on-secondary-fixed-variant: '#29486d'
  tertiary-fixed: '#dbe1ff'
  tertiary-fixed-dim: '#b4c5ff'
  on-tertiary-fixed: '#00174b'
  on-tertiary-fixed-variant: '#003ea8'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  mono-financial:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-xxs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  space-3xl: 4rem
  gutter-mobile: 1rem
  gutter-desktop: 1.5rem
  margin-mobile: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
---

## Brand & Style

This design system targets institutional-grade confidence paired with modern social commerce fluidity. It serves discerning buyers, verified merchants, and financial operators who require absolute clarity, rigorous security, and dignified elegance. The emotional baseline is quiet authority, architectural precision, and transparency—evoking the permanence of classic banking combined with the responsiveness of modern digital exchanges.

The design movement is **Corporate / Modern** distilled to an uncompromising, minimalist standard:
- **Zero Toy Aesthetics:** Absence of playful micro-illustrations, bouncy transitions, or candy-like accents.
- **Architectural Structure:** Grid discipline, hairline boundaries, and precise alignment establish credibility before a single interaction takes place.
- **Dignified Micro-interactions:** Transitions are brief (120ms–180ms), crisp, and linear or ease-out, avoiding exaggerated spring dynamics.

## Colors

The palette operates on strict chromatic restraint, prioritizing readability and institutional weight.

### Palette Architecture
- **Primary Navy (`#0B192C`):** Anchors primary calls-to-action, high-emphasis text, and authoritative navigation surfaces.
- **Secondary Navy (`#1E3E62`):** Handles interactive states, secondary containers, and focused table headers.
- **Subdued Accent (`#2563EB`):** A controlled cobalt reserved for active system states, links, and operational status indicators. Light tints (`#EFF6FF`) provide background fill for informational tags.
- **Neutrals & Canvases:**
  - Base Background: Pure White (`#FFFFFF`) and Pristine Off-White (`#F8FAFC`).
  - Layered Surface / Inset: Crisp Light Slate (`#F1F5F9`).
  - Structural Hairlines: Subtle Slate (`#E2E8F0`).
  - Body Text: Slate 700 (`#334155`).
  - Secondary Text & Metadata: Slate 500 (`#64748B`).

### Dark Mode & High-Contrast Rules
In inverted contexts or dark surfaces, the canvas shifts to Deep Slate Navy (`#0E1726`), structural borders move to `#1E293B`, and interactive blue elevates to `#60A5FA` to sustain WCAG AAA contrast ratios for financial text and critical figures.

## Typography

Typography relies entirely on **Inter** to ensure maximum utility across multi-currency displays, escrow states, and micro-copy. 

### Tabular Numbers & Financial Output
All monetary values, account balances, transaction ledgers, and order quantities must enforce tabular lining figures via OpenType features (`font-feature-settings: "tnum" 1, "cv05" 1`). This eliminates character wobble during real-time balance calculations and preserves strict column alignment in high-density data tables.

### Hierarchy & Letter Spacing
Negative tracking is deployed systematically on titles (`-0.025em` to `-0.01em`) to eliminate looseness in display text, while structural badges and sub-labels under 12px require positive letter-spacing (`0.04em`) with uppercase treatment for legibility at small scale.

## Layout & Spacing

The layout is built on a responsive 12-column grid system paired with an 8pt architectural rhythm (with a 4pt sub-grid for compact financial tables and input controls).

### Breakpoints & Geometry
- **Mobile (320px – 767px):** 4-column layout, 16px margins, 16px gutters. Transaction actions are anchored to persistent bottom control sheets.
- **Tablet (768px – 1023px):** 8-column layout, 32px margins, 20px gutters. Dual-pane view for social activity streams alongside checkout verification.
- **Desktop (1024px – 1440px+):** 12-column layout, max content boundary of 1280px, 48px margins, 24px gutters. Master-detail navigation stays docked for instant verification access.

### Density & Rhythms
Data density takes precedence over decorative negative space. Information-rich panels (escrow logs, counter-offers, dispute timelines) collapse vertical padding to `space-sm` (8px) or `space-md` (12px), retaining rigorous alignment along hairline grid separators.

## Elevation & Depth

This system avoids expressive blur elevations or diffused colored shadows. Visual planes are created through **crisp hairlines** combined with **subtle, cold ambient shadows**.

### Elevation Scale
1. **Base Floor (Level 0):** Flat background surfaces (`#FFFFFF` or `#F8FAFC`) with no shadow. Structural separation is maintained solely by a 1px border (`#E2E8F0`).
2. **Card & Panel (Level 1):** Floating standard items use an ultra-refined dual shadow:  
   `box-shadow: 0 1px 2px 0 rgba(11, 25, 44, 0.04), 0 1px 3px 0 rgba(11, 25, 44, 0.06);` enclosed by a 1px border (`#E2E8F0`).
3. **Dropdowns & Popovers (Level 2):** Context menus and selector panels use:  
   `box-shadow: 0 4px 6px -1px rgba(11, 25, 44, 0.06), 0 2px 4px -2px rgba(11, 25, 44, 0.04);` bordered by `#CBD5E1`.
4. **Modals & Escrow Overlays (Level 3):** Verification sheets and payment prompts take:  
   `box-shadow: 0 20px 25px -5px rgba(11, 25, 44, 0.10), 0 8px 10px -6px rgba(11, 25, 44, 0.04);` with a strict solid or frosted backdrop tint (`rgba(11, 25, 44, 0.40)` with `backdrop-filter: blur(4px)`).

## Shapes

The design system employs a **Soft (Level 1)** geometric standard. Rounding is measured and architectural to preserve serious structural integrity across tables, verification modules, and cards.

### Corner Radius Standards
- **Inputs, Buttons & Badges:** `rounded-md` (4px to 6px). Retains clean perimeter definition without harsh industrial sharp points or casual pill softness.
- **Cards, Panels & Containers:** `rounded-lg` (8px). Provides subtle boundary delineation without turning individual blocks into floating bubbles.
- **Large Modals & Drawers:** `rounded-xl` (12px maximum). Ensures large modal frames remain crisp and rooted.
- **Pill/Bubbly Styles Prohibited:** Pill radius (`rounded-full`) is restricted exclusively to user avatars and circular status indicator dots (e.g., green network heartbeat dots). Badges, buttons, and chips must remain structured rectangular elements with 4px–6px corner radii.

## Components

### Buttons
- **Primary:** Solid Deep Navy (`#0B192C`) fill, pure white text, 1px matching border. Hover moves to `#1E3E62`. Pressed state compresses scale to `0.99` with zero shadow.
- **Secondary:** White fill, 1px border (`#E2E8F0`), text color `#0B192C`. Hover initiates `#F8FAFC` background with border `#CBD5E1`.
- **Destructive/Action:** Crisp red-slate (`#991B1B`), flat container with high-contrast text for critical financial authorizations.
- **Metrics:** Heights are standardized at 36px (compact) and 44px (default) with horizontal padding of 14px and 18px.

### Inputs & Form Controls
- **Text Inputs:** Height 40px, 1px border (`#CBD5E1`), background `#FFFFFF`, text `#0B192C`. Focused state utilizes a hairline 1px ring in `#2563EB` with no heavy outer halos. 
- **Monetary Inputs:** Suffix currency codes (e.g., `USD`, `EUR`) locked into right-hand fixed containers with muted slate backgrounds (`#F1F5F9`). Numerical text must render in `mono-financial` tabular figures.

### Checkboxes & Radios
- Square with 3px border radius for checkboxes; circular for radios. Inactive border 1.5px (`#CBD5E1`), active fill `#0B192C` with white checkmark icon.

### Cards & Marketplace Tiles
- Minimal surface elevation with strict 1px boundary (`#E2E8F0`). Cards segment metadata (seller reputation, product lineage, transaction guarantee status) using hairline horizontal dividers (`border-t border-slate-100`).

### High-Trust Badges & Status Chips
- Non-pill, rectangular tags with subtle 4px corner radii and 1px border.
- **KYC Verified / Tier 1 Merchant:** Light steel-navy background (`#F1F5F9`), slate navy border (`#CBD5E1`), deep navy text (`#0B192C`), accompanied by an outlined 1.5px stroke shield-check icon.
- **Escrow / In-Transit:** Subdued amber-slate (`#FEF3C7` background, `#D97706` text, `#FDE68A` border).
- **Settled / Confirmed:** Muted emerald tint (`#ECFDF5` background, `#047857` text, `#A7F3D0` border).

### Iconography
- Outlined precision icons (Feather / Lucide style) maintaining a non-negotiable 1.5px to 2.0px stroke weight across all sizes (16px, 20px, 24px). Icons inherit the active text color and never feature multi-tone cartoon fills.