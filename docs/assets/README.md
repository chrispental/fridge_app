# Source assets

`fridge_logo_source.png` is the original Fridge Chef artwork export (RGB, with a
baked-in checkerboard background). It is **not** used by the app. The transparent,
keyed-out derivatives the frontend actually serves live in `frontend/public/`:
`logo.png`, `logo-mark.png` (nav/login/onboarding), `favicon.png`, `apple-touch-icon.png`.
Regenerate those from this file if the logo ever changes.
