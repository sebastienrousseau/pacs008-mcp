# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the Pacs008 MCP server."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from mcp.server.fastmcp import FastMCP  # noqa: E402
from pacs008.standards.bah import BusinessApplicationHeader  # noqa: E402
from pacs008.xml.parser import ParsedMessage  # noqa: E402

import pacs008_mcp.server as server  # noqa: E402

MSG_TYPE = "pacs.008.001.08"

EXPECTED_TOOLS = {
    "list_message_types",
    "list_schemes",
    "get_scheme",
    "get_required_fields",
    "get_input_schema",
    "validate_records",
    "validate_scheme",
    "generate_message",
    "validate_xml",
    "parse_message",
    "convert_mt103",
    "classify_address",
    "validate_address",
    "repair_address",
    "validate_addresses",
}


def _registered_tool_names() -> set[str]:
    """Return the names of every tool registered on the FastMCP server."""
    manager = getattr(server.server, "_tool_manager", None)
    if manager is not None and hasattr(manager, "list_tools"):
        return {tool.name for tool in manager.list_tools()}
    tools = asyncio.run(server.server.list_tools())
    return {tool.name for tool in tools}


def _tool_input_schema(name: str) -> dict:
    """Return the JSON input schema a client sees for the named tool."""
    for tool in asyncio.run(server.server.list_tools()):
        if tool.name == name:
            return tool.inputSchema
    raise AssertionError(f"tool not registered: {name}")


# ---------------------------------------------------------------------------
# Registration / schema metadata
# ---------------------------------------------------------------------------


def test_server_and_main_are_well_formed():
    """The module exposes a FastMCP server and a callable ``main``."""
    assert isinstance(server.server, FastMCP)
    assert callable(server.main)


def test_all_tools_registered():
    """All fifteen tools are registered on the server."""
    assert _registered_tool_names() == EXPECTED_TOOLS
    assert len(EXPECTED_TOOLS) == 15


def test_message_type_param_exposes_enum():
    """Closed-set message_type surfaces its 20 values as JSON-Schema enum."""
    prop = _tool_input_schema("get_input_schema")["properties"]["message_type"]
    assert prop["enum"] == server._MESSAGE_TYPE_VALUES
    assert len(prop["enum"]) == 20


def test_scheme_param_exposes_enum():
    """Closed-set scheme surfaces the registry aliases as JSON-Schema enum."""
    prop = _tool_input_schema("get_scheme")["properties"]["scheme"]
    assert prop["enum"] == server._SCHEME_VALUES
    # The 7 canonical profiles are all valid enum values.
    assert {"cbpr_plus", "chaps", "fedwire", "generic"} <= set(prop["enum"])


# ---------------------------------------------------------------------------
# list_message_types / list_schemes
# ---------------------------------------------------------------------------


def test_list_message_types_returns_20():
    """The list tool reports every supported message type (20)."""
    result = server.list_message_types()
    assert isinstance(result, list)
    assert len(result) == 20
    assert all("message_type" in r and "name" in r for r in result)
    assert {
        "message_type": MSG_TYPE,
        "name": "FI to FI Customer Credit Transfer",
    } in result


def test_message_type_name_unknown_family_falls_back():
    """An unknown family returns the raw message type as its name."""
    assert server._message_type_name("zzzz.999.999.99") == "zzzz.999.999.99"


def test_list_schemes_dedupes_to_canonical():
    """Registry aliases collapse to the 7 canonical profiles."""
    result = server.list_schemes()
    names = {r["scheme"] for r in result}
    assert names == {
        "cbpr_plus",
        "chaps",
        "fedwire",
        "generic",
        "hvps_plus",
        "sct_inst",
        "t2_rtgs",
    }
    assert all(r["scheme"] == r["name"] for r in result)


# ---------------------------------------------------------------------------
# get_scheme
# ---------------------------------------------------------------------------


def test_get_scheme_returns_rules():
    """A known scheme returns its rule attributes."""
    rules = server.get_scheme("cbpr_plus")
    assert rules["name"] == "cbpr_plus"
    assert rules["uetr_required"] is True
    assert rules["max_remit_info_len"] == 140
    assert sorted(rules["allowed_charge_bearers"]) == [
        "CRED",
        "DEBT",
        "SHAR",
        "SLEV",
    ]
    assert isinstance(rules["pinned_versions"], dict)
    assert isinstance(rules["lei_required_for"], list)


