import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from .config import DATABASE_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS apartments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_code TEXT NOT NULL,
    adresse TEXT NOT NULL,
    loyer_hors_charge INTEGER NOT NULL,
    loyer_charges_uniquement INTEGER NOT NULL,
    UNIQUE(numero_code, adresse)
);

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prenom TEXT NOT NULL,
    nom TEXT NOT NULL,
    civilite TEXT NOT NULL DEFAULT 'Monsieur',
    email TEXT NOT NULL,
    apartment_id INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (apartment_id) REFERENCES apartments(id)
);

CREATE TABLE IF NOT EXISTS owner_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    bailleur_nom TEXT,
    bailleur_email TEXT
);
"""


def connect(db_path: Path | str = DATABASE_PATH) -> sqlite3.Connection:
    """Open the local SQLite database with useful row and foreign-key settings."""
    is_uri = isinstance(db_path, str) and db_path.startswith("file:")
    connection = sqlite3.connect(db_path, uri=is_uri)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def open_db(db_path: Path = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Open, commit, and close a SQLite connection reliably."""
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(db_path: Path = DATABASE_PATH) -> None:
    """Create or update the database structure without inserting private data."""
    with open_db(db_path) as connection:
        connection.executescript(SCHEMA)
        ensure_owner_settings_row(connection)
        migrate_apartments_unique_constraint(connection)
        migrate_tenants_civilite(connection)


def ensure_owner_settings_row(connection: sqlite3.Connection) -> None:
    """Keep exactly one row for private landlord settings."""
    connection.execute(
        """
        INSERT OR IGNORE INTO owner_settings (id, bailleur_nom, bailleur_email)
        VALUES (1, NULL, NULL)
        """
    )


def migrate_apartments_unique_constraint(connection: sqlite3.Connection) -> None:
    """Migrate old databases where numero_code was unique by itself."""
    columns = connection.execute("PRAGMA table_info(apartments)").fetchall()
    if not columns:
        return

    create_table = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'apartments'
        """
    ).fetchone()
    if create_table is None or "numero_code TEXT NOT NULL UNIQUE" not in create_table["sql"]:
        return

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.executescript(
            """
            CREATE TABLE apartments_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_code TEXT NOT NULL,
                adresse TEXT NOT NULL,
                loyer_hors_charge INTEGER NOT NULL,
                loyer_charges_uniquement INTEGER NOT NULL,
                UNIQUE(numero_code, adresse)
            );

            INSERT INTO apartments_new (
                id,
                numero_code,
                adresse,
                loyer_hors_charge,
                loyer_charges_uniquement
            )
            SELECT
                id,
                numero_code,
                adresse,
                loyer_hors_charge,
                loyer_charges_uniquement
            FROM apartments;

            DROP TABLE apartments;
            ALTER TABLE apartments_new RENAME TO apartments;
            """
        )
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def migrate_tenants_civilite(connection: sqlite3.Connection) -> None:
    """Add the civilite column to databases created before that field existed."""
    columns = connection.execute("PRAGMA table_info(tenants)").fetchall()
    column_names = {column["name"] for column in columns}
    if "civilite" not in column_names:
        connection.execute(
            "ALTER TABLE tenants ADD COLUMN civilite TEXT NOT NULL DEFAULT 'Monsieur'"
        )


def validate_civilite(civilite: str) -> str:
    """Normalize and validate the only civilities supported by the template."""
    normalized = civilite.strip()
    if normalized not in {"Madame", "Monsieur"}:
        raise ValueError("La civilite doit etre 'Madame' ou 'Monsieur'.")
    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """Store empty CLI values as NULL instead of invisible blank strings."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def update_owner_settings(
    bailleur_nom: str | None = None,
    bailleur_email: str | None = None,
    db_path: Path = DATABASE_PATH,
) -> None:
    """Update private owner settings stored only in the local SQLite database."""
    updates = []
    values = []

    if bailleur_nom is not None:
        updates.append("bailleur_nom = ?")
        values.append(normalize_optional_text(bailleur_nom))
    if bailleur_email is not None:
        updates.append("bailleur_email = ?")
        values.append(normalize_optional_text(bailleur_email))

    if not updates:
        raise ValueError("Aucune modification demandee.")

    with open_db(db_path) as connection:
        connection.executescript(SCHEMA)
        ensure_owner_settings_row(connection)
        connection.execute(
            f"UPDATE owner_settings SET {', '.join(updates)} WHERE id = 1",
            values,
        )


def get_owner_settings(db_path: Path = DATABASE_PATH) -> sqlite3.Row | dict[str, None]:
    """Return private owner settings without writing during read-only commands."""
    with open_db(db_path) as connection:
        try:
            owner = connection.execute(
                """
                SELECT bailleur_nom, bailleur_email
                FROM owner_settings
                WHERE id = 1
                """
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc):
                raise
            return {"bailleur_nom": None, "bailleur_email": None}

    return owner or {"bailleur_nom": None, "bailleur_email": None}


