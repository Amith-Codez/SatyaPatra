# SatyaPatra console: design brief

This brief explains why the console looks and behaves the way it does. Each rule names its source and the place in the code where it is applied (`src/styles.css` unless stated).

## 1. Foundation: UX4G 3.0, not a custom look

The console uses the tokens of **UX4G 3.0**, the Government of India design system from NeGD/MeitY ([ux4g.gov.in/foundations](https://www.ux4g.gov.in/foundations)). The values were read from the CSS variables on ux4g.gov.in.

Why this and not a startup-style theme: AICTE officers use government portals every day. A console that matches UX4G feels familiar, follows GIGW-oriented accessibility rules, and can be adopted without a redesign.

| Token | Value | Where used |
|---|---|---|
| Primary | `#4A2BC2` (`--p-600`) | Primary buttons, active nav, links, focus ring |
| Primary dark | `#1A0E3D` (`--p-950`) | Government strip at the top |
| Primary tint | `#F2EFFF` (`--p-50`) | First-visit guide, avatar |
| Typeface | Noto Sans, Noto Sans Display, Noto Sans Mono, Noto Sans Devanagari | Body text, headings and numbers, IDs and hashes, Hindi |
| Radius scale | 2 / 4 / 8 / 12 / 16 / 24 px | Inputs 4, cards 8 to 12, dialogs 16 |
| Spacing | 4 px base | Every gap is a multiple of 4 |
| Focus ring | `0 0 0 2px #fff, 0 0 0 4px` primary | Every button, link, row and tab (`--ring`) |

## 2. Colour: meaning before mood

- **Status colours carry meaning only.** Green `#006C35` means Verified, red `#C62E26` Mismatch, orange `#B35A06` Expired, amber `#8A5800` Manual review, primary `#4A2BC2` Pending, grey `#5F5F5F` Source unavailable. Nothing decorative uses them, so a red dot always means "look here".
- **Status is never colour alone.** Each status is a dot plus a word, and the word has a plain-language tooltip (`STATUS_HELP` in `src/ui.tsx`). This helps colour-blind users and printouts.
- **Why purple-blue, and why not "blue = trust" as a slogan.** The UAE government design system notes that the trust link with blue is mostly convention, and that contrast and consistency matter more than hue ([designsystem.gov.ae](https://designsystem.gov.ae/insights/the-color-psychology-of-government-trust)). The console therefore keeps the official UX4G primary and spends its effort on contrast. All text colours meet WCAG AA on white.
- **One dominant colour.** The interface is about 90% neutral greys, the primary appears only on actions and the active page, and red appears only where there is a finding.

## 3. Typography: one family, hierarchy from size and weight

- **One family in four cuts** (Sans, Display, Mono, Devanagari), loaded locally via `@fontsource` so the console works offline. The [@supercharge.design typography rules](https://www.instagram.com/p/DP9N82Bj711/) and the other [#uidesigntips](https://www.instagram.com/explore/tags/uidesigntips/) carousels give the same advice: use 1 to 2 typefaces at most.
- **Base 14 px, ±2 px steps** for a data-dense tool (body 14, labels 12 to 13, page title 22, application name 24). Hierarchy comes from size, weight (400/500/600) and grey level, not from more fonts. Source: [The 80% of UI Design: Typography](https://www.youtube.com/watch?v=9-oefwZ6Z74).
- **Numbers are tabular** (`font-variant-numeric: tabular-nums`) and right-aligned in tables, so risk scores and timings line up.
- **IDs and hashes use the mono cut** and never wrap mid-token (`.table td.mono`).

## 4. Spacing and layout

- **8 px rhythm, outside-in.** The page has 28 to 32 px margins, sections are 24 px apart, items inside a group are 8 to 12 px apart, and the minimum gap is 6 px. Source: [Master Spacing in UI Design](https://www.youtube.com/watch?v=cf95Z7Ngg8k).
- **The sidebar is the spine.** It holds the product name, search, three daily pages, five "trust infrastructure" pages and live system status at the bottom. Source: [build a Dashboard UI in 8 minutes](https://www.youtube.com/watch?v=B7k5rOgmOGY).
- **Lists instead of bordered boxes.** Queues and findings are rows separated by hairlines rather than a grid of cards, because fewer borders mean less clutter (same video, plus the Instagram carousels).
- **Stats strip.** The four headline numbers sit in one strip with thin dividers rather than in four floating cards.

## 5. User experience: anyone can use it on the first visit

| Feature | What it does | Code |
|---|---|---|
| First-visit guide | Three steps (institutions upload, five engines check, you decide) with "Got it"; it stays dismissed | `pages/Overview.tsx` |
| Recommended next step | Every application opens with one sentence on what to do, and the recommended action is the only primary button (Mismatch → send for inspection, Manual review → request clarification, Verified → forward) | `pages/Application.tsx` `nextStep()` |
| Confirm before acting | Each decision opens a dialog that explains its effect, takes an optional note, closes on Esc, and shows the ledger fingerprint in a toast | `pages/Application.tsx` |
| Evidence on the page | Every finding is numbered, and the same number is drawn on the document where the problem is | `.viewer .mark` |
| Plain language | "White patch over text", not "pdf_overlay_edit"; "Warning sign, +25 risk", not "weight 25" | `pages/*.tsx` |
| What the statuses mean | A help panel on the queue explains all six PS statuses | `pages/Queue.tsx` |
| Search everywhere | ⌘K / Ctrl+K opens a palette that searches pages and applications, driven entirely by keyboard | `App.tsx` `Palette` |
| Try without a file | Eight sample documents run with one click, and a live five-step progress bar shows each engine finishing | `pages/Verify.tsx` |
| Friendly errors | Wrong file type or a file too large is explained in a sentence, not as an error code | `pages/Verify.tsx` |
| Empty states | Every list says what an empty result means and what to do next | `.empty` |
| Deep links | `/app/<id>?doc=<doc>&tab=geo` and `/verify?sample=<file>` open exactly the right view | `pages/Application.tsx`, `pages/Verify.tsx` |

## 6. Accessibility and inclusion

- Skip link to the main content, visible focus ring on every control, `aria-pressed` on toggles, `role="status"` on live results.
- **Text size A− / A / A+** in the government strip, which scales the whole console.
- **English / हिन्दी** switch for navigation, remembered per user.
- Respects `prefers-reduced-motion`.
- **Phone layout (≤ 900 px):** the sidebar becomes a sticky header with a swipeable page strip, tables scroll inside their own box, decision buttons stack under the explanation, and nothing scrolls the page sideways.

## 7. Things deliberately left out (the "AI-made" tells)

These were removed after the v2 review:

- Gradient backgrounds.
- Glowing cards.
- Emoji icons.
- Every element in its own bordered card.
- Several accent colours competing with each other.
- Centred body text.
- Decorative charts.
- Fake "AI confidence" percentages.

Every number on screen comes from the backend or from `data/eval/results.json`.