def test_get_scheme_unknown_returns_error():
    """An unknown scheme returns an error dict, not an exception."""
    result = server.get_scheme("does-not-exist")
    assert "error" in result


# ---------------------------------------------------------------------------
# get_required_fields / get_input_schema
# ---------------------------------------------------------------------------


def test_get_required_fields_lists_fields():
    """Required fields for pacs.008 include the core mandatory columns."""
    fields = server.get_required_fields(MSG_TYPE)
    assert "msg_id" in fields
    assert "interbank_settlement_amount" in fields


def test_get_required_fields_invalid_type_returns_error_entry():
    """An unsupported message type yields an error string entry."""
    result = server.get_required_fields("pacs.999.999.99")
    assert any("error" in str(item) for item in result)


def test_get_input_schema_returns_schema():
    """The full JSON Schema is returned for a valid message type."""
    schema = server.get_input_schema(MSG_TYPE)
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "msg_id" in schema["properties"]


def test_get_input_schema_invalid_type_returns_error_dict():
    """An unsupported message type returns an ``{"error": ...}`` dict."""
    result = server.get_input_schema("pacs.999.999.99")
    assert isinstance(result, dict)
    assert "error" in result


# ---------------------------------------------------------------------------
# validate_records
# ---------------------------------------------------------------------------


def test_validate_records_valid_report(sample_record):
    """A well-formed record validates cleanly with a full report shape."""
    report = server.validate_records(MSG_TYPE, [sample_record])
    assert report["is_valid"] is True
    assert report["total"] == 1
    assert report["valid"] == 1
    assert report["errors"] == []


def test_validate_records_reports_errors(sample_record):
    """A record missing a required field is reported invalid, not raised."""
    incomplete = dict(sample_record)
    incomplete.pop("msg_id")
    report = server.validate_records(MSG_TYPE, [incomplete])
    assert report["is_valid"] is False
    assert report["valid"] < report["total"]
    assert report["errors"]
    err = report["errors"][0]
    assert {"row", "field", "message", "value"} <= set(err)


def test_validate_records_invalid_type_returns_error_dict():
    """An unsupported message type returns an ``{"error": ...}`` dict."""
    result = server.validate_records("pacs.999.999.99", [{}])
    assert isinstance(result, dict)
    assert "error" in result


# ---------------------------------------------------------------------------
# validate_scheme
# ---------------------------------------------------------------------------


def test_validate_scheme_clean_batch(sample_record):
    """The permissive generic profile flags no violations."""
    report = server.validate_scheme("generic", [sample_record])
    assert report["scheme"] == "generic"
    assert report["is_valid"] is True
    assert report["total"] == 1
    assert report["violations"] == []


def test_validate_scheme_reports_violations():
    """A record missing a mandatory UETR is flagged under fedwire."""
    record = {"charge_bearer": "SHAR", "interbank_settlement_amount": "1.00"}
    report = server.validate_scheme("fedwire", [record])
    assert report["is_valid"] is False
    assert report["violations"]
    v = report["violations"][0]
    assert {"row", "party", "field", "rule", "message", "severity"} <= set(v)


def test_validate_scheme_unknown_returns_error():
    """An unknown scheme returns an error dict, not an exception."""
    result = server.validate_scheme("nope", [{}])
    assert "error" in result


# ---------------------------------------------------------------------------
# generate_message
# ---------------------------------------------------------------------------


def test_generate_message_returns_xml(sample_record):
    """Generating pacs.008.001.08 yields a validated XML document."""
    xml = server.generate_message(MSG_TYPE, [sample_record])
    assert isinstance(xml, str)
    assert xml.lstrip().startswith("<?xml")
    assert "Document" in xml


def test_generate_message_caches_staged_template(sample_record):
    """A second generation reuses the staged template (cache hit branch)."""
    first = server.generate_message(MSG_TYPE, [sample_record])
    second = server.generate_message(MSG_TYPE, [sample_record])
    assert first == second


