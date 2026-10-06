from pathlib import Path

import pytest

from wildquest.quests.models import QuestType, Requirement, load_quests


QUEST_DIR = Path(__file__).parents[1] / "data/quests"


def test_catalog_has_at_least_30_unique_valid_quests_and_all_types() -> None:
    quests = load_quests(QUEST_DIR)
    assert len(quests) >= 30
    assert {quest.type for quest in quests.values()} == set(QuestType)
    assert all(Requirement.DAYLIGHT in quest.requires for quest in quests.values())
    assert all(Requirement.MARKED_TRAIL in quest.requires for quest in quests.values())


def test_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text(
        """
id: bad-quest
type: observe
difficulty: easy
duration_min: 1
requires: [daylight, marked_trail]
prompt_seed: This prompt is long enough.
success_criteria: This criterion is valid.
hint: A valid hint.
safety_notes: These safety notes are valid.
surprise: forbidden
"""
    )
    with pytest.raises(ValueError):
        load_quests(tmp_path)
