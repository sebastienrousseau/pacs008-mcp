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

"""Model Context Protocol (MCP) server for Pacs008.

This server exposes the Pacs008 library's ISO 20022 ``pacs.008`` (FI-to-FI
Customer Credit Transfer) capabilities as MCP tools so that any MCP-compatible
client (Claude Desktop, IDEs, agents) can discover message types and scheme
profiles, validate records against the JSON Schema and against a rail's usage
guidelines, generate validated XML, validate raw XML against the bundled XSD,
and parse inbound ISO 20022 messages.

Every tool is a thin, typed wrapper over the ``pacs008`` library -- the same
package used by the CLI and REST API -- so all interfaces behave identically.
Tools return JSON-serializable data (dicts, lists, or strings); on a
:class:`ValueError` they return an ``{"error": ...}`` payload rather than
raising.

Launching the server:
    * As a console script::

        pacs008-mcp

    * Programmatically::

        from pacs008_mcp.server import main
        main()

    * In an MCP client config (e.g. Claude Desktop ``claude_desktop_config.json``)::

        {
          "mcpServers": {
            "pacs008": {
              "command": "pacs008-mcp"
            }
          }
        }

The server communicates over stdio (FastMCP's default transport).
"""

import dataclasses
import json
import os
import shutil
import tempfile
from importlib.resources import files
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pacs008.constants import valid_xml_types
from pacs008.profiles import get_profile, list_profiles
from pacs008.standards.address import (
    AddressPolicy,
    PostalAddress,
    Severity,
    from_unstructured,
)
from pacs008.standards.address import (
    validate_addresses as _lib_validate_addresses,
)
from pacs008.validation.schema_validator import SchemaValidator
from pacs008.xml.generate_xml import generate_xml_string
from pacs008.xml.parser import parse
from pacs008.xml.validate_via_xsd import validate_xml_string_via_xsd
from pydantic import Field

from pacs008_mcp import __version__

server = FastMCP("pacs008")
# FastMCP does not expose a version kwarg; without this override the
# MCP SDK's own version leaks into serverInfo.version, breaking
# manifest/runtime coherence checks (e.g. Glama scoring).
server._mcp_server.version = __version__

# Shared MCP tool annotations. Every tool in this server is a pure,
# side-effect-free reader over the pacs008 library: each tool computes solely
# from its arguments and the JSON Schemas / XSD templates bundled with the
# pacs008 library. None opens a caller-supplied filesystem path or reaches an
# external system, so all are marked ``readOnlyHint`` + ``idempotentHint``,
# never ``destructiveHint``, and closed-world (``openWorldHint=False``).
#
# These hints let MCP clients (and the Glama quality grader) reason about
# safety, caching, and auto-approval without executing the tool.
_PURE_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

# Human-readable names for each ISO 20022 message family, sourced verbatim from
# the pacs008 library's own generator docstrings (pacs008.xml.generate_xml).
_FAMILY_NAMES: dict[str, str] = {
    "pacs.002": "FI to FI Payment Status Report",
    "pacs.003": "FI to FI Customer Direct Debit",
    "pacs.004": "Payment Return",
    "pacs.007": "FI to FI Payment Reversal",
    "pacs.008": "FI to FI Customer Credit Transfer",
    "pacs.009": "Financial Institution Credit Transfer",
    "pacs.010": "Financial Institution Direct Debit",
    "pacs.028": "FI to FI Payment Status Request",
}


def _message_type_name(message_type: str) -> str:
    """Return the human name for a message type from its family prefix."""
    family = ".".join(message_type.split(".")[:2])
    return _FAMILY_NAMES.get(family, message_type)


# The pacs008 library's ``validate_path`` guard (invoked by
# ``generate_xml_string``) only permits paths under the current working
# directory or a system temp directory. The bundled templates live inside the
# installed package -- outside the CWD when the server is launched from
# anywhere else -- so we stage each message type's ``template.xml`` + ``.xsd``
# into a per-process temp directory (an allowed base) once and reuse them.
_STAGE_DIR = tempfile.mkdtemp(prefix="pacs008mcp-")
_STAGED: dict[str, tuple[str, str]] = {}


