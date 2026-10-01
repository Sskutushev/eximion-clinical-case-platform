"""Load synthetic demo cases through the same validation + service path as the API."""

import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.schemas.cases import ClinicalCaseCreate
from app.services.cases import create_case

SEED_FILE = Path(__file__).with_name("seed_cases.json")


def main() -> None:
    engine = build_engine(get_settings())
    session_factory = build_session_factory(engine)
    payloads = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    for raw in payloads:
        with session_factory() as session:
            case_id = create_case(session, ClinicalCaseCreate.model_validate(raw))
        print(f"seeded {case_id}  {raw['title']}")
    engine.dispose()


if __name__ == "__main__":
    main()
