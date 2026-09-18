# Durable project notes

These notes capture decisions and follow-ups, not a session log. Verify current
code and PR state before acting; update or remove notes as decisions change.

## Product decisions

- **Servings:** Home and Cook expose “Cooking for,” initially using household size.
  A request override does not change that default. Weekly plans use household size.
  Generate the entire recipe for the selected count; do not just relabel servings
  or scale ingredients while leaving contradictory quantities in the steps.
- **Cooking safety:** Keep guidance calm, brief, and specific to handling hazards.
  The user explicitly found repeated hot warnings excessive. Do not add a warning
  to routine preheating/simmering or repeat a precaution already in the instruction.
  Avoid false positives such as “hot sauce.” These reminders are heuristic, not a
  comprehensive safety check.
- **Visuals:** Consistent cooking-method and food-category icons replace unrelated
  stock/search photos. Keep related recipe links. Uploaded fridge/receipt photos
  still belong in the extraction/review workflow.
- **Inventory:** Use conservative ingredient identity. Pantry pepper must not make
  bell pepper appear available; butter must not cover peanut butter. Unknown
  quantities or incompatible units require checking, not an “in stock” claim.

## Follow-up from September 18, 2026

- Sync `design.pen` with the serving controls, focused cooking warnings, and
  icon-based meal/inventory views introduced in
  [PR #41](https://github.com/chrispental/fridge_app/pull/41).
  The user explicitly deferred this sync after the Pen/Pencil connector could not
  read the design. Reconnect and verify the existing document loads before editing.
  Remove this follow-up once the design is synced.

## Previously recorded environment context

- A September 1, 2026 project memory records Supabase's free plan and an accepted
  “Leaked Password Protection Disabled” advisory due to that plan's limitations.
  This is historical context, not a current account check. Reverify plan/capability
  changes when relevant instead of repeatedly presenting the same accepted advisory
  as a newly discovered issue.
- More extensive architecture context lives in `CLAUDE.md`. Machine-local Claude
  memories also exist, but important shared decisions should live in this repository
  so they remain available across tools and future checkouts.
