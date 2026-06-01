import argparse
from datetime import date

from .db import (
    active_tenants_with_apartments,
    add_apartment,
    add_tenant,
    get_owner_settings,
    init_db,
    list_apartments,
    list_tenants,
    set_tenant_active,
    update_apartment,
    update_owner_settings,
    update_tenant,
)
from .mailer import (
    build_message,
    build_test_message,
    check_gmail_login,
    forget_gmail_password,
    get_gmail_password,
    send_message,
    validate_email,
)
from .receipts import generate_receipts, preview_pdf


def ask_month_year(args) -> tuple[int, int]:
    """Read month/year from CLI flags or ask interactively."""
    month = args.month
    year = args.year

    if month is None:
        month = int(input(f"Mois [1-12] ({date.today().month}): ") or date.today().month)
    if year is None:
        year = int(input(f"Annee ({date.today().year}): ") or date.today().year)

    return month, year


def owner_name() -> str:
    """Read the landlord name required by the Word template."""
    owner = get_owner_settings()
    name = owner["bailleur_nom"] if owner else None
    if not name:
        raise ValueError(
            "Nom du bailleur manquant. Configure-le avec "
            "`python -m rent_receipt_generator set-owner --nom \"Jean Dupont\"`."
        )
    return name.strip()


def owner_email(sender_override: str | None = None) -> str:
    """Use --sender when provided, otherwise use the private owner email."""
    if sender_override:
        return validate_email(sender_override)

    owner = get_owner_settings()
    email = owner["bailleur_email"] if owner else None
    if not email:
        raise ValueError(
            "Email du bailleur manquant. Configure-le avec "
            "`python -m rent_receipt_generator set-owner --email owner@example.com`."
        )
    return validate_email(email)


def command_init_db(_args) -> None:
    """Create or migrate the local SQLite database."""
    init_db()
    print("Base SQLite initialisee.")


def command_list(_args) -> None:
    """Display apartments and tenants in a human-readable format."""
    print("\nAppartements")
    print("------------")
    for apartment in list_apartments():
        print(
            f"- ID {apartment['id']} | {apartment['numero_code']} | {apartment['adresse']} | "
            f"{apartment['loyer_hors_charge']} + {apartment['loyer_charges_uniquement']} = "
            f"{apartment['loyer_total']} euros"
        )

    print("\nLocataires")
    print("----------")
    tenants = list_tenants()
    if not tenants:
        print("Aucun locataire enregistre.")
    for tenant in tenants:
        status = "actif" if tenant["active"] else "inactif"
        print(
            f"- ID {tenant['id']} | {tenant['civilite']} {tenant['prenom']} {tenant['nom']} | "
            f"{tenant['email']} | "
            f"appartement ID {tenant['apartment_id']} ({tenant['appartement_numero_code']}) | {status}"
        )


def command_show_owner(_args) -> None:
    """Display configured landlord settings without showing any password."""
    owner = get_owner_settings()
    name = owner["bailleur_nom"] or "non configure"
    email = owner["bailleur_email"] or "non configure"
    print("\nBailleur")
    print("--------")
    print(f"Nom   : {name}")
    print(f"Email : {email}")


def command_set_owner(args) -> None:
    """Update private landlord settings used for PDFs and Gmail."""
    email = validate_email(args.email) if args.email else None
    update_owner_settings(bailleur_nom=args.nom, bailleur_email=email)
    print("Informations bailleur mises a jour.")


def command_add_tenant(args) -> None:
    add_tenant(args.prenom, args.nom, args.civilite, args.email, args.apartment_id)
    print(f"Locataire ajoute: {args.prenom} {args.nom}")


def command_add_apartment(args) -> None:
    add_apartment(
        numero_code=args.numero_code,
        adresse=args.adresse,
        loyer_hors_charge=args.loyer_hors_charge,
        loyer_charges_uniquement=args.charges,
    )
    print(f"Appartement ajoute: {args.numero_code}")


def command_update_tenant(args) -> None:
    update_tenant(
        tenant_id=args.tenant_id,
        prenom=args.prenom,
        nom=args.nom,
        civilite=args.civilite,
        email=args.email,
        apartment_id=args.apartment_id,
    )
    print(f"Locataire ID {args.tenant_id} modifie.")


def command_deactivate_tenant(args) -> None:
    set_tenant_active(args.tenant_id, False)
    print(f"Locataire ID {args.tenant_id} desactive.")


