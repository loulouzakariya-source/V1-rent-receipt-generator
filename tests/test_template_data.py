import pytest

from rent_receipt_generator.receipts import build_template_data, safe_filename, validate_template_data


def tenant_row():
    return {
        "prenom": " Jane ",
        "nom": " Doe ",
        "civilite": "Madame",
        "email": "jane@example.com",
        "appartement_numero_code": "Apartment A",
        "appartement_adresse": "1 Test Street",
        "loyer_hors_charge": 500,
        "loyer_charges_uniquement": 50,
        "loyer_total": 550,
    }


def test_build_template_data_maps_all_expected_values():
    data = build_template_data(tenant_row(), 7, 2026, "Owner Test")

    assert data["locataire_prenom"] == "Jane"
    assert data["locataire_nom"] == "Doe"
    assert data["locataire_nom_prenom"] == "Jane Doe"
    assert data["bailleur_nom"] == "Owner Test"
    assert data["loyer_total"] == "550"
    assert data["date_mois_et_annee"] == "juillet 2026"


def test_validate_template_data_rejects_empty_required_values():
    data = build_template_data(tenant_row(), 7, 2026, "Owner Test")
    data["locataire_email"] = " "

    with pytest.raises(ValueError) as exc_info:
        validate_template_data(data)

    assert "locataire_email" in str(exc_info.value)


def test_safe_filename_removes_windows_forbidden_characters():
    filename = safe_filename('Quittance: Jane/Doe <2026>?')

    assert filename == "Quittance_ Jane_Doe _2026__"
