import sqlite3
from uuid import uuid4

import pytest

from rent_receipt_generator.db import (
    active_tenants_with_apartments,
    add_apartment,
    add_tenant,
    get_owner_settings,
    init_db,
    list_apartments,
    list_tenants,
    set_tenant_active,
    update_owner_settings,
)


@pytest.fixture()
def db_path():
    uri = f"file:rent_receipt_generator_test_{uuid4().hex}?mode=memory&cache=shared"
    anchor = sqlite3.connect(uri, uri=True)
    try:
        yield uri
    finally:
        anchor.close()


def test_database_stores_apartments_tenants_and_owner_settings(db_path):
    init_db(db_path)
    update_owner_settings("Owner Test", "owner@example.com", db_path)
    add_apartment("Apartment A", "1 Test Street", 500, 50, db_path)
    add_tenant("Jane", "Doe", "Madame", "jane@example.com", 1, db_path)

    owner = get_owner_settings(db_path)
    apartments = list_apartments(db_path)
    tenants = list_tenants(db_path)
    active_rows = active_tenants_with_apartments(db_path)

    assert owner["bailleur_nom"] == "Owner Test"
    assert owner["bailleur_email"] == "owner@example.com"
    assert apartments[0]["loyer_total"] == 550
    assert tenants[0]["civilite"] == "Madame"
    assert tenants[0]["apartment_id"] == 1
    assert active_rows[0]["appartement_adresse"] == "1 Test Street"


def test_add_tenant_rejects_unknown_apartment(db_path):
    init_db(db_path)

    with pytest.raises(ValueError, match="Appartement introuvable"):
        add_tenant("John", "Doe", "Monsieur", "john@example.com", 99, db_path)


def test_tenant_can_be_deactivated_without_deleting_record(db_path):
    init_db(db_path)
    add_apartment("Apartment A", "1 Test Street", 500, 50, db_path)
    add_tenant("Jane", "Doe", "Madame", "jane@example.com", 1, db_path)

    set_tenant_active(1, False, db_path)

    assert list_tenants(db_path)[0]["active"] == 0
    assert active_tenants_with_apartments(db_path) == []
