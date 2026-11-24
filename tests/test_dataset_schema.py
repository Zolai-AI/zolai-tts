import json
from pathlib import Path

import jsonschema

from zolai_tts.data.validate import load_schema, validate_jsonl, validate_record

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "dataset/schemas/utterance.schema.json"
MANIFEST_SCHEMA = ROOT / "dataset/schemas/metadata.schema.json"
SAMPLE = ROOT / "dataset/metadata/sample.jsonl"


def _sample_record() -> dict[str, object]:
    return json.loads(SAMPLE.read_text(encoding="utf-8").splitlines()[0])


def test_both_schemas_compile_as_draft2020_12() -> None:
    for path in (SCHEMA, MANIFEST_SCHEMA):
        jsonschema.Draft202012Validator.check_schema(load_schema(path))


def test_sample_jsonl_matches_utterance_schema() -> None:
    report = validate_jsonl(SAMPLE, SCHEMA)
    assert report.checked == 3
    assert report.valid, report.errors


def test_required_field_missing_is_reported() -> None:
    record = _sample_record()
    del record["consent"]
    errors = validate_record(record, load_schema(SCHEMA))
    assert any("consent" in error for error in errors)


def test_wrong_type_is_reported() -> None:
    record = _sample_record()
    record["sample_rate"] = "22050"
    errors = validate_record(record, load_schema(SCHEMA))
    assert any("sample_rate" in error for error in errors)


def test_unknown_language_value_is_rejected() -> None:
    record = _sample_record()
    record["language"] = "mizo"
    errors = validate_record(record, load_schema(SCHEMA))
    assert any("language" in error for error in errors)


def test_absolute_audio_path_is_rejected() -> None:
    record = _sample_record()
    record["audio_path"] = "/absolute/utt.wav"
    errors = validate_record(record, load_schema(SCHEMA))
    assert any("audio_path" in error for error in errors)


def test_validate_jsonl_reports_line_numbers(tmp_path: Path) -> None:
    good = SAMPLE.read_text(encoding="utf-8").splitlines()[0]
    bad = good.replace('"language":"ted"', '"language":"mizo"')
    path = tmp_path / "bad.jsonl"
    path.write_text("\n".join((good, bad)) + "\n", encoding="utf-8")
    report = validate_jsonl(path, SCHEMA)
    assert report.checked == 2
    assert any(error.startswith("line 2:") for error in report.errors)
