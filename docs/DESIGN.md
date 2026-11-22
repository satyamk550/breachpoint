# Frontend design system

This foundation preserves the existing CTF interface: near-black green-tinted
surfaces, one lime accent, compact mono labels, Space Grotesk display type, the
four-square mark, and thin borders with restrained corners. The values below
were extracted from the original status page styles.

## Brand

`src/config/brand.ts` is the only source of the platform name and tagline.
`VITE_APP_NAME` can override the default name at build time. Header, footer,
document title, and page metadata read from this config. Do not copy the brand
name into components or HTML metadata.

## Tokens

Tokens are declared in `src/styles/tokens.css` and exposed as Tailwind theme
extensions in `tailwind.config.ts`. Component styles refer to semantic token
names. Keep literal color values confined to the token declarations and favicon.

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#101210` | Page background |
| `--color-surface` | `#171a16` | Cards and controls |
| `--color-surface-raised` | `#1d2218` | Hovered/raised controls |
| `--color-border` | `#30342d` | Card and divider borders |
| `--color-border-strong` | `#393e34` | Control borders |
| `--color-text` | `#f2f1e9` | Primary text |
| `--color-text-muted` | `#92968c` | Supporting text |
| `--color-accent` | `#d5f379` | Brand lime |
| `--color-accent-contrast` | `#101210` | Text on lime |
| `--color-success` | `#b7c98a` | Healthy state |
| `--color-warning` | `#d5f379` | Warning state, reuses the brand accent |
| `--color-danger` | `#e2825d` | Error state |
| `--color-info` | `#a4a99b` | Informational state |
| `--radius-sm` / `--radius-control` / `--radius` | `5px / 6px / 8px` | Buttons, icons, cards |
| `--shadow-sm` / `--shadow-md` | `none / none` | Preserve the flat original surfaces |
| `--shadow-focus` / `--shadow-status` | accent-tinted | Keyboard focus and live state |

Semantic warning and informational tokens reuse colors already present in the
original status styles. Do not add a second accent or a new status palette.

### Typography

Fonts are served locally with `@fontsource`, so the interface works on an
offline event LAN.

| Token | Font | Existing use |
|---|---|---|
| `--font-body` | DM Sans | Body copy and controls |
| `--font-display` | Space Grotesk | Brand and headings |
| `--font-mono` | DM Mono | Small uppercase labels and status data |

The type scale retains the original 9px labels, 10px captions, 11px small copy,
14px body, 16px cards, 18px titles, 25px section headings, and the responsive
52px-76px display headline.

### Spacing and layout

The page keeps the original 1120px content width, 40px desktop page gutters,
84px header, 92px intro top spacing, 30px section separation, 20px card padding,
14px grid gap, and 62px footer separation. At small widths the gutter reduces
to 20px, the header to 72px, and service cards use one column. Above 1600px,
the centered max-width composition gains vertical breathing room for projector
visibility without becoming a separate projector interface.

## Component use

Import primitives from `src/components/ui`. They have typed props and use the
semantic tokens:

```tsx
<Button variant="primary" loading={saving}>Save</Button>
<Card><CardHeader><CardTitle>Service</CardTitle></CardHeader></Card>
<Badge variant="success" role="status">Operational</Badge>
```

- `Button` supports primary, secondary, ghost, danger, and loading states.
- `Card` has header, title, description, content, and footer parts.
- `Badge` offers success, warning, danger, info, and neutral status variants.
- `Label`, `Input`, `Textarea`, `Select`, and `FieldError` form accessible field
  building blocks. Labels belong above controls; errors should be connected
  using `aria-describedby`.
- `Dialog` and `Tooltip` use Radix primitives for keyboard behavior, focus
  management, Escape dismissal, and accessible relationships.
- `ToastProvider` and `useToast` provide transient announcements. Toasts are
  suitable for action feedback, not persistent validation errors.
- `Skeleton`, `Spinner`, and `EmptyState` cover loading and no-data states.
- `Tabs` uses roving keyboard focus. `Table<Row>` requires typed columns,
  stable row keys, and an accessible caption.
- `CopyButton` copies only on explicit user action; it does not persist or log
  copied values. Keep secrets out of rendered text unless disclosure is an
  explicit part of the screen.

The app shell provides the skip link, header, responsive status navigation,
main landmark, and footer. Radix Tooltip's provider and TanStack Query's client
are installed once in `src/main.tsx`.

## Data layer

`src/api/client.ts` prefixes requests with `/api/v1`, includes same-origin
credentials, parses JSON, reports HTTP errors as `ApiError`, and times out
requests. Add a CSRF header at its marked hook point when cookie-authenticated
mutations are introduced. Do not store credentials in browser storage.

`useHealth` polls every 15 seconds while visible, pauses background polling,
backs off after failures, and accepts the health endpoint's 503 response body
to distinguish dependency degradation from an unreachable backend.

## Rules for future screens

- **Login:** use the field primitives, visible labels, inline errors, and the
  same surface/button tokens. Never place passwords or tokens in browser
  storage or toast text.
- **Challenge board:** keep challenge visibility and state in semantic badges;
  use responsive cards with the existing border/radius rules. Never render a
  challenge flag in the page.
- **Scoreboard:** use a captioned `Table` for team rows and preserve readable
  number alignment. Keep score derivation on the server.
- **Admin tables:** use `Table<Row>` with stable keys and explicit empty,
  loading, and error states. Keep action buttons keyboard reachable and
  announce destructive outcomes.
- **All screens:** use `brand` for platform metadata, tokens for colors and
  spacing, semantic landmarks, visible `:focus-visible` states, and reduced
  motion fallbacks. Test at 360px, 1280px, and 1920px. Do not introduce routes
  or product workflows before their assigned phase.
