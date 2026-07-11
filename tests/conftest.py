"""Shared fixtures for the pacs008-mcp test suite."""

import pytest

# A minimal, fully valid pacs.008 payment record. The field set is derived from
# the pacs008 library's own generation tests (tests/test_generate_xml.py) and
# satisfies the pacs.008.001.08 input JSON Schema and XSD.
_RECORD = {
    "msg_id": "MSG001",
    "creation_date_time": "2026-01-15T10:30:00",
    "nb_of_txs": 1,
    "settlement_method": "CLRG",
    "interbank_settlement_date": "2026-01-15",
    "end_to_end_id": "E2E001",
    "tx_id": "TX001",
    "interbank_settlement_amount": 1000.00,
    "interbank_settlement_currency": "EUR",
    "charge_bearer": "SHAR",
    "debtor_name": "Debtor Corp",
    "debtor_account_iban": "DE89370400440532013000",
    "debtor_agent_bic": "DEUTDEFF",
    "creditor_agent_bic": "COBADEFF",
    "creditor_name": "Creditor Ltd",
    "creditor_account_iban": "GB29NWBK60161331926819",
    "remittance_information": "Invoice 12345",
    "uetr": "7a562c67-ca16-48ba-b074-65581be6f001",
}


@pytest.fixture
def sample_record() -> dict:
    """A complete, schema- and XSD-valid pacs.008 payment record."""
    return dict(_RECORD)