def _resolve_template_paths(message_type: str) -> tuple[str, str]:
    """Return staged (template.xml, xsd) paths for a message type.

    The bundled files are resolved from the *installed* ``pacs008`` package via
    :func:`importlib.resources.files` and copied into a temp directory the
    library's path guard accepts, so the server works no matter what directory
    it is launched from. Results are cached per message type.
    """
    cached = _STAGED.get(message_type)
    if cached is not None:
        return cached

    src = files("pacs008") / "templates" / message_type
    dest = os.path.join(_STAGE_DIR, message_type)
    os.makedirs(dest, exist_ok=True)
    template_path = shutil.copy(
        str(src / "template.xml"), os.path.join(dest, "template.xml")
    )
    xsd_path = shutil.copy(
        str(src / f"{message_type}.xsd"),
        os.path.join(dest, f"{message_type}.xsd"),
    )
    _STAGED[message_type] = (template_path, xsd_path)
    return template_path, xsd_path


# ---------------------------------------------------------------------------
# Closed-set parameter enums.
#
# Every value below is derived from the pacs008 library's own source-of-truth
# constants / registry (never hardcoded here), so the accepted set stays in
# lockstep with the backend. The ``enum`` is JSON Schema metadata only -- it
# lets MCP clients constrain/auto-complete inputs -- while the library
# continues to enforce these values at runtime.
# ---------------------------------------------------------------------------
_MESSAGE_TYPE_VALUES: list[str] = sorted(valid_xml_types)
_MESSAGE_TYPE_LIST = ", ".join(f"'{v}'" for v in _MESSAGE_TYPE_VALUES)

_MessageType = Annotated[
    str,
    Field(
        description=(
            "A supported ISO 20022 pacs message type, e.g. 'pacs.008.001.08' "
            "FI-to-FI Customer Credit Transfer. Must be exactly one of: "
            f"{_MESSAGE_TYPE_LIST} (see list_message_types)."
        ),
        json_schema_extra={"enum": _MESSAGE_TYPE_VALUES},
    ),
]

_SCHEME_VALUES: list[str] = sorted(list_profiles())
_SCHEME_LIST = ", ".join(f"'{v}'" for v in _SCHEME_VALUES)

_Scheme = Annotated[
    str,
    Field(
        description=(
            "A registered scheme / usage-guideline profile name "
            "(case-insensitive), e.g. 'cbpr_plus', 'fedwire', 'chaps'. Must be "
            f"one of: {_SCHEME_LIST} (see list_schemes)."
        ),
        json_schema_extra={"enum": _SCHEME_VALUES},
    ),
]

# Address validation policy, derived from the pacs008 library's own
# ``AddressPolicy`` enum (source of truth). ``hybrid_or_structured`` is the
# November 14, 2026 cliff default: it rejects fully unstructured postal
# addresses across SWIFT CBPR+, HVPS+, T2 RTGS, CHAPS, Fedwire and Lynx.
_ADDRESS_POLICY_VALUES: list[str] = [policy.value for policy in AddressPolicy]
_ADDRESS_POLICY_LIST = ", ".join(f"'{v}'" for v in _ADDRESS_POLICY_VALUES)
_DEFAULT_ADDRESS_POLICY: str = AddressPolicy.HYBRID_OR_STRUCTURED.value

_AddressPolicy = Annotated[
    str,
    Field(
        description=(
            "Postal-address validation policy. 'unstructured_ok' permits any "
            "form (pre-cliff / generic); 'hybrid_or_structured' rejects fully "
            "unstructured addresses (the SWIFT CBPR+ UG2026 default in force "
            "from 14 November 2026); 'structured_only' requires full "
            f"structured form. Must be one of: {_ADDRESS_POLICY_LIST}."
        ),
        json_schema_extra={"enum": _ADDRESS_POLICY_VALUES},
    ),
]


def _build_address(address: dict) -> PostalAddress:
    """Construct a ``PostalAddress`` from a snake_case field dict.

    Raises ``ValueError``/``TypeError`` (e.g. bad country code, over-length
    field, or an unknown key) which callers translate to an error payload.
    """
    return PostalAddress(**address)


def _address_to_dict(address: PostalAddress) -> dict[str, Any]:
    """Serialize a ``PostalAddress`` to a JSON-friendly dict.

    ``adr_line`` (a tuple on the frozen dataclass) is emitted as a list.
    """
    data = dataclasses.asdict(address)
    data["adr_line"] = list(data["adr_line"])
    return data