def add_apartment(
    numero_code: str,
    adresse: str,
    loyer_hors_charge: int,
    loyer_charges_uniquement: int,
    db_path: Path = DATABASE_PATH,
) -> None:
    """Create a new apartment without storing any private data in source code."""
    with open_db(db_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO apartments (
                    numero_code,
                    adresse,
                    loyer_hors_charge,
                    loyer_charges_uniquement
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    numero_code.strip(),
                    adresse.strip(),
                    loyer_hors_charge,
                    loyer_charges_uniquement,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Un appartement utilise deja ce couple numero + adresse."
            ) from exc


def add_tenant(
    prenom: str,
    nom: str,
    civilite: str,
    email: str,
    apartment_id: int,
    db_path: Path = DATABASE_PATH,
) -> None:
    """Create a tenant and link it to an existing apartment."""
    civilite = validate_civilite(civilite)
    with open_db(db_path) as connection:
        apartment = connection.execute(
            "SELECT id FROM apartments WHERE id = ?",
            (apartment_id,),
        ).fetchone()
        if apartment is None:
            raise ValueError(f"Appartement introuvable avec l'id {apartment_id}")

        connection.execute(
            """
            INSERT INTO tenants (prenom, nom, civilite, email, apartment_id, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (prenom.strip(), nom.strip(), civilite, email.strip(), apartment_id),
        )


def update_tenant(
    tenant_id: int,
    prenom: str | None = None,
    nom: str | None = None,
    civilite: str | None = None,
    email: str | None = None,
    apartment_id: int | None = None,
    db_path: Path = DATABASE_PATH,
) -> None:
    """Update only the tenant fields provided by the caller."""
    updates = []
    values = []

    if prenom is not None:
        updates.append("prenom = ?")
        values.append(prenom.strip())
    if nom is not None:
        updates.append("nom = ?")
        values.append(nom.strip())
    if civilite is not None:
        updates.append("civilite = ?")
        values.append(validate_civilite(civilite))
    if email is not None:
        updates.append("email = ?")
        values.append(email.strip())
    if apartment_id is not None:
        updates.append("apartment_id = ?")
        values.append(apartment_id)

    if not updates:
        raise ValueError("Aucune modification demandee.")

    with open_db(db_path) as connection:
        tenant = connection.execute(
            "SELECT id FROM tenants WHERE id = ?",
            (tenant_id,),
        ).fetchone()
        if tenant is None:
            raise ValueError(f"Locataire introuvable avec l'id {tenant_id}")

        if apartment_id is not None:
            apartment = connection.execute(
                "SELECT id FROM apartments WHERE id = ?",
                (apartment_id,),
            ).fetchone()
            if apartment is None:
                raise ValueError(f"Appartement introuvable avec l'id {apartment_id}")

        values.append(tenant_id)
        connection.execute(
            f"UPDATE tenants SET {', '.join(updates)} WHERE id = ?",
            values,
        )


def set_tenant_active(tenant_id: int, active: bool, db_path: Path = DATABASE_PATH) -> None:
    """Activate or deactivate a tenant without deleting their record."""
    with open_db(db_path) as connection:
        cursor = connection.execute(
            "UPDATE tenants SET active = ? WHERE id = ?",
            (1 if active else 0, tenant_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Locataire introuvable avec l'id {tenant_id}")


def update_apartment(
    apartment_id: int,
    numero_code: str | None = None,
    adresse: str | None = None,
    loyer_hors_charge: int | None = None,
    loyer_charges_uniquement: int | None = None,
    db_path: Path = DATABASE_PATH,
) -> None:
    """Update only the apartment fields provided by the caller."""
    updates = []
    values = []

    if numero_code is not None:
        updates.append("numero_code = ?")
        values.append(numero_code.strip())
    if adresse is not None:
        updates.append("adresse = ?")
        values.append(adresse.strip())
    if loyer_hors_charge is not None:
        updates.append("loyer_hors_charge = ?")
        values.append(loyer_hors_charge)
    if loyer_charges_uniquement is not None:
        updates.append("loyer_charges_uniquement = ?")
        values.append(loyer_charges_uniquement)

    if not updates:
        raise ValueError("Aucune modification demandee.")

    with open_db(db_path) as connection:
        values.append(apartment_id)
        try:
            cursor = connection.execute(
                f"UPDATE apartments SET {', '.join(updates)} WHERE id = ?",
                values,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Un autre appartement utilise deja ce couple numero + adresse."
            ) from exc

        if cursor.rowcount == 0:
            raise ValueError(f"Appartement introuvable avec l'id {apartment_id}")


def list_apartments(db_path: Path = DATABASE_PATH) -> list[sqlite3.Row]:
    with open_db(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT
                    id,
                    numero_code,
                    adresse,
                    loyer_hors_charge,
                    loyer_charges_uniquement,
                    loyer_hors_charge + loyer_charges_uniquement AS loyer_total
                FROM apartments
                ORDER BY id
                """
            )
        )


def list_tenants(db_path: Path = DATABASE_PATH) -> list[sqlite3.Row]:
    with open_db(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT
                    tenants.id,
                    tenants.prenom,
                    tenants.nom,
                    tenants.civilite,
                    tenants.email,
                    tenants.active,
                    apartments.id AS apartment_id,
                    apartments.numero_code AS appartement_numero_code
                FROM tenants
                JOIN apartments ON apartments.id = tenants.apartment_id
                ORDER BY apartments.id, tenants.nom, tenants.prenom
                """
            )
        )


def active_tenants_with_apartments(db_path: Path = DATABASE_PATH) -> list[sqlite3.Row]:
    with open_db(db_path) as connection:
        return list(
            connection.execute(
                """
                SELECT
                    tenants.id AS tenant_id,
                    tenants.prenom,
                    tenants.nom,
                    tenants.civilite,
                    tenants.email,
                    apartments.numero_code AS appartement_numero_code,
                    apartments.adresse AS appartement_adresse,
                    apartments.loyer_hors_charge,
                    apartments.loyer_charges_uniquement,
                    apartments.loyer_hors_charge + apartments.loyer_charges_uniquement AS loyer_total
                FROM tenants
                JOIN apartments ON apartments.id = tenants.apartment_id
                WHERE tenants.active = 1
                ORDER BY apartments.numero_code
                """
            )
        )
