# Brand spec — IsyShell console (reference: isy.one)

Extracted from `https://isy.one/assets/css/style.css` (412 KB) by frequency-counting real hex values.
Not guessed from memory.

## Source signal (top brand hex by frequency)

| Hex        | Count | Role on isy.one                         |
|------------|-------|-----------------------------------------|
| `#fcb400`  | 136   | **Signature gold accent** (CTAs, marks) |
| `#0e113a`  | 81    | Deep indigo-navy surface                |
| `#010128`  | 64    | Deepest navy (hero backgrounds)         |
| `#0c3a30`  | 38    | Forest-green secondary brand surface    |
| `#101c86`  | 6     | Royal blue (logo / homepage headline)   |
| `#ff9c00`  | 17    | Warm orange (gold variant)              |

Display typeface on isy.one: **Inter Tight** (`font-family:"Inter Tight",sans-serif` x7).
This is why the console uses Inter Tight as the display face even though the seed default is a
serif — a faithful reference-match honours the brand's real type, and the active brand wins over the
skill default.

## Tokens bound to the console `:root`

```css
--navy-900: #010128;   /* deepest */
--navy-700: #0e113a;   /* sidebar / dark chrome */
--royal:    #101c86;   /* brand royal */
--forest:   #0c3a30;   /* secondary brand surface */
--gold:     #fcb400;   /* the single accent */

--bg:       #f6f5f1;   /* warm off-white workspace canvas */
--surface:  #ffffff;
--border:   #e7e6e0;
--text:     #15161c;
--muted:    #6a6c76;

--green:#1f9d57; --amber:#e8920c; --red:#dc2626;   /* fleet status */

--font-display: "Inter Tight", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
--font-body:    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif;
--font-mono:    ui-monospace, "SF Mono", Menlo, monospace;
```

## Layout posture observed

- Dark navy chrome against a light/white content field — high contrast, premium.
- Gold used surgically: accents, active states, one decisive CTA — never as a wash.
- Generous whitespace, hairline borders, restrained radii.
- Reconciles with the house palette (Azul Petróleo `#0E2035` ≈ navy; Off-White `#F7F3F0` ≈ canvas).

## How it maps to the IsyShell admin console

- **Navy left rail** (`--navy-700`) — brand mark + primary navigation, gold active indicator.
- **Warm off-white workspace** — fleet cards, catalog tables, audit log.
- **Gold accent budget per screen:** brand dot + active nav + one primary CTA. Status colors
  (green/amber/red) are functional, not brand accent.
- **Inter Tight** for headings/numerals, system sans for body, mono for tokens / IDs / durations.
