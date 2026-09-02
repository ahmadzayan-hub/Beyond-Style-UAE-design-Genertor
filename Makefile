.PHONY: external-ai-e2e check-pins calibration-coupon

# Production acceptance check for Claude / GPT-Image-2 / Hermes external
# execution. Never fakes a PASS — reports SKIPPED_NO_CREDENTIALS or
# OPTIONAL_NOT_RUNNING honestly when a provider/runtime is absent. See
# backend/scripts/external_ai_acceptance.py and docs/STATUS.md.
external-ai-e2e:
	cd backend && python3 scripts/external_ai_acceptance.py

# Fail if the local Python environment drifted from backend/requirements.txt
# (the drift that once kept CI red for eight commits while local runs
# looked green). Run before committing.
check-pins:
	python3 scripts/check_env_pins.py

# Workshop calibration kit: cut/engrave the coupon once, record clean
# features, then `python3 scripts/calibrate_workshop.py apply ... --write`.
calibration-coupon:
	python3 scripts/calibrate_workshop.py coupon --out docs/evidence/calibration/
