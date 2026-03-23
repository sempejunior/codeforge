from __future__ import annotations

from codeforge.domain.entities.team import Team


def test_team_create_sets_defaults() -> None:
    team = Team.create(name="Platform")

    assert team.name == "Platform"
    assert team.description is None
    assert str(team.id)


def test_team_create_with_description() -> None:
    team = Team.create(name="Payments", description="Owns checkout flows")

    assert team.description == "Owns checkout flows"