def command_activate_tenant(args) -> None:
    set_tenant_active(args.tenant_id, True)
    print(f"Locataire ID {args.tenant_id} active.")


def command_update_apartment(args) -> None:
    update_apartment(
        apartment_id=args.apartment_id,
        numero_code=args.numero_code,
        adresse=args.adresse,
        loyer_hors_charge=args.loyer_hors_charge,
        loyer_charges_uniquement=args.charges,
    )
    print(f"Appartement ID {args.apartment_id} modifie.")


def command_generate(args) -> None:
    """Generate receipt PDFs without sending any email."""
    month, year = ask_month_year(args)
    rows = active_tenants_with_apartments()
    if not rows:
        raise SystemExit("Aucun locataire actif. Ajoute d'abord un locataire.")

    generated = generate_receipts(rows, month, year, owner_name())
    for receipt in generated:
        print(f"PDF genere: {receipt.pdf_path}")
        if args.preview:
            preview_pdf(receipt.pdf_path)


def command_run(args) -> None:
    """Generate receipts, preview them, then optionally send one email per receipt."""
    month, year = ask_month_year(args)
    rows = active_tenants_with_apartments()
    if not rows:
        raise SystemExit("Aucun locataire actif. Ajoute d'abord un locataire.")

    signature = owner_name()
    generated = generate_receipts(rows, month, year, signature)
    for receipt in generated:
        print(f"PDF genere: {receipt.pdf_path}")
        preview_pdf(receipt.pdf_path)

    sender = owner_email(args.sender)
    password = None if args.dry_run else get_gmail_password(sender)

    for receipt, row in zip(generated, rows):
        print("\nEmail prepare")
        print("-------------")
        print(f"Destinataire : {receipt.tenant_name} <{receipt.tenant_email}>")
        print(f"Objet        : Quittance de loyer - {receipt.month_label}")
        print(f"Piece jointe : {receipt.pdf_path}")
        print(f"Signature    : {signature}")

        if args.dry_run:
            print("Mode dry-run : aucun email n'est envoye.")
            continue

        answer = input(f"Envoyer la quittance a {receipt.tenant_name} <{receipt.tenant_email}> ? [o/N] ")
        if answer.strip().lower() != "o":
            print("Envoi ignore.")
            continue

        message = build_message(
            sender=sender,
            recipient=receipt.tenant_email,
            tenant_first_name=row["prenom"].strip(),
            month_label=receipt.month_label,
            pdf_path=receipt.pdf_path,
            signature=signature,
        )
        send_message(sender, password, message)
        print(f"Email envoye a {receipt.tenant_email}")


def command_test_email(args) -> None:
    """Send one minimal email to verify Gmail credentials before real receipts."""
    sender = owner_email(args.sender)
    recipient = validate_email(args.recipient)
    password = get_gmail_password(sender)
    message = build_test_message(sender, recipient)
    send_message(sender, password, message)
    print(f"Email de test envoye a {recipient}")


def command_check_gmail(args) -> None:
    """Verify Gmail SMTP connection and login without sending an email."""
    sender = owner_email(args.sender)
    password = get_gmail_password(sender)
    for step in check_gmail_login(sender, password):
        print(step)


def command_forget_gmail_password(args) -> None:
    """Remove the stored Gmail app password so it can be entered again."""
    sender = owner_email(args.sender)
    forget_gmail_password(sender)
    print(f"Mot de passe Gmail supprime pour {sender}.")


