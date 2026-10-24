# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The text-taking tools answer any input with a payload, never a raise.

An agent hands ``validate_xml``, ``parse_message`` and ``convert_mt103``
whatever text it holds. Each must return its result or an ``{"error":
...}`` payload; an exception reaches the client only as an opaque "Error
executing tool" with the reason lost. ``fuzz/fuzz_tools.py`` drives the
same contract with Atheris; these are its fixed and property-based cases.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pacs008_mcp.server as server

MSG_TYPE = "pacs.008.001.08"

#: Documents that declare DTD entities: external (XXE) and nested
#: (billion laughs). defusedxml refuses both.
ENTITY_DOCUMENTS = (
    '<!DOCTYPE a [<!ENTITY e SYSTEM "file:///etc/passwd">]><a>&e;</a>',
    '<!DOCTYPE a [<!ENTITY x "y"><!ENTITY z "&x;&x;">]><a>&z;</a>',
)

#: Text shaped like XML often enough to get past the first byte.
_XMLISH = st.one_of(
    st.text(max_size=200),
    st.text(max_size=60).map(lambda body: f"<Document>{body}</Document>"),
    st.sampled_from(ENTITY_DOCUMENTS),
)


@pytest.mark.parametrize("xml", ENTITY_DOCUMENTS)
def test_validate_xml_refuses_entity_declarations_with_error(xml):
    """defusedxml's EntitiesForbidden comes back as an error payload."""
    result = server.validate_xml(MSG_TYPE, xml)
    assert set(result) == {"error"}
    assert result["error"].startswith("refused XML: EntitiesForbidden(")


@given(xml=_XMLISH)
def test_validate_xml_answers_any_text(xml):
    """Any text gets a verdict or an error payload."""
    result = server.validate_xml(MSG_TYPE, xml)
    assert set(result) in ({"error"}, {"message_type", "is_valid"})


@given(xml=_XMLISH)
def test_parse_message_answers_any_text(xml):
    """Any text gets a classification or an error payload."""
    assert isinstance(server.parse_message(xml), dict)


@given(text=st.text(max_size=300))
def test_convert_mt103_answers_any_text(text):
    """Any text gets records or an error payload."""
    assert isinstance(server.convert_mt103(text), dict)


def test_validate_xml_answers_an_out_of_range_year_with_error():
    """elementpath's OverflowError on a year past datetime's range is a payload.

    Atheris found it: a ``CreDtTm`` year with more digits than datetime holds
    made the XSD validator raise ``OverflowError: year overflow``.
    """
    with open("fuzz/corpus/pacs008-generated.xml", encoding="utf-8") as fh:
        xml = fh.read().replace(
            "<CreDtTm>2026-01-15T10:30:00</CreDtTm>",
            "<CreDtTm>99999999999-01-15T10:30:00</CreDtTm>",
        )
    assert "99999999999" in xml
    result = server.validate_xml(MSG_TYPE, xml)
    assert set(result) == {"error"}
    assert "OverflowError" in result["error"]
