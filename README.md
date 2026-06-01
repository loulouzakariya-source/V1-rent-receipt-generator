# Rent Receipt Generator

Rent Receipt Generator is a local-first Python tool for generating monthly rent receipts from a Word template, converting them to PDF with Microsoft Word, and sending them to tenants through Gmail SMTP.

The current version is a command-line V1 designed for Windows. A graphical interface can be built on top of the same core modules later.

## Features

- Store apartments, tenants, and landlord settings in a local SQLite database.
- Generate one personalized receipt per active tenant.
- Replace Word placeholders such as `{locataire_nom_prenom}`, `{bailleur_nom}`, `{date_mois_et_annee}`, and rent amounts.
- Convert generated `.docx` files to `.pdf` with Microsoft Word.
- Send receipts through Gmail using an app password.
- Store the Gmail app password in the Windows Credential Manager through `keyring`.
- Keep private files out of Git by default.

## Security And Privacy

Rent Receipt Generator is intentionally local-first:

- Tenant data is stored in `rent_receipt_generator.db`.
- Landlord name and sender email are stored in `rent_receipt_generator.db`.
- Gmail app passwords are stored through the system keyring, not in source code.
- Generated receipts are stored under `quittances/`.
- The private Word template is expected to be named `Quittance_Template.docx`.

These files are ignored by Git:

```text
*.db
quittances/
Quittance_Template.docx
.env
.env.*
*.local.*
```

Before publishing the repository, always run:

```powershell
git status
git ls-files
```

Make sure no database, real template, generated receipt, tenant name, tenant email, landlord name, or real address is tracked by Git.

## Requirements

- Windows
- Python 3.11 or newer
- Microsoft Word installed locally
- A Gmail account with 2-step verification enabled
- A Gmail app password for SMTP authentication

Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install development dependencies for tests:

```powershell
python -m pip install -r requirements-dev.txt
```

## Template

Place your private Word template at the project root:

```text
Quittance_Template.docx
```

The template can contain placeholders such as:

```text
{bailleur_nom}
{civilite}
{locataire_prenom}
{locataire_nom}
{locataire_nom_prenom}
{appartement_numero_code}
{appartement_adresse}
{date_mois_et_annee}
{date_premier_jour_du_mois}
{date_dernier_jour_du_mois}
{date_paiement}
{loyer_total}
{loyer_hors_charge}
{loyer_charges_uniquement}
```

The real template is private and should not be committed. If you want to publish an example template later, create an anonymized file such as `Quittance_Template.example.docx`.

## Initialize The Database

```powershell
python -m rent_receipt_generator init-db
```

List current data:

```powershell
python -m rent_receipt_generator list
```

## Configure The Landlord

Landlord settings are stored locally in `rent_receipt_generator.db`.

```powershell
python -m rent_receipt_generator set-owner --nom "Jane Owner" --email owner@example.com
python -m rent_receipt_generator show-owner
```

The landlord name is used for `{bailleur_nom}` and email signatures. The landlord email is used as the default Gmail sender.

## Manage Apartments

Add an apartment:

```powershell
python -m rent_receipt_generator add-apartment --numero-code "Apartment 101" --adresse "1 Example Street, 75000 Paris" --loyer-hors-charge 700 --charges 80
```

Update an apartment:

```powershell
python -m rent_receipt_generator update-apartment --apartment-id 1 --loyer-hors-charge 720 --charges 85
```

## Manage Tenants

Add a tenant:

```powershell
python -m rent_receipt_generator add-tenant --prenom Jane --nom Doe --civilite Madame --email jane@example.com --apartment-id 1
```

Use quotes for compound names:

```powershell
python -m rent_receipt_generator add-tenant --prenom John --nom "Van Doe" --civilite Monsieur --email john@example.com --apartment-id 1
```

Update a tenant:

```powershell
python -m rent_receipt_generator update-tenant --tenant-id 1 --email new.email@example.com
python -m rent_receipt_generator update-tenant --tenant-id 1 --apartment-id 2
python -m rent_receipt_generator update-tenant --tenant-id 1 --civilite Madame
```

Deactivate or reactivate a tenant:

```powershell
python -m rent_receipt_generator deactivate-tenant --tenant-id 1
python -m rent_receipt_generator activate-tenant --tenant-id 1
```

Inactive tenants stay in the database but are ignored when receipts are generated.

## Generate Receipts

Generate PDFs without sending email:

```powershell
python -m rent_receipt_generator generate --month 6 --year 2026
```

Preview generated PDFs:

```powershell
python -m rent_receipt_generator generate --month 6 --year 2026 --preview
```

Generated files are written to:

```text
quittances/YYYY-MM/
```

## Gmail Setup

Use a Gmail app password, not your main Google password.

1. Enable 2-step verification on your Google account.
2. Create a Gmail app password.
3. Run a Gmail check or send flow.
4. Enter the app password when prompted.
5. Accept storing it in the Windows Credential Manager if desired.

Check Gmail login without sending email:

```powershell
python -m rent_receipt_generator check-gmail
```

Send a minimal test email:

```powershell
python -m rent_receipt_generator test-email --recipient recipient@example.com
```

Forget the stored Gmail app password:

```powershell
python -m rent_receipt_generator forget-gmail-password
```

## Generate And Send

Simulate the full flow without sending email:

```powershell
python -m rent_receipt_generator run --month 6 --year 2026 --dry-run
```

Generate receipts and send them:

```powershell
python -m rent_receipt_generator run --month 6 --year 2026
```

You can temporarily override the configured sender:

```powershell
python -m rent_receipt_generator run --month 6 --year 2026 --sender another.sender@example.com
```

## Tests

The automated tests cover:

- Monthly date calculation, including leap years.
- SQLite database initialization and core operations.
- Template data preparation.
- Email message construction without contacting Gmail.

Run tests:

```powershell
python -m pytest
```

These tests do not use your real database, do not open Microsoft Word, and do not send emails.

## Project Structure

```text
rent_receipt_generator/
  __main__.py      # Enables `python -m rent_receipt_generator`
  cli.py           # Command-line interface
  config.py        # Local paths and Gmail SMTP constants
  db.py            # SQLite schema and data access functions
  mailer.py        # Gmail SMTP and email message helpers
  receipts.py      # Word template filling and PDF generation
tests/
  test_database.py
  test_mailer.py
  test_receipt_dates.py
  test_template_data.py
```

## Current Limitations

- PDF conversion requires Microsoft Word on Windows.
- The V1 interface is command-line only.
- The project currently supports one active apartment assignment per tenant.
- Email delivery depends on Gmail SMTP availability and valid app-password credentials.

## Roadmap

- Add a desktop GUI for non-technical usage.
- Add an anonymized sample Word template.
- Add optional global confirmation before sending all emails.
- Add import/export helpers for backup and migration.
