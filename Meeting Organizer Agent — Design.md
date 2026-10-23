# design.md — Meeting Organizer Agent

Visual and interface rules. Read with `rule.md` (anti-slop list) before building any screen.

**Fonts:** Libre Baskerville + Jost (Jost replaces Josefin Sans from `rule.md`; update that file to match). IBM Plex Mono for data.

---

## 1. Direction

**Quiet editorial, Swiss grid, serif voice.** A printed report that happens to be interactive. Large serif headlines, small uppercase Jost labels, hairline rules, numbered sections, one restrained accent.

### What is taken from each reference

| Reference | Borrow | Leave behind |
| --- | --- | --- |
| **Lovera** (agency) | Oversized wordmark with a small ™ mark; numbered sections (`01`, `0—1`); big stat figures with a tiny caption; numbered FAQ rows; process timeline with durations; the `⊹` glyph as a bullet and divider; generous whitespace | Marquees, testimonials, pricing cards, fake client logos |
| **Kero** (SaaS) | Clean section rhythm; component-driven layout; one clear message per block | Opinionated AI imagery, illustrations, gradient visuals |
| **Ramp** (Swiss) | Strict grid, flush-left text, bold type contrast, rules instead of boxes, confident empty space | Sales-page structure, course/subscription patterns |

Note: the references were read from their page text and structure, not their pixels. The palette and sizes below are our own, tuned to the references' mood.

### Principles

1. Type does the work. Layout is built from text, rules, and space.
2. One accent, used rarely (primary action, overdue, active).
3. Numbers and labels get character: big serif numerals, tiny uppercase captions.
4. Every screen reads like a document, not a widget board.
5. If an element can be a line instead of a box, make it a line.

---

## 2. Color

### Light (default)

| Token | Hex | Use |
| --- | --- | --- |
| `--paper` | `#F6F3EE` | Page background |
| `--surface` | `#FBFAF7` | Raised areas, inputs |
| `--ink` | `#161513` | Text, primary button |
| `--ink-soft` | `#5C5850` | Secondary text |
| `--ink-faint` | `#8F8A7F` | Placeholders, disabled |
| `--rule` | `#D9D4CA` | 1px lines |
| `--rule-strong` | `#161513` | Section top rules, table headers |
| `--accent` | `#8A2F1F` | Brick red |
| `--accent-wash` | `#F0E1DC` | Faint tint behind accent items |
| `--ok` | `#3F5B3A` | Approved, done |
| `--warn` | `#9A6B1C` | Pending |
| `--tint` | `#EFEBE4` | Row hover, selected |

### Dark

| Token | Hex |
| --- | --- |
| `--paper` | `#131210` |
| `--surface` | `#1A1917` |
| `--ink` | `#ECE7DD` |
| `--ink-soft` | `#A8A296` |
| `--rule` | `#2E2B27` |
| `--accent` | `#C4533F` |
| `--ok` | `#8DAA84` |
| `--warn` | `#D1A04E` |

### Rules

- Text on paper must pass WCAG AA (ink on paper is about 16:1; accent on paper about 7:1).
- Accent never fills large areas. Max one accent element per viewport section.
- No gradients, no transparency tricks, no colored shadows.
- Status is never color alone: always a text label.

---

## 3. Typography

| Role | Font | Weight | Notes |
| --- | --- | --- | --- |
| Display, headings | **Libre Baskerville** | 400, italic 400 | Tight tracking `-0.02em` at large sizes |
| Reading text (agenda, minutes, descriptions) | **Libre Baskerville** | 400 | 16px, line-height 1.7, max 68ch |
| Labels, nav, buttons, table headers, captions | **Jost** | 400, 500 | Uppercase, `letter-spacing: 0.12em`, 11–12px |
| UI body (form fields, small text) | **Jost** | 400 | 14–15px |
| Data, timestamps, IDs, traces | **IBM Plex Mono** | 400 | 13px, tabular numerals |

### Scale

| Token | Size / line | Use |
| --- | --- | --- |
| `display` | 72–96 / 0.95 | Login wordmark only |
| `h1` | 44 / 1.05 | Page title |
| `h2` | 30 / 1.15 | Section title |
| `h3` | 22 / 1.25 | Subsection |
| `lead` | 17 / 1.6 italic | Short intros under titles |
| `body` | 16 / 1.7 | Reading text |
| `ui` | 14 / 1.5 | Controls |
| `label` | 11 / 1.4, uppercase, `0.12em` | Captions, headers |
| `stat` | 64 / 1 Libre Baskerville | Big numbers |

