.PHONY: external-ai-e2e

# Production acceptance check for Claude / GPT-Image-2 / Hermes external
# execution. Never fakes a PASS — reports SKIPPED_NO_CREDENTIALS or
# OPTIONAL_NOT_RUNNING honestly when a provider/runtime is absent. See
# backend/scripts/external_ai_acceptance.py and docs/STATUS.md.
external-ai-e2e:
	cd backend && python3 scripts/external_ai_acceptance.py
