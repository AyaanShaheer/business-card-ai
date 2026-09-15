from pydantic import ValidationError
import pytest

from packages.schemas import Lead


def test_valid_qwen_response_is_accepted() -> None:
    payload = {
        "first_name": "Ayaan",
        "last_name": "Shaheer",
        "job_title": "MLOps Engineer",
        "company": "Royal Cloud Consultancy",
        "location": "Dubai, United Arab Emirates",
        "phone_number": "+971 50 123 4567",
        "email_address": "ayaan@example.com",
    }

    lead = Lead.model_validate(payload)

    assert lead.first_name == "Ayaan"
    assert lead.last_name == "Shaheer"
    assert lead.email_address == "ayaan@example.com"


def test_missing_optional_fields_are_allowed() -> None:
    payload = {
        "first_name": "Ayaan",
        "last_name": "Shaheer",
        "job_title": None,
        "company": None,
        "location": None,
        "phone_number": None,
        "email_address": None,
    }

    lead = Lead.model_validate(payload)

    assert lead.first_name == "Ayaan"
    assert lead.company is None


def test_invalid_email_is_rejected() -> None:
    payload = {
        "first_name": "Ayaan",
        "last_name": "Shaheer",
        "email_address": "not-an-email",
    }

    with pytest.raises(ValidationError):
        Lead.model_validate(payload)


def test_unexpected_field_is_rejected() -> None:
    payload = {
        "first_name": "Ayaan",
        "last_name": "Shaheer",
        "email_address": "ayaan@example.com",
        "extra_field": "unexpected",
    }

    with pytest.raises(ValidationError):
        Lead.model_validate(payload)