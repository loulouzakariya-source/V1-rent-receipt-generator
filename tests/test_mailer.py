from io import BytesIO

import pytest

from rent_receipt_generator.mailer import build_message, validate_email


class InMemoryPdf:
    suffix = ".pdf"
    name = "receipt.pdf"

    def exists(self):
        return True

    def open(self, mode):
        return BytesIO(b"%PDF-1.4\n% test pdf\n")


def test_validate_email_accepts_simple_valid_address():
    assert validate_email(" owner@example.com ") == "owner@example.com"


def test_validate_email_rejects_obvious_invalid_address():
    with pytest.raises(ValueError, match="Adresse email invalide"):
        validate_email("not-an-email")


def test_build_message_sets_body_headers_and_pdf_attachment():
    message = build_message(
        sender="owner@example.com",
        recipient="tenant@example.com",
        tenant_first_name="Jane",
        month_label="juillet 2026",
        pdf_path=InMemoryPdf(),
        signature="Owner Test",
    )

    assert message["From"] == "owner@example.com"
    assert message["To"] == "tenant@example.com"
    assert message["Subject"] == "Quittance de loyer - juillet 2026"

    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "Bonjour Jane" in body
    assert "juillet 2026" in body
    assert "Owner Test" in body

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "receipt.pdf"
    assert attachments[0].get_content_type() == "application/pdf"
