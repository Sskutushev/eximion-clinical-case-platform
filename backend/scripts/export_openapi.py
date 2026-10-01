"""Write the OpenAPI document (contract source of truth) to contracts/openapi.json.

Deterministic output (sorted keys) so CI can detect drift with `git diff --exit-code`.
No database connection is needed.
"""

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    schema = create_app(Settings(environment="local")).openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OpenAPI written to {output}")


if __name__ == "__main__":
    main()
