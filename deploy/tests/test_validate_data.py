import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validate-data.py"
SPEC = importlib.util.spec_from_file_location("validate_data", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_valid_dataset_and_duplicate_detection(tmp_path):
    def write_scene(name, scenario):
        scene = tmp_path / "category" / name
        scene.mkdir(parents=True)
        (scene / "scene_card.json").write_text(json.dumps({"scenario_name": scenario, "client_profile": {"role": "主任"}, "scoring_points": [{"id": "S1"}]}), encoding="utf-8")
        (scene / "knowledge_cards.json").write_text("[]", encoding="utf-8")
    write_scene("one", "场景一")
    report = MODULE.validate(tmp_path)
    assert not report["errors"]
    write_scene("two", "场景一")
    report = MODULE.validate(tmp_path)
    assert any("duplicate scenario_name" in item for item in report["errors"])


def test_empty_scene_is_a_blocking_error(tmp_path):
    (tmp_path / "category" / "empty").mkdir(parents=True)
    report = MODULE.validate(tmp_path)
    assert report["errors"]