def test_generate_message_invalid_type_returns_error(sample_record):
    """An unsupported message type returns a serialized error payload."""
    out = server.generate_message("pacs.999.999.99", [sample_record])
    payload = json.loads(out)
    assert "error" in payload


def test_generate_message_missing_fields_returns_error():
    """A record missing required fields yields a serialized error, not a raise."""
    out = server.generate_message(MSG_TYPE, [{}])
    payload = json.loads(out)
    assert "error" in payload


# ---------------------------------------------------------------------------
# validate_xml
# ---------------------------------------------------------------------------


def test_validate_xml_accepts_generated_document(sample_record):
    """A freshly generated document validates against its XSD."""
    xml = server.generate_message(MSG_TYPE, [sample_record])
    result = server.validate_xml(MSG_TYPE, xml)
    assert result == {"message_type": MSG_TYPE, "is_valid": True}


def test_validate_xml_rejects_garbage():
    """Malformed XML fails XSD validation but does not raise."""
    result = server.validate_xml(MSG_TYPE, "<not-valid/>")
    assert result["is_valid"] is False


def test_validate_xml_invalid_type_returns_error():
    """An unsupported message type returns an error dict."""
    result = server.validate_xml("pacs.999.999.99", "<x/>")
    assert "error" in result


# ---------------------------------------------------------------------------
# parse_message
# ---------------------------------------------------------------------------


def test_parse_message_classifies_generated_document(sample_record):
    """A generated pacs.008 document is parsed and classified (no BAH)."""
    xml = server.generate_message(MSG_TYPE, [sample_record])
    result = server.parse_message(xml)
    assert result["msg_family"] == "pacs.008"
    assert result["msg_def_idr"] == MSG_TYPE
    assert result["envelope_wrapped"] is False
    assert result["bah"] is None


def test_parse_message_malformed_returns_error():
    """Malformed XML returns an error dict rather than raising."""
    result = server.parse_message("<not-xml")
    assert "error" in result


def test_parse_message_serializes_bah(monkeypatch):
    """A BAH-wrapped message serializes the header into a dict."""
    bah = BusinessApplicationHeader(
        sender_bic="DEUTDEFF",
        receiver_bic="COBADEFF",
        biz_msg_idr="BIZ-001",
        msg_def_idr="pacs.008.001.08",
        creation_dt="2026-01-15T10:30:00",
        priority="NORM",
        signature=None,
    )
    parsed = ParsedMessage(
        msg_def_idr="pacs.008.001.08",
        msg_family="pacs.008",
        version="001.08",
        bah=bah,
        root_local_name="Document",
        namespace_uri="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
        envelope_wrapped=True,
    )
    monkeypatch.setattr(server, "parse", lambda xml: parsed)
    result = server.parse_message("<ignored/>")
    assert result["envelope_wrapped"] is True
    assert result["bah"]["sender_bic"] == "DEUTDEFF"
    assert result["bah"]["msg_def_idr"] == "pacs.008.001.08"


# ---------------------------------------------------------------------------
# convert_mt103
# ---------------------------------------------------------------------------

# A realistic, complete MT103 covering every mapped field (mirrors the
# pacs008-loader-mt103 library's own `_full_mt103` test fixture).
_FULL_MT103 = (
    ":20:REF20240712001\n"
    ":23B:CRED\n"
    ":32A:260712EUR12345,67\n"
    ":50K:/DE89370400440532013000\n"
    "JOHN DOE\n"
    "123 MAIN STREET\n"
    "BERLIN\n"
    ":52A:DEUTDEFF\n"
    ":57A:CHASUS33\n"
    ":59:/GB29NWBK60161331926819\n"
    "ACME TRADING LTD\n"
    "1 CORPORATE AVENUE\n"
    "LONDON\n"
    ":70:INVOICE 998877\n"
    ":71A:SHA\n"
)


