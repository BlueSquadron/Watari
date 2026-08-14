"""Property 23: Report Template Tag Population.

For any report template containing data tags, and for any case with data
in the referenced fields, generating a report SHALL substitute ALL
template tags with the corresponding current case data.

Feature: watari-case-management, Property 23: Report Template Tag Population
**Validates: Requirements 18.5**

Pure function tests against `reports.render_markdown` using Jinja2
with `StrictUndefined` — any unsubstituted tag SHALL raise an error.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jinja2 import UndefinedError

from src.services.reports import render_markdown


def test_simple_tag_substitution() -> None:
    tpl = "Title: {{ case.title }}"
    ctx = {"case": {"title": "Incident 42"}}
    assert render_markdown(tpl, ctx) == "Title: Incident 42"


def test_loop_over_observables() -> None:
    tpl = (
        "Observables:\n"
        "{% for o in observables %}"
        "- {{ o.type }}: {{ o.value }}\n"
        "{% endfor %}"
    )
    ctx = {
        "observables": [
            {"type": "ip", "value": "1.2.3.4"},
            {"type": "domain", "value": "example.org"},
        ]
    }
    result = render_markdown(tpl, ctx)
    assert "ip: 1.2.3.4" in result
    assert "domain: example.org" in result


def test_unsubstituted_tag_raises() -> None:
    """Using an undefined variable SHALL raise (StrictUndefined)."""
    with pytest.raises(UndefinedError):
        render_markdown("{{ missing.thing }}", {})


@given(
    titles=st.lists(
        st.text(alphabet="abcdefghijklmnop ", min_size=1, max_size=30),
        min_size=0,
        max_size=10,
    )
)
def test_all_loop_elements_present(titles: list[str]) -> None:
    """Every element in the source list SHALL appear in the rendered output."""
    tpl = "{% for t in titles %}* {{ t }}\n{% endfor %}"
    result = render_markdown(tpl, {"titles": titles})
    for title in titles:
        assert title in result