@server.tool(title="List pacs message types", annotations=_PURE_READ)
def list_message_types() -> list[dict]:
    """List every supported ISO 20022 pacs message type and its human name.

    Use this first, before any generation or validation call, to discover the
    exact ``message_type`` strings this server accepts (e.g.
    ``pacs.008.001.08`` FI-to-FI Customer Credit Transfer). To learn a type's
    required fields or full schema, call ``get_required_fields`` or
    ``get_input_schema`` instead.

    Returns a list of ``{"message_type": ..., "name": ...}`` dictionaries, one
    per supported message type.
    """
    return [
        {"message_type": mt, "name": _message_type_name(mt)}
        for mt in _MESSAGE_TYPE_VALUES
    ]


@server.tool(title="List scheme profiles", annotations=_PURE_READ)
def list_schemes() -> list[dict]:
    """List every registered scheme / usage-guideline profile.

    Scheme profiles (CBPR+, HVPS+, Fedwire, CHAPS, T2 RTGS, SCT Inst, generic)
    layer rail-specific rules on top of base ISO 20022. Use this to discover
    the ``scheme`` names accepted by ``get_scheme`` and ``validate_scheme``.

    Registry aliases (e.g. ``cbpr+``, ``cbprplus``) collapse to their canonical
    profile, so each profile appears exactly once. Returns a list of
    ``{"scheme": ..., "name": ...}`` dictionaries.
    """
    canonical = {get_profile(name).name for name in _SCHEME_VALUES}
    return [{"scheme": name, "name": name} for name in sorted(canonical)]


@server.tool(title="Get scheme profile rules", annotations=_PURE_READ)
def get_scheme(scheme: _Scheme) -> dict:
    """Return the rule attributes of a scheme / usage-guideline profile.

    Use this to inspect a rail's constraints -- whether the UETR is mandatory,
    the permitted charge bearers, remittance-info length cap, per-message
    transaction cardinality, pinned message versions, and which parties must
    carry an LEI -- before assembling or validating a batch.

    Args:
        scheme: A registered scheme profile name (see ``list_schemes``).
    """
    try:
        profile = get_profile(scheme)
        return {
            "scheme": scheme,
            "name": profile.name,
            "mr_version": profile.mr_version,
            "uetr_required": profile.uetr_required,
            "max_remit_info_len": profile.max_remit_info_len,
            "allowed_charge_bearers": sorted(profile.allowed_charge_bearers),
            "max_transactions_per_msg": profile.max_transactions_per_msg,
            "lei_required_for": list(profile.lei_required_for()),
            "pinned_versions": profile.pinned_versions(),
        }
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(title="Get required fields", annotations=_PURE_READ)
def get_required_fields(
    message_type: _MessageType,
) -> list[str]:
    """List only the required input field names for a pacs message type.

    Use this for a quick checklist of the mandatory columns before building
    payment records. For full type/format constraints (not just which fields
    are required), call ``get_input_schema`` instead.

    Args:
        message_type: A supported ISO 20022 pacs message type.
    """
    try:
        return SchemaValidator(message_type).get_required_fields()
    except ValueError as exc:
        return [f"error: {exc}"]


@server.tool(title="Get input JSON Schema", annotations=_PURE_READ)
def get_input_schema(
    message_type: _MessageType,
) -> dict:
    """Return the full JSON Schema for a message type's flat input record.

    Use this to learn every field, its type, and its constraints before
    assembling records, or to drive a form/UI. For just the required-field
    names use ``get_required_fields``; to check records against this schema use
    ``validate_records``.

    Args:
        message_type: A supported ISO 20022 pacs message type.
    """
    try:
        return dict(SchemaValidator(message_type).schema)
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(title="Validate records against schema", annotations=_PURE_READ)
def validate_records(
    message_type: _MessageType,
    records: Annotated[
        list[dict],
        Field(
            description=(
                "One or more flat payment records, each a dict of field name "
                "-> value; validated against the message type's input JSON "
                "Schema (see get_input_schema / get_required_fields)."
            )
        ),
    ],
) -> dict:
    """Validate flat payment records against a message type's JSON Schema.

    Use this before ``generate_message`` to catch structural/type errors per
    record and get a row-by-row error report. This checks JSON-Schema shape
    only; to check a batch against a rail's usage guidelines use
    ``validate_scheme``.

    Returns a report ``{"is_valid": bool, "total": int, "valid": int,
    "errors": [...]}``.

    Args:
        message_type: A supported ISO 20022 pacs message type.
        records: One or more flat payment records to validate.
    """
    try:
        validator = SchemaValidator(message_type)
    except ValueError as exc:
        return {"error": str(exc)}

    total, valid, errors = validator.validate_batch(records)
    report_errors = [
        {
            "row": row_idx,
            "field": err.path,
            "message": err.message,
            "value": err.value,
        }
        for row_idx, row_errors in errors
        for err in row_errors
    ]
    return {
        "is_valid": not report_errors,
        "total": total,
        "valid": valid,
        "errors": report_errors,
    }


