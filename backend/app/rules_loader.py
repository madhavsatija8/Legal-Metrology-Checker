"""
Single place that knows where rules/legal_metrology_rules.json lives and
how to read it — used by routers/rule_versions.py (to hash/activate it)
and by the Step 5 compliance engine (to read its actual content). Kept
separate from both so neither has to duplicate the path-resolution logic.
"""
import json
import os

# Default assumes running locally from the repo (backend/app/ -> up to the
# repo root -> rules/). In Docker the layout is flatter, so docker-compose.yml
# sets RULES_CONFIG_PATH=/app/rules/legal_metrology_rules.json explicitly —
# always prefer that over guessing relative paths across environments.
_DEFAULT_RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "rules", "legal_metrology_rules.json")
RULES_FILE = os.getenv("RULES_CONFIG_PATH", _DEFAULT_RULES_FILE)


def read_rules_raw() -> bytes:
    with open(RULES_FILE, "rb") as f:
        return f.read()


def load_rules() -> dict:
    """Parsed rule config, for the compliance engine to evaluate against.

    Note: this always reads the live file on disk, not the RuleVersion row
    stamped on a scan. If rules are edited without calling
    POST /rule-versions/sync-from-file, the file and the "active" DB record
    can drift apart — sync-from-file is what keeps them in step.
    """
    return json.loads(read_rules_raw())