def test_convert_mt103_maps_expected_pacs008_record():
    """A complete MT103 converts to the expected single pacs.008 record."""
    result = server.convert_mt103(_FULL_MT103)
    assert result["message_type"] == MSG_TYPE
    assert result["records"] == [
        {
            "msg_id": "REF20240712001",
            "end_to_end_id": "REF20240712001",
            "creation_date_time": "2026-07-12T00:00:00",
            "nb_of_txs": 1,
            "settlement_method": "CLRG",
            "interbank_settlement_amount": 12345.67,
            "interbank_settlement_currency": "EUR",
            "charge_bearer": "SHAR",
            "debtor_name": "JOHN DOE",
            "debtor_agent_bic": "DEUTDEFF",
            "creditor_agent_bic": "CHASUS33",
            "creditor_name": "ACME TRADING LTD",
        }
    ]


def test_convert_mt103_record_is_schema_valid():
    """The converted record validates against the pacs.008 JSON Schema.

    The KEY correctness proof: the MT103 output is fed straight into the
    server's own ``validate_records`` tool and comes back clean, so it can
    drive ``generate_message`` unchanged.
    """
    result = server.convert_mt103(_FULL_MT103)
    report = server.validate_records(MSG_TYPE, result["records"])
    assert report["is_valid"] is True
    assert report["total"] == 1
    assert report["valid"] == 1
    assert report["errors"] == []


def test_convert_mt103_output_generates_xml():
    """The converted record drives generate_message to a validated document."""
    result = server.convert_mt103(_FULL_MT103)
    xml = server.generate_message(MSG_TYPE, result["records"])
    assert xml.lstrip().startswith("<?xml")
    assert "Document" in xml


def test_convert_mt103_malformed_returns_error():
    """An MT103 missing a mandatory field returns an ``{"error": ...}`` dict."""
    result = server.convert_mt103(":23B:CRED\n")
    assert isinstance(result, dict)
    assert "error" in result
    assert "records" not in result


# ---------------------------------------------------------------------------
# November 2026 structured-address tools
# ---------------------------------------------------------------------------

_STRUCTURED_ADDRESS = {
    "strt_nm": "High Street",
    "bldg_nb": "1",
    "pst_cd": "AB1 2CD",
    "twn_nm": "London",
    "ctry": "GB",
}
_HYBRID_ADDRESS = {
    "twn_nm": "London",
    "ctry": "GB",
    "adr_line": ["1 High Street"],
}
_UNSTRUCTURED_ADDRESS = {"adr_line": ["1 High Street", "London"]}


def test_address_policy_param_exposes_enum():
    """The address policy param surfaces the AddressPolicy values as enum."""
    prop = _tool_input_schema("validate_address")["properties"]["policy"]
    assert prop["enum"] == server._ADDRESS_POLICY_VALUES
    assert set(prop["enum"]) == {
        "unstructured_ok",
        "hybrid_or_structured",
        "structured_only",
    }
    # The default is the November 2026 cliff policy.
    assert prop["default"] == "hybrid_or_structured"


def test_classify_address_structured():
    """A full structured address classifies as structured."""
    result = server.classify_address(_STRUCTURED_ADDRESS)
    assert result["classification"] == "structured"
    assert result["is_structured"] is True
    assert result["is_hybrid"] is False
    assert result["is_unstructured"] is False
    assert result["has_structured_fields"] is True


def test_classify_address_hybrid():
    """Town + country + one free-form line classifies as hybrid."""
    result = server.classify_address(_HYBRID_ADDRESS)
    assert result["classification"] == "hybrid"
    assert result["is_hybrid"] is True


def test_classify_address_unstructured():
    """Free-form lines only classify as unstructured."""
    result = server.classify_address(_UNSTRUCTURED_ADDRESS)
    assert result["classification"] == "unstructured"
    assert result["is_unstructured"] is True


def test_classify_address_bad_country_returns_error():
    """An invalid ISO country code returns an error dict (ValueError path)."""
    result = server.classify_address({"twn_nm": "X", "ctry": "ZZ"})
    assert "error" in result


def test_classify_address_unknown_field_returns_error():
    """An unknown field returns an error dict (TypeError path)."""
    result = server.classify_address({"not_a_field": "x"})
    assert "error" in result


def test_validate_address_rejects_unstructured_under_cliff():
    """An unstructured address is blocked under the default cliff policy."""
    result = server.validate_address(_UNSTRUCTURED_ADDRESS)
    assert result["policy"] == "hybrid_or_structured"
    assert result["classification"] == "unstructured"
    assert result["is_acceptable"] is False
    assert result["findings"]
    finding = result["findings"][0]
    assert finding["severity"] == "block"
    assert "unstructured" in finding["message"].lower()