@server.tool(title="Validate records against a scheme", annotations=_PURE_READ)
def validate_scheme(
    scheme: _Scheme,
    records: Annotated[
        list[dict],
        Field(
            description=(
                "One or more flat payment records, each a dict of field name "
                "-> value; checked against the scheme's usage-guideline "
                "business rules (charge bearer, UETR, remittance length, "
                "per-message cardinality)."
            )
        ),
    ],
) -> dict:
    """Validate payment records against a scheme's usage-guideline rules.

    Use this to check a batch against a rail's rulebook (CBPR+, HVPS+,
    Fedwire, CHAPS, T2 RTGS, SCT Inst) -- charge-bearer restrictions, UETR
    presence, remittance-info length, and per-message transaction cardinality.
    This is complementary to ``validate_records`` (JSON-Schema shape).

    Returns ``{"scheme": str, "is_valid": bool, "total": int,
    "violations": [...]}``.

    Args:
        scheme: A registered scheme profile name (see ``list_schemes``).
        records: One or more flat payment records to check.
    """
    try:
        profile = get_profile(scheme)
    except ValueError as exc:
        return {"error": str(exc)}

    violations = profile.validate_business_rules(records)
    return {
        "scheme": scheme,
        "is_valid": not violations,
        "total": len(records),
        "violations": [dataclasses.asdict(v) for v in violations],
    }


@server.tool(title="Generate pacs XML from records", annotations=_PURE_READ)
def generate_message(
    message_type: _MessageType,
    records: Annotated[
        list[dict],
        Field(
            description=(
                "One or more flat payment records, each a dict of field name "
                "-> value, from which the pacs XML is generated; run "
                "validate_records first to surface record-level errors."
            )
        ),
    ],
) -> str:
    """Generate a validated ISO 20022 pacs XML message from in-memory records.

    This is the primary generation tool: pass payment records you already hold
    in memory and receive an XSD-validated XML document; no file is written.
    Run ``validate_records`` first to surface record-level errors, and
    ``list_message_types`` to confirm the ``message_type`` string.

    Returns the validated XML document as a string, or an ``{"error": ...}``
    payload (serialized) if generation fails.

    Args:
        message_type: A supported ISO 20022 pacs message type.
        records: One or more flat payment records.
    """
    if message_type not in valid_xml_types:
        return json.dumps({"error": f"Invalid message type: {message_type}"})
    try:
        template_path, xsd_path = _resolve_template_paths(message_type)
        return generate_xml_string(
            records, message_type, template_path, xsd_path
        )
    except (ValueError, KeyError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})


@server.tool(title="Validate XML against XSD", annotations=_PURE_READ)
def validate_xml(
    message_type: _MessageType,
    xml: Annotated[
        str,
        Field(
            description=(
                "A raw ISO 20022 XML document to validate against the bundled "
                "XSD schema for the given message type."
            )
        ),
    ],
) -> dict:
    """Validate a raw XML string against a message type's bundled XSD.

    Use this to check an externally produced XML document against the official
    ISO 20022 schema. To generate a document that is already XSD-validated,
    use ``generate_message`` instead.

    Returns ``{"message_type": str, "is_valid": bool}``.

    Args:
        message_type: A supported ISO 20022 pacs message type.
        xml: The raw XML document to validate.
    """
    if message_type not in valid_xml_types:
        return {"error": f"Invalid message type: {message_type}"}
    _, xsd_path = _resolve_template_paths(message_type)
    return {
        "message_type": message_type,
        "is_valid": validate_xml_string_via_xsd(xml, xsd_path),
    }


