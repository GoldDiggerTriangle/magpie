import json
from pathlib import Path


CONDITION_ENUMS = json.loads(Path(__file__).with_name("condition_enums.json").read_text(encoding="utf-8"))["values"]
