"""Single source of truth for the DPDP Act 2023 consent notice version.

Bump this string whenever the Privacy Policy / Terms of Service materially
change what personal data is collected or how it's used. Existing users
keep whatever version they originally consented to; the frontend re-prompts
for consent only where that matters (new signups).
"""

CONSENT_POLICY_VERSION = "2026-09-11"