@server.tool(title="Parse inbound ISO 20022 XML", annotations=_PURE_READ)
def parse_message(
    xml: Annotated[
        str,
        Field(
            description=(
                "A raw inbound ISO 20022 XML message (pacs.008 / pacs.002 / "
                "pacs.004, optionally BAH-envelope-wrapped) to classify."
            )
        ),
    ],
) -> dict:
    """Parse and classify an inbound ISO 20022 XML message.

    Use this on the receiving side to identify what a message is -- its
    ``msg_def_idr`` (e.g. ``pacs.002.001.10``), family, version, and any
    Business Application Header -- before processing it. Handles both bare
    ``Document`` messages and BAH-wrapped envelopes.

    Returns a dict with ``msg_def_idr``, ``msg_family``, ``version``,
    ``root_local_name``, ``namespace_uri``, ``envelope_wrapped`` and ``bah``.

    Args:
        xml: The raw inbound XML message.
    """
    try:
        parsed = parse(xml)
    except ValueError as exc:
        return {"error": str(exc)}

    bah: dict[str, Any] | None = (
        dataclasses.asdict(parsed.bah) if parsed.bah is not None else None
    )
    return {
        "msg_def_idr": parsed.msg_def_idr,
        "msg_family": parsed.msg_family,
        "version": parsed.version,
        "root_local_name": parsed.root_local_name,
        "namespace_uri": parsed.namespace_uri,
        "envelope_wrapped": parsed.envelope_wrapped,
        "bah": bah,
    }


# ---------------------------------------------------------------------------
# November 2026 structured-address cliff tools.
#
# On 14 November 2026, fully unstructured postal addresses are decommissioned
# across SWIFT CBPR+, HVPS+, T2 RTGS, CHAPS, Fedwire and Lynx: any high-value
# or cross-border payment carrying an unstructured-only address is rejected at
# the rail. These tools wrap the pacs008 library's ``standards.address`` module
# so agents can classify, validate and repair addresses ahead of the cliff.
# ---------------------------------------------------------------------------

_ADDRESS_DICT_FIELD = Annotated[
    dict,
    Field(
        description=(
            "An ISO 20022 PostalAddress27 as a dict of snake_case fields, e.g. "
            "{'strt_nm': 'High St', 'bldg_nb': '1', 'pst_cd': 'AB1 2CD', "
            "'twn_nm': 'London', 'ctry': 'GB'} and optional 'adr_line' (list "
            "of free-form lines). 'ctry' must be ISO 3166-1 alpha-2."
        )
    ),
]


@server.tool(title="Classify a postal address", annotations=_PURE_READ)
def classify_address(address: _ADDRESS_DICT_FIELD) -> dict:
    """Classify a postal address as structured, hybrid, or unstructured.

    Use this to see where an address stands against the 14 November 2026 SWIFT
    cliff: ``structured`` (town + country + structured detail, no free-form
    lines), ``hybrid`` (town + country + 1-2 free-form ``adr_line`` lines, the
    minimum CBPR+ UG2026 bar), or ``unstructured`` (free-form only — rejected
    from the cliff date). To check acceptability under a policy use
    ``validate_address``; to upgrade legacy lines use ``repair_address``.

    Returns ``{"classification": str, "is_structured": bool, "is_hybrid":
    bool, "is_unstructured": bool, "has_structured_fields": bool}`` or an
    ``{"error": ...}`` payload.

    Args:
        address: The postal address as a dict of snake_case fields.
    """
    try:
        addr = _build_address(address)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    return {
        "classification": addr.classify().value,
        "is_structured": addr.is_structured(),
        "is_hybrid": addr.is_hybrid(),
        "is_unstructured": addr.is_unstructured(),
        "has_structured_fields": addr.has_structured_fields,
    }


