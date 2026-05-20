import pytest
from src.generate_ostris_config import parse_overrides


def test_parse_overrides_coerces_common_types() -> None:
    overrides = parse_overrides([
        "steps=100",
        "lr=0.0001",
        "use_gc=true",
        "resume=null",
        "name=flux2",
    ])

    assert overrides["steps"] == 100
    assert overrides["lr"] == 0.0001
    assert overrides["use_gc"] is True
    assert overrides["resume"] is None
    assert overrides["name"] == "flux2"


def test_parse_overrides_rejects_missing_separator() -> None:
    with pytest.raises(ValueError) as exc:
        parse_overrides(["not_an_override"])

        assert "key=value" in str(exc)