def build_parser() -> argparse.ArgumentParser:
    """Declare every command available through `python -m rent_receipt_generator ...`."""
    parser = argparse.ArgumentParser(description="Generation et envoi de quittances de loyer.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialiser la base SQLite.")
    init_parser.set_defaults(func=command_init_db)

    list_parser = subparsers.add_parser("list", help="Afficher les donnees enregistrees.")
    list_parser.set_defaults(func=command_list)

    show_owner_parser = subparsers.add_parser("show-owner", help="Afficher les infos bailleur.")
    show_owner_parser.set_defaults(func=command_show_owner)

    set_owner_parser = subparsers.add_parser("set-owner", help="Modifier les infos bailleur.")
    set_owner_parser.add_argument("--nom", help="Nom utilise dans les quittances et la signature email.")
    set_owner_parser.add_argument("--email", help="Adresse Gmail d'envoi par defaut.")
    set_owner_parser.set_defaults(func=command_set_owner)

    add_parser = subparsers.add_parser("add-tenant", help="Ajouter un locataire.")
    add_parser.add_argument("--prenom", required=True)
    add_parser.add_argument("--nom", required=True)
    add_parser.add_argument("--civilite", required=True, choices=["Madame", "Monsieur"])
    add_parser.add_argument("--email", required=True)
    add_parser.add_argument("--apartment-id", type=int, required=True, help="ID affiche par la commande list.")
    add_parser.set_defaults(func=command_add_tenant)

    add_apartment_parser = subparsers.add_parser("add-apartment", help="Ajouter un appartement.")
    add_apartment_parser.add_argument("--numero-code", required=True)
    add_apartment_parser.add_argument("--adresse", required=True)
    add_apartment_parser.add_argument("--loyer-hors-charge", type=int, required=True)
    add_apartment_parser.add_argument("--charges", type=int, required=True)
    add_apartment_parser.set_defaults(func=command_add_apartment)

    update_tenant_parser = subparsers.add_parser("update-tenant", help="Modifier un locataire.")
    update_tenant_parser.add_argument("--tenant-id", type=int, required=True)
    update_tenant_parser.add_argument("--prenom")
    update_tenant_parser.add_argument("--nom")
    update_tenant_parser.add_argument("--civilite", choices=["Madame", "Monsieur"])
    update_tenant_parser.add_argument("--email")
    update_tenant_parser.add_argument("--apartment-id", type=int)
    update_tenant_parser.set_defaults(func=command_update_tenant)

    deactivate_tenant_parser = subparsers.add_parser("deactivate-tenant", help="Desactiver un locataire.")
    deactivate_tenant_parser.add_argument("--tenant-id", type=int, required=True)
    deactivate_tenant_parser.set_defaults(func=command_deactivate_tenant)

    activate_tenant_parser = subparsers.add_parser("activate-tenant", help="Reactiver un locataire.")
    activate_tenant_parser.add_argument("--tenant-id", type=int, required=True)
    activate_tenant_parser.set_defaults(func=command_activate_tenant)

    update_apartment_parser = subparsers.add_parser("update-apartment", help="Modifier un appartement.")
    update_apartment_parser.add_argument("--apartment-id", type=int, required=True)
    update_apartment_parser.add_argument("--numero-code")
    update_apartment_parser.add_argument("--adresse")
    update_apartment_parser.add_argument("--loyer-hors-charge", type=int)
    update_apartment_parser.add_argument("--charges", type=int)
    update_apartment_parser.set_defaults(func=command_update_apartment)

    generate_parser = subparsers.add_parser("generate", help="Generer les PDF sans envoyer d'email.")
    generate_parser.add_argument("--month", type=int)
    generate_parser.add_argument("--year", type=int)
    generate_parser.add_argument("--preview", action="store_true")
    generate_parser.set_defaults(func=command_generate)

    run_parser = subparsers.add_parser("run", help="Generer, previsualiser, puis envoyer.")
    run_parser.add_argument("--month", type=int)
    run_parser.add_argument("--year", type=int)
    run_parser.add_argument("--sender", help="Adresse Gmail d'envoi.")
    run_parser.add_argument("--dry-run", action="store_true", help="Prepare les emails sans les envoyer.")
    run_parser.set_defaults(func=command_run)

    test_email_parser = subparsers.add_parser("test-email", help="Envoyer un email de test sans quittance.")
    test_email_parser.add_argument("--sender", help="Adresse Gmail d'envoi.")
    test_email_parser.add_argument("--recipient", required=True, help="Adresse qui recoit le test.")
    test_email_parser.set_defaults(func=command_test_email)

    check_gmail_parser = subparsers.add_parser("check-gmail", help="Verifier Gmail sans envoyer d'email.")
    check_gmail_parser.add_argument("--sender", help="Adresse Gmail d'envoi.")
    check_gmail_parser.set_defaults(func=command_check_gmail)

    forget_gmail_parser = subparsers.add_parser(
        "forget-gmail-password",
        help="Supprimer le mot de passe Gmail stocke localement.",
    )
    forget_gmail_parser.add_argument("--sender", help="Adresse Gmail d'envoi.")
    forget_gmail_parser.set_defaults(func=command_forget_gmail_password)

    return parser


def main() -> None:
    """Parse CLI arguments and convert expected errors into readable messages."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as exc:
        raise SystemExit(f"Erreur: {exc}") from exc