@server.tool(title="Validate a postal address", annotations=_PURE_READ)
def validate_address(
    address: _ADDRESS_DICT_FIELD,
    policy: _AddressPolicy = _DEFAULT_ADDRESS_POLICY,
) -> dict:
    """Validate one postal address against an address policy.

    Use this to decide whether an address will clear a rail. The default
    ``hybrid_or_structured`` policy is the November 14, 2026 cliff rule
    (SWIFT CBPR+, HVPS+, T2 RTGS, CHAPS, Fedwire, Lynx): it rejects fully
    unstructured addresses. Findings mirror the library's pipeline severity
    (a policy rejection is a blocking finding).

    Returns ``{"policy": str, "classification": str, "is_acceptable": bool,
    "findings": [{"severity": str, "message": str}, ...]}`` or an
    ``{"error": ...}`` payload.

    Args:
        address: The postal address as a dict of snake_case fields.
        policy: The validation policy to enforce (see the enum values).
    """
    try:
        resolved = AddressPolicy(policy)
    except ValueError:
        return {"error": f"Invalid policy: {policy!r}"}
    try:
        addr = _build_address(address)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}

    reason = addr.validate(resolved)
    findings = (
        [{"severity": Severity.BLOCK.value, "message": reason}]
        if reason is not None
        else []
    )
    return {
        "policy": resolved.value,
        "classification": addr.classify().value,
        "is_acceptable": reason is None,
        "findings": findings,
    }


@server.tool(title="Repair an unstructured address", annotations=_PURE_READ)
def repair_address(
    lines: Annotated[
        list[str],
        Field(
            description=(
                "Legacy unstructured address lines (free-form). Empty or "
                "whitespace-only lines are skipped."
            )
        ),
    ],
    country: Annotated[
        str,
        Field(
            description=(
                "ISO 3166-1 alpha-2 country code (e.g. 'GB', 'US', 'DE', "
                "'FR', 'JP') used to drive country-aware repair heuristics."
            )
        ),
    ],
) -> dict:
    """Upgrade legacy unstructured address lines toward hybrid/structured form.

    Experimental country-aware repair (``GB``, ``US``, ``DE``, ``FR``, ``JP``
    have dedicated heuristics; other countries get a best-effort pass promoting
    the last line to a town). Use this to lift pre-cliff data over the
    November 14, 2026 bar; audit the output before submitting, and keep both
    the original and derived address in your audit trail.

    Returns ``{"address": {...}, "classification": str, "is_structured":
    bool, "is_hybrid": bool}`` (so you can see the unstructured -> hybrid /
    structured upgrade) or an ``{"error": ...}`` payload.

    Args:
        lines: Legacy unstructured address lines.
        country: ISO 3166-1 alpha-2 country code driving the heuristics.
    """
    try:
        addr = from_unstructured(lines, country)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "address": _address_to_dict(addr),
        "classification": addr.classify().value,
        "is_structured": addr.is_structured(),
        "is_hybrid": addr.is_hybrid(),
    }


@server.tool(
    title="Validate addresses in payment rows", annotations=_PURE_READ
)
def validate_addresses(
    addresses: Annotated[
        list[dict],
        Field(
            description=(
                "Payment-row dicts. The pipeline scans each row for columns of "
                "the form '{party}_address_{field}' (party in debtor, creditor, "
                "debtor_agent, creditor_agent, ultimate_debtor, "
                "ultimate_creditor; field a snake_case PostalAddress field such "
                "as twn_nm/ctry/strt_nm or adr_line_0..adr_line_6) and "
                "validates each party's address."
            )
        ),
    ],
    policy: _AddressPolicy = _DEFAULT_ADDRESS_POLICY,
) -> dict:
    """Batch-validate every party address across a list of payment rows.

    Use this before ``generate_message`` to catch addresses that will be
    rejected at the rail. The default ``hybrid_or_structured`` policy enforces
    the November 14, 2026 cliff. Each finding is reported per offending
    ``(row, party)`` pair.

    Returns ``{"policy": str, "is_valid": bool, "total": int, "errors":
    [{"row": int, "party": str, "severity": str, "message": str,
    "classification": str}, ...]}`` or an ``{"error": ...}`` payload.

    Args:
        addresses: One or more payment-row dicts (see the field description).
        policy: The validation policy to enforce (see the enum values).
    """
    try:
        resolved = AddressPolicy(policy)
    except ValueError:
        return {"error": f"Invalid policy: {policy!r}"}

    errors = _lib_validate_addresses(addresses, resolved)
    return {
        "policy": resolved.value,
        "is_valid": not errors,
        "total": len(addresses),
        "errors": [
            {
                "row": err.row,
                "party": err.party,
                "severity": err.severity.value,
                "message": err.message,
                "classification": err.classification.value,
            }
            for err in errors
        ],
    }


def main() -> None:
    """Run the Pacs008 MCP server over stdio (the ``pacs008-mcp`` entry point)."""
    server.run()


if __name__ == "__main__":
    main()