### Rules

- Headlines in sentence case. Italic for one emphasized word at most.
- Uppercase only for Jost labels, never for serif headings.
- Numbers in tables: Plex Mono or Jost with `font-variant-numeric: tabular-nums`.
- Never more than three type sizes inside one section.
- Italic Libre Baskerville is used for reasoning text (slot explanations, source quotes).

### Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet">
```

Fallbacks: `"Libre Baskerville", Georgia, serif` · `"Jost", "Helvetica Neue", Arial, sans-serif` · `"IBM Plex Mono", ui-monospace, monospace`.

---

## 4. Layout and spacing

- **Grid:** 12 columns, 24px gutters, max width 1280px, side margin 48px desktop / 20px mobile.
- **Spacing scale (8px base):** 4, 8, 16, 24, 32, 48, 64, 96, 128.
- **Sections:** top edge is a 1px `--rule-strong` line, a small label on the left (`01 — Awaiting approval`), content on the right columns. This is the Swiss/Lovera numbered-section pattern.
- **Alignment:** flush left, ragged right. Never center body text.
- **Radius:** 0–2px. **Shadow:** none.
- **Breakpoints:** 390 / 768 / 1024 / 1280. Tables become stacked rows on mobile.

---

## 5. Components

| Component | Spec |
| --- | --- |
| **Wordmark** | "Meeting Organizer" in Libre Baskerville with a small superscript `™`-style mark, top left. Large on login. |
| **Nav** | Jost uppercase labels with an underline on active. No icons. A thin rule below. |
| **Primary button** | Ink fill, paper text, Jost uppercase 12px, `14px 24px`, 2px radius. Hover: accent fill. |
| **Secondary** | Text with 1px underline. Hover: underline thickens. |
| **Destructive** | Accent outline, accent text. |
| **Input** | Bottom border only (1px rule), no box. Focus: ink border and a 2px accent underline. Label above in Jost uppercase. |
| **Table** | Header row: Jost uppercase labels with a strong rule below. Rows separated by hairlines. Hover: `--tint`. No zebra stripes. |
| **Status** | Small Jost label with a 6px square marker (not a circle): Pending (warn), Approved (ok), Overdue (accent), Draft (ink-faint). |
| **Stat block** | Big serif numeral, tiny uppercase caption below, a rule above. |
| **Numbered list / FAQ rows** | `01`, `02` in Plex Mono at left; title in serif; expand with a thin plus sign. Use for agenda items and help. |
| **Process / timeline** | Used for the meeting lifecycle: steps `01 Schedule → 02 Agenda → 03 Meeting → 04 Minutes → 05 Actions`, each with its state and time taken. |
| **Glyph `⊹`** | Section dividers and list bullets, used sparingly. |
| **Dialog** | Paper surface, 1px ink border, no overlay blur (use 40% ink overlay). |
| **Toast** | Not used. Use inline banners with a left accent rule. |
| **Tabs** | Jost labels, active has a 2px ink underline. |
| **Quote block** | Italic serif with a left 2px rule; source timestamp in Plex Mono beneath. Used for grounded action items. |
| **Empty state** | One sentence and one text link. |

### Icons

Mostly none. Where needed (calendar, upload, download, search), 16px, 1.25 stroke, single color. Maximum 15 icons in the entire app.

---

## 6. Screens

### Login

- Left two-thirds: giant wordmark (display size) on paper, one italic line below: *"Meetings, minuted and followed through."*
- Right: sign-in form with bottom-border inputs, one primary button.
- Footer line: course name and year in Jost label style. No illustration.

### Dashboard

- Page title: today's date as `h1` ("Sunday, 4 October").
- Three numbered sections: `01 Awaiting approval`, `02 This week`, `03 Overdue`. Each is a plain table.
- Right margin: three stat blocks (meetings this month, actions closed on time, minutes approved).

### New meeting and slot picker

- Form on the left; ranked slots on the right as a ruled list.
- Each slot: time in serif, one italic line of reasoning, a "Select" text link.
- Room suggestion appears below as a plain row.

### Agenda editor

- Numbered rows `01 Item — owner — minutes`. Drag handle appears on hover only.
- Total time shown beside the title with a thin progress rule (ink on rule).

### Minutes review

- Two columns on paper. Left: transcript in Plex Mono, small, with timestamps. Right: minutes in serif with generous line height.
- Margin column for comments. Approve button fixed at the bottom, ink fill.
- Action items appear as quote blocks tied to transcript timestamps; clicking scrolls the transcript.

### Action tracker

- Table by default. Kanban toggle shows columns separated by vertical hairlines, cards are text rows without boxes.

### Memory chat

- Not a bubble UI. Question as a serif heading, answer as reading text with numbered footnotes; sources listed beneath in Plex Mono.

### Trace viewer

- Indented monospace tree, each step with duration and tokens right-aligned. Expand a step to see prompt and output. No timeline graphics.

### Evaluation

- Stat blocks for WER, F1, hallucination rate; one thin line chart per metric, direct labels, no legend, no gridlines beyond the baseline.

### Admin

- Plain tables and forms.

---

## 7. Motion

- Duration 120–180ms, ease-out. Opacity and 4px translate only.
- Page load: sections fade in top to bottom, 40ms apart.
- Numbers count up once on the dashboard (400ms). No looping animation anywhere.
- Hover: underline or tint changes only.
- Respect `prefers-reduced-motion`: all motion off.

---

## 8. Voice and microcopy

| Instead of | Write |
| --- | --- |
| "Welcome back!" | "Sunday, 4 October." |
| "Oops, something went wrong" | "The calendar could not be reached. Your draft is saved." |
| "Generate with AI" | "Draft minutes" |
| "Awesome! Meeting created" | "Meeting scheduled for Tuesday, 3 PM." |
| "No data yet" | "No meetings this week. Schedule one." |

Short, specific, no exclamation marks, no marketing verbs.

---

## 9. Implementation tokens

### CSS variables

```css
:root {
  --paper: #F6F3EE; --surface: #FBFAF7; --tint: #EFEBE4;
  --ink: #161513; --ink-soft: #5C5850; --ink-faint: #8F8A7F;
  --rule: #D9D4CA; --rule-strong: #161513;
  --accent: #8A2F1F; --accent-wash: #F0E1DC;
  --ok: #3F5B3A; --warn: #9A6B1C;
  --font-serif: "Libre Baskerville", Georgia, serif;
  --font-sans: "Jost", "Helvetica Neue", Arial, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --radius: 2px;
}
:root[data-theme="dark"] {
  --paper: #131210; --surface: #1A1917; --tint: #211F1C;
  --ink: #ECE7DD; --ink-soft: #A8A296; --ink-faint: #6F6A60;
  --rule: #2E2B27; --rule-strong: #ECE7DD;
  --accent: #C4533F; --accent-wash: #2A1814;
  --ok: #8DAA84; --warn: #D1A04E;
}
body { background: var(--paper); color: var(--ink); font-family: var(--font-serif); }
.label { font-family: var(--font-sans); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
```

### Tailwind (theme only, no defaults)

```ts
export default {
  theme: {
    colors: {
      paper: "var(--paper)", surface: "var(--surface)", tint: "var(--tint)",
      ink: "var(--ink)", soft: "var(--ink-soft)", faint: "var(--ink-faint)",
      rule: "var(--rule)", accent: "var(--accent)", ok: "var(--ok)", warn: "var(--warn)",
      transparent: "transparent", current: "currentColor",
    },
    fontFamily: { serif: ["Libre Baskerville", "Georgia", "serif"],
                  sans: ["Jost", "Helvetica Neue", "Arial", "sans-serif"],
                  mono: ["IBM Plex Mono", "monospace"] },
    borderRadius: { none: "0", DEFAULT: "2px" },
    boxShadow: {},
  },
};
```

---

## 10. Accessibility

- Visible focus ring on every control: 2px accent outline, 2px offset.
- Minimum tap target 44px.
- Full keyboard navigation, including approval and table rows.
- Labels on every input; errors announced with `aria-live`.
- Contrast checked in both themes before each phase closes.

---

## 11. Review checklist

- [ ] Only the three font families appear
- [ ] Accent appears at most once per screen section
- [ ] No box shadows, gradients, emoji, or default Tailwind colors
- [ ] Sections use numbered labels and top rules
- [ ] Tables, not cards, for lists of records
- [ ] Copy follows section 8
- [ ] Tested at 390px and 1280px, light and dark
- [ ] Screenshot test: it should look like a designed report, not a template