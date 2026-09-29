# Security Rules
- Passwords hashed with bcrypt or argon2. Never store, log, or transmit
  plaintext passwords. Never email a password — only email invite/reset
  LINKS, which are single-use and time-limited.
- No secrets, API keys, or credentials in code. Use a .env file (already
  git-ignored) and a .env.example with placeholder values checked into git.
- Every backend endpoint must check the caller's role tier before
  returning any data — see docs/permissions.md.
- Internal export and Tracking Sheet downloads, and any Cost
  Price/Margin field, must be blocked SERVER-SIDE (return 403 to a
  Sales or Catalog Entry tier user). Hiding a button in the UI is a
  nicety, never the actual guard — assume a user can call the API directly.
- A Sales-tier user's API responses must never include cost or margin
  fields, even if the frontend doesn't render them.
- Invite and password-reset tokens must be single-use and expire after a
  short, defined window.
- Flag clearly in your output when you've written authentication or
  access-control code — this is the part of the build that most needs a
  human security review before go-live (see docs/requirements.md, NFR-9).