def test_validate_address_accepts_structured():
    """A structured address is acceptable with no findings."""
    result = server.validate_address(_STRUCTURED_ADDRESS)
    assert result["is_acceptable"] is True
    assert result["findings"] == []


def test_validate_address_unstructured_ok_policy_accepts():
    """The permissive policy accepts an unstructured address."""
    result = server.validate_address(
        _UNSTRUCTURED_ADDRESS, policy="unstructured_ok"
    )
    assert result["is_acceptable"] is True
    assert result["findings"] == []


def test_validate_address_invalid_policy_returns_error():
    """An unknown policy returns an error dict, not an exception."""
    result = server.validate_address(_STRUCTURED_ADDRESS, policy="nope")
    assert "error" in result


def test_validate_address_bad_address_returns_error():
    """A malformed address returns an error dict (build failure path)."""
    result = server.validate_address({"ctry": "ZZ"})
    assert "error" in result


def test_repair_address_upgrades_unstructured_to_hybrid():
    """Legacy GB lines are repaired into a hybrid address."""
    result = server.repair_address(
        ["10 Downing Street", "London", "SW1A 2AA"], "GB"
    )
    assert result["classification"] == "hybrid"
    assert result["is_hybrid"] is True
    assert result["is_structured"] is False
    addr = result["address"]
    assert addr["twn_nm"] == "London"
    assert addr["pst_cd"] == "SW1A 2AA"
    assert addr["ctry"] == "GB"
    assert isinstance(addr["adr_line"], list)
    assert "10 Downing Street" in addr["adr_line"]


def test_repair_address_bad_country_returns_error():
    """An invalid country hint returns an error dict."""
    result = server.repair_address(["1 High Street"], "ZZ")
    assert "error" in result


def test_validate_addresses_flags_unstructured_row():
    """A payment row with an unstructured debtor address is flagged."""
    rows = [
        {
            "debtor_address_adr_line_0": "1 High Street",
            "debtor_address_adr_line_1": "London",
        }
    ]
    result = server.validate_addresses(rows)
    assert result["policy"] == "hybrid_or_structured"
    assert result["is_valid"] is False
    assert result["total"] == 1
    err = result["errors"][0]
    assert err["row"] == 0
    assert err["party"] == "debtor"
    assert err["severity"] == "block"
    assert err["classification"] == "unstructured"


def test_validate_addresses_clean_batch():
    """A row with a structured creditor address passes validation."""
    rows = [
        {
            "creditor_address_strt_nm": "High Street",
            "creditor_address_bldg_nb": "1",
            "creditor_address_twn_nm": "London",
            "creditor_address_ctry": "GB",
        }
    ]
    result = server.validate_addresses(rows)
    assert result["is_valid"] is True
    assert result["total"] == 1
    assert result["errors"] == []


def test_validate_addresses_invalid_policy_returns_error():
    """An unknown policy returns an error dict, not an exception."""
    result = server.validate_addresses([{}], policy="nope")
    assert "error" in result


# ---------------------------------------------------------------------------
# main + dispatch
# ---------------------------------------------------------------------------


def test_main_runs_the_server(monkeypatch):
    """``main`` delegates to the FastMCP server's ``run`` over stdio."""
    calls = []
    monkeypatch.setattr(server.server, "run", lambda: calls.append(True))
    server.main()
    assert calls == [True]


def test_call_tool_through_fastmcp():
    """Tools are invocable through the FastMCP dispatch layer."""

    async def go():
        result = await server.server.call_tool("list_schemes", {})
        block = result[0] if isinstance(result, list | tuple) else result
        text = getattr(block, "text", None)
        if text is None and isinstance(result, tuple):
            text = json.dumps(result[1])
        return json.loads(text)

    payload = asyncio.run(go())
    # FastMCP wraps a bare list return under a "result" key.
    schemes = payload["result"] if isinstance(payload, dict) else payload
    assert any(s["scheme"] == "cbpr_plus" for s in schemes)
