# Durable project notes

These notes capture decisions and follow-ups, not a session log. Verify current
code and PR state before acting; update or remove notes as decisions change.

## Product decisions

- **Servings:** Home and Cook expose “Cooking for,” initially using household size.
  A request override does not change that default. Weekly plans default to household
  size and accept a per-plan override (plus a start date) when the plan is created.
  Generate the entire recipe for the selected count; do not just relabel servings
  or scale ingredients while leaving contradictory quantities in the steps.
- **Adjusting a recipe:** “Adjust recipe” rewrites a suggested meal in place from a
  short instruction and records the instruction on the recipe. Allergies, equipment,
  and the weather grill gate are re-enforced server-side; a rejected adjustment leaves
  the recipe untouched. Cooked and ordered meals are not adjustable.
- **Leftovers:** Saving leftovers is an opt-in checkbox when marking a meal cooked.
  The item is “leftover <title>” with an unknown amount and a four-day fridge estimate,
  so it surfaces in “use these first” without ever counting as stock for an ingredient.
- **Expiry estimates:** Manual entry prefills an expiry from category and storage
  (same table as photo scans) until the user picks a date. It is a visible suggestion,
  never a silent fact; pantry goods with no basis for an estimate stay blank.
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
- **Shopping:** Plan shopping covers only meals still to cook, excluding cooked
  meals and delivery nights. An individual recipe can still be imported for an
  intentional repeat. Ordinary cooking water needs no purchase; specialty waters
  such as coconut, bottled, and sparkling water remain inventory items.
- **Shopping edits:** Quantity/unit edits represent the amount purchased, which
  moves into inventory. A blank quantity stays unknown; editing preserves whether
  the item is checked and where it was imported from.
- **Cooking recovery:** Surface the latest unfinished cooking session throughout
  the app. Dismissing its reminder keeps the recipe's saved steps and timers.

## Previously recorded environment context

- A September 1, 2026 project memory records Supabase's free plan and an accepted
  “Leaked Password Protection Disabled” advisory due to that plan's limitations.
  This is historical context, not a current account check. Reverify plan/capability
  changes when relevant instead of repeatedly presenting the same accepted advisory
  as a newly discovered issue.
- More extensive architecture context lives in `CLAUDE.md`. Machine-local Claude
  memories also exist, but important shared decisions should live in this repository
  so they remain available across tools and future checkouts.
