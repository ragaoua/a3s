import pathlib

from google.adk.skills import Skill
from google.adk.tools.skill_toolset import SkillToolset

from src.agent.skills import get_skill_toolsets
from tests.utils import write_skill


def _get_registered_skills(toolset: SkillToolset) -> dict[str, Skill]:
    return toolset._skills  # pyright: ignore[reportPrivateUsage]


def test_get_skill_toolsets_returns_empty_for_nonexistent_dir(
    tmp_path: pathlib.Path,
) -> None:
    missing = tmp_path / "does-not-exist"

    assert get_skill_toolsets(str(missing)) == []


def test_get_skill_toolsets_returns_empty_for_dir_with_no_skills(
    tmp_path: pathlib.Path,
) -> None:
    assert get_skill_toolsets(str(tmp_path)) == []


def test_get_skill_toolsets_loads_single_valid_skill(
    tmp_path: pathlib.Path,
) -> None:
    write_skill(tmp_path, "hello-skill", description="says hello")

    toolsets = get_skill_toolsets(str(tmp_path))

    assert len(toolsets) == 1
    toolset = toolsets[0]
    skills = _get_registered_skills(toolset)
    assert list(skills.keys()) == ["hello-skill"]
    loaded = skills["hello-skill"]
    assert loaded.frontmatter.name == "hello-skill"
    assert loaded.frontmatter.description == "says hello"
    assert loaded.instructions == "Body for hello-skill"


def test_get_skill_toolsets_loads_all_skills_in_dir(
    tmp_path: pathlib.Path,
) -> None:
    write_skill(tmp_path, "alpha-skill")
    write_skill(tmp_path, "beta-skill")
    write_skill(tmp_path, "gamma-skill")

    toolsets = get_skill_toolsets(str(tmp_path))

    assert len(toolsets) == 1
    toolset = toolsets[0]
    assert set(_get_registered_skills(toolset).keys()) == {
        "alpha-skill",
        "beta-skill",
        "gamma-skill",
    }


def test_get_skill_toolsets_skips_invalid_skill_dirs(
    tmp_path: pathlib.Path,
) -> None:
    write_skill(tmp_path, "good-skill")
    (tmp_path / "broken-skill").mkdir()  # no SKILL.md

    toolsets = get_skill_toolsets(str(tmp_path))

    assert len(toolsets) == 1
    toolset = toolsets[0]
    assert list(_get_registered_skills(toolset).keys()) == ["good-skill"]


def test_get_skill_toolsets_returns_empty_when_all_skill_dirs_are_invalid(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "broken-one").mkdir()
    (tmp_path / "broken-two").mkdir()

    assert get_skill_toolsets(str(tmp_path)) == []


def test_get_skill_toolsets_ignores_non_directory_entries(
    tmp_path: pathlib.Path,
) -> None:
    write_skill(tmp_path, "real-skill")
    (tmp_path / "stray-file.txt").write_text("not a skill", encoding="utf-8")

    toolsets = get_skill_toolsets(str(tmp_path))

    toolset = toolsets[0]
    assert list(_get_registered_skills(toolset).keys()) == ["real-skill"]
