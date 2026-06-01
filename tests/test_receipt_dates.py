import pytest

from rent_receipt_generator.receipts import receipt_dates


def test_receipt_dates_for_30_day_month():
    dates = receipt_dates(6, 2026)

    assert dates["date_mois_et_annee"] == "juin 2026"
    assert dates["date_premier_jour_du_mois"] == "01/06/2026"
    assert dates["date_dernier_jour_du_mois"] == "30/06/2026"
    assert dates["date_paiement"] == "05/06/2026"


def test_receipt_dates_for_31_day_month():
    dates = receipt_dates(7, 2026)

    assert dates["date_mois_et_annee"] == "juillet 2026"
    assert dates["date_dernier_jour_du_mois"] == "31/07/2026"


def test_receipt_dates_for_leap_year_february():
    dates = receipt_dates(2, 2024)

    assert dates["date_mois_et_annee"] == "fevrier 2024"
    assert dates["date_dernier_jour_du_mois"] == "29/02/2024"


def test_receipt_dates_for_non_leap_year_february():
    dates = receipt_dates(2, 2025)

    assert dates["date_dernier_jour_du_mois"] == "28/02/2025"


def test_receipt_dates_rejects_invalid_month():
    with pytest.raises(ValueError, match="mois"):
        receipt_dates(13, 2026)
