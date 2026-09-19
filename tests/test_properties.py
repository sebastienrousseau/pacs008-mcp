"""Property-based tests over the invariants the tool handlers own.

The example-based tests pin specific inputs. These state what has to hold
for *any* input a tool's schema admits: an error envelope always carries
a non-empty ``error`` string, every result is JSON-serialisable (it has
to cross the wire), and the summary fields of a report agree with its
detail rows. Hypothesis is deterministic here (see ``conftest.py``), so a
failing example reproduces on the next run.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pacs008_mcp.server as server

MSG_TYPE = "pacs.008.001.08"

# Plain letters, digits and spaces: enough to exercise the handlers'
# logic without tripping the library's character-set rules, which are
# its own concern and tested in its own repository.
_WORDS = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "
    ),
    min_size=1,
    max_size=30,
)
_COUNTRIES = st.sampled_from(["GB", "DE", "FR", "US", "JP", "BE", "NL"])
_ADDRESS_FIELDS = ("strt_nm", "bldg_nb", "pst_cd", "twn_nm", "ctry")
_PARTIES = ("debtor", "creditor", "debtor_agent", "creditor_agent")

#: A PostalAddress27 dict with any subset of fields present, so the
#: strategy reaches structured, hybrid, unstructured and invalid forms.
_ADDRESSES = st.fixed_dictionaries(
    {},
    optional={
        "strt_nm": _WORDS,
        "bldg_nb": st.text(alphabet="0123456789", min_size=1, max_size=4),
        "pst_cd": _WORDS,
        "twn_nm": _WORDS,
        "ctry": _COUNTRIES,
        "adr_line": st.lists(_WORDS, max_size=3),
    },
)

#: Payment rows whose address columns follow the ``{party}_address_{field}``
#: convention the batch validator scans for.
_ADDRESS_ROWS = st.lists(
    st.dictionaries(
        keys=st.tuples(
            st.sampled_from(_PARTIES), st.sampled_from(_ADDRESS_FIELDS)
        ).map(lambda pair: f"{pair[0]}_address_{pair[1]}"),
        values=_WORDS,
        max_size=6,
    ),
    max_size=4,
)

_BASE_RECORD = {
    "msg_id": "MSG001",
    "creation_date_time": "2026-01-15T10:30:00",
    "nb_of_txs": 1,
    "settlement_method": "CLRG",
    "end_to_end_id": "E2E001",
    "interbank_settlement_amount": 1000.00,
    "interbank_settlement_currency": "EUR",
    "charge_bearer": "SHAR",
    "debtor_name": "Debtor Corp",
    "debtor_agent_bic": "DEUTDEFF",
    "creditor_agent_bic": "COBADEFF",
    "creditor_name": "Creditor Ltd",
}


@st.composite
def _records(draw: st.DrawFn) -> list[dict]:
    """Valid records with some fields dropped or overwritten at random."""
    count = draw(st.integers(min_value=0, max_value=3))
    records = []
    for _ in range(count):
        record = dict(_BASE_RECORD)
        for key in draw(st.sets(st.sampled_from(sorted(_BASE_RECORD)))):
            if draw(st.booleans()):
                del record[key]
            else:
                record[key] = draw(st.one_of(_WORDS, st.integers()))
        records.append(record)
    return records


@st.composite
def _bics(draw: st.DrawFn) -> tuple[str, str]:
    """A structurally valid BIC and a noisy spelling of it.

    Returns ``(clean, noisy)``: ``noisy`` carries random case and
    spaces/hyphens the tool promises to strip.
    """
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    bank = draw(st.text(alphabet=letters, min_size=4, max_size=4))
    country = draw(_COUNTRIES)
    location = draw(st.text(alphabet=letters, min_size=2, max_size=2))
    branch = draw(st.sampled_from(["", "XXX", "500", "ABC"]))
    clean = f"{bank}{country}{location}{branch}"
    noisy = "".join(ch.lower() if draw(st.booleans()) else ch for ch in clean)
    for sep in draw(st.lists(st.sampled_from([" ", "-"]), max_size=2)):
        at = draw(st.integers(min_value=0, max_value=len(noisy)))
        noisy = noisy[:at] + sep + noisy[at:]
    return clean, noisy


@pytest.fixture(scope="module", autouse=True)
def _no_directory_endpoint():
    """Keep the BIC lookup offline for every example Hypothesis draws."""
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv(server._BIC_DIRECTORY_URL_ENV, raising=False)
        yield


def _is_error(result: dict) -> bool:
    """True for an error envelope, asserting it is well-formed."""
    if "error" not in result:
        return False
    assert isinstance(result["error"], str) and result["error"]
    return True


@given(st.text(min_size=1))
def test_message_type_name_is_identity_outside_known_families(
    message_type: str,
) -> None:
    """A type outside the family table names itself; inside it, the table."""
    family = ".".join(message_type.split(".")[:2])
    expected = server._FAMILY_NAMES.get(family, message_type)
    assert server._message_type_name(message_type) == expected


@given(st.sampled_from(sorted(server._FAMILY_NAMES)), st.integers(1, 99))
def test_message_type_name_resolves_every_family(
    family: str, version: int
) -> None:
    """Every family in the table resolves for any variant number."""
    assert (
        server._message_type_name(f"{family}.001.{version:02d}")
        == server._FAMILY_NAMES[family]
    )


@given(_ADDRESSES)
def test_classify_address_flags_agree_with_classification(
    address: dict,
) -> None:
    """Exactly one of the three flags is set, and it names the class."""
    result = server.classify_address(address)
    json.dumps(result)
    if _is_error(result):
        return
    flags = {
        "structured": result["is_structured"],
        "hybrid": result["is_hybrid"],
        "unstructured": result["is_unstructured"],
    }
    assert sum(flags.values()) == 1
    assert flags[result["classification"]] is True


@given(_ADDRESSES, st.sampled_from(server._ADDRESS_POLICY_VALUES))
def test_validate_address_is_acceptable_iff_no_findings(
    address: dict, policy: str
) -> None:
    """The verdict, the findings and the classification agree."""
    result = server.validate_address(address, policy)
    json.dumps(result)
    if _is_error(result):
        return
    assert result["policy"] == policy
    assert result["is_acceptable"] == (result["findings"] == [])
    classified = server.classify_address(address)
    assert result["classification"] == classified["classification"]
    if policy == "unstructured_ok":
        assert result["is_acceptable"] is True


@given(st.lists(_WORDS, max_size=4), _COUNTRIES)
def test_repair_address_round_trips_through_classify(
    lines: list[str], country: str
) -> None:
    """A repaired address is itself a valid input to ``classify_address``."""
    result = server.repair_address(lines, country)
    json.dumps(result)
    if _is_error(result):
        return
    again = server.classify_address(result["address"])
    assert again["classification"] == result["classification"]
    assert again["is_structured"] == result["is_structured"]
    assert again["is_hybrid"] == result["is_hybrid"]


@given(_ADDRESS_ROWS, st.sampled_from(server._ADDRESS_POLICY_VALUES))
def test_validate_addresses_summary_agrees_with_rows(
    rows: list[dict], policy: str
) -> None:
    """``total`` counts the rows, ``is_valid`` is ``errors == []``.

    A row whose column breaks a field rule is an error envelope, never
    an exception; the property found the handler letting one escape.
    """
    result = server.validate_addresses(rows, policy)
    json.dumps(result)
    if _is_error(result):
        return
    assert result["policy"] == policy
    assert result["total"] == len(rows)
    assert result["is_valid"] == (result["errors"] == [])
    for error in result["errors"]:
        assert 0 <= error["row"] < len(rows)
        assert error["party"] in _PARTIES
        assert error["message"]


@given(_records())
def test_validate_records_summary_agrees_with_rows(
    records: list[dict],
) -> None:
    """``valid`` is the number of rows without an error, never more."""
    result = server.validate_records(MSG_TYPE, records)
    json.dumps(result)
    assert not _is_error(result)
    assert result["total"] == len(records)
    assert result["is_valid"] == (result["errors"] == [])
    failing_rows = {error["row"] for error in result["errors"]}
    assert result["valid"] == len(records) - len(failing_rows)
    for error in result["errors"]:
        assert 0 <= error["row"] < len(records)
        assert error["message"]


@given(_bics())
def test_verify_bic_online_normalises_and_splits_the_code(
    bic: tuple[str, str],
) -> None:
    """Noise is stripped, the parts re-join to the code, nothing is invented."""
    clean, noisy = bic
    result = server.verify_bic_online(noisy)
    json.dumps(result)
    assert result["is_structurally_valid"] is True
    assert result["bic"] == clean
    assert result["length"] == len(clean) in (8, 11)
    parts = (
        result["bank_code"],
        result["country_code"],
        result["location_code"],
        result["branch_code"] or "",
    )
    assert "".join(parts) == clean
    assert (result["branch_code"] is None) == (len(clean) == 8)
    assert result["directory"] is None
    assert "note" in result and "error" not in result


@given(st.text(max_size=60))
def test_build_prompt_echoes_the_goal_iff_it_is_not_blank(goal: str) -> None:
    """The task line appears exactly when the goal has content."""
    out = server.build_pacs008_message(goal)
    assert ("The task is" in out) == bool(goal.strip())
    if goal.strip():
        assert goal.strip() in out
    for fragment in (
        "list_message_types(",
        "validate_records(",
        "validate_scheme(",
        "generate_message(",
    ):
        assert fragment in out


@given(st.one_of(st.sampled_from(server._SCHEME_VALUES), _WORDS))
def test_scheme_resource_round_trips_get_scheme(scheme: str) -> None:
    """The resource is the tool's payload after a JSON round trip."""
    payload = server.get_scheme(scheme)
    assert json.loads(server.scheme_resource(scheme)) == payload
    if _is_error(payload):
        assert scheme not in server._SCHEME_VALUES
    else:
        assert payload["scheme"] == scheme
        assert set(payload["allowed_charge_bearers"]) <= {
            "CRED",
            "DEBT",
            "SHAR",
            "SLEV",
        }
