import getpass
import smtplib
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from smtplib import SMTPAuthenticationError, SMTPException

from .config import GMAIL_KEYRING_SERVICE, GMAIL_SMTP_HOST, GMAIL_SMTP_PORT


def get_gmail_password(gmail_address: str) -> str:
    """Read the Gmail app password from Windows keyring or ask the user once."""
    try:
        import keyring
    except ImportError:
        print("La librairie keyring n'est pas installee.")
        print("Le mot de passe d'application Gmail sera demande a chaque lancement.")
        return read_app_password()

    password = keyring.get_password(GMAIL_KEYRING_SERVICE, gmail_address)
    if password:
        password = normalize_app_password(password)
        print(f"Mot de passe Gmail charge depuis Windows ({len(password)} caracteres).")
        return password

    password = read_app_password()
    save = input("Le stocker dans le gestionnaire d'identifiants Windows ? [o/N] ").strip().lower()
    if save == "o":
        keyring.set_password(GMAIL_KEYRING_SERVICE, gmail_address, password)
        print("Mot de passe stocke dans le gestionnaire d'identifiants.")
    return password


def normalize_app_password(password: str) -> str:
    """Remove visual spaces often shown by Google in app passwords."""
    return "".join(password.split())


def read_app_password() -> str:
    """Read the hidden app password and confirm only its sanitized length."""
    password = normalize_app_password(getpass.getpass("Mot de passe d'application Gmail: "))
    print(f"Mot de passe capture ({len(password)} caracteres apres suppression des espaces).")
    if len(password) != 16:
        print("Attention: un mot de passe d'application Gmail contient normalement 16 caracteres.")
    return password


def forget_gmail_password(gmail_address: str) -> None:
    """Delete a stored Gmail app password from the Windows keyring."""
    try:
        import keyring
    except ImportError as exc:
        raise ValueError("La librairie keyring n'est pas installee.") from exc

    try:
        keyring.delete_password(GMAIL_KEYRING_SERVICE, gmail_address)
    except keyring.errors.PasswordDeleteError as exc:
        raise ValueError("Aucun mot de passe stocke trouve pour cette adresse.") from exc


def validate_email(address: str) -> str:
    """Keep email validation simple: enough to catch empty or obvious mistakes."""
    normalized = address.strip()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise ValueError(f"Adresse email invalide: {address}")
    return normalized


def validate_pdf_attachment(pdf_path: Path) -> None:
    """Fail early if the expected PDF attachment is missing or not a PDF."""
    if not pdf_path.exists():
        raise ValueError(f"Piece jointe introuvable: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"La piece jointe n'est pas un PDF: {pdf_path}")


def build_message(
    sender: str,
    recipient: str,
    tenant_first_name: str,
    month_label: str,
    pdf_path: Path,
    signature: str,
) -> EmailMessage:
    """Build the tenant email and attach the generated receipt PDF."""
    sender = validate_email(sender)
    recipient = validate_email(recipient)
    validate_pdf_attachment(pdf_path)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"Quittance de loyer - {month_label}"
    message.set_content(
        f"Bonjour {tenant_first_name},\n\n"
        f"Voici en piece jointe la quittance pour le mois de {month_label}.\n\n"
        "En te souhaitant bonne reception.\n\n"
        f"{signature}\n",
        charset="utf-8",
    )

    with pdf_path.open("rb") as file:
        message.add_attachment(
            file.read(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )
    return message


def build_test_message(sender: str, recipient: str) -> EmailMessage:
    """Build a tiny email used only to verify Gmail SMTP settings."""
    sender = validate_email(sender)
    recipient = validate_email(recipient)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "Test Rent Receipt Generator"
    message.set_content(
        "Bonjour,\n\n"
        "Ceci est un email de test envoye par Rent Receipt Generator.\n\n"
        "Si tu le recois, la configuration Gmail fonctionne.\n",
        charset="utf-8",
    )
    return message


def check_gmail_login(sender: str, password: str) -> list[str]:
    """Check Gmail SMTP connection and login without sending any email."""
    sender = validate_email(sender)
    steps = []
    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as smtp:
            steps.append("Connexion SMTP SSL ouverte.")
            smtp.ehlo()
            steps.append("Serveur Gmail joignable.")
            smtp.login(sender, password)
            steps.append("Authentification Gmail reussie.")
    except SMTPAuthenticationError as exc:
        raise ValueError(
            "Authentification Gmail refusee. Verifie l'adresse Gmail et le mot de passe d'application."
        ) from exc
    except UnicodeError as exc:
        raise ValueError(
            "Le mot de passe stocke contient un caractere non compatible avec Gmail SMTP. "
            "Supprime-le du gestionnaire d'identifiants puis ressaisis le mot de passe d'application."
        ) from exc
    except SMTPException as exc:
        raise ValueError(f"Erreur SMTP pendant le diagnostic Gmail: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Erreur reseau pendant le diagnostic Gmail: {exc}") from exc
    return steps


def send_message(sender: str, password: str, message: EmailMessage) -> None:
    """Send a prepared email through Gmail SMTP with readable errors."""
    try:
        # Sending bytes avoids ASCII-only serialization surprises on Windows.
        payload = message.as_bytes(policy=SMTP)
        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, message.get_all("To", []), payload)
    except SMTPAuthenticationError as exc:
        raise ValueError(
            "Authentification Gmail refusee. Verifie l'adresse Gmail et le mot de passe d'application."
        ) from exc
    except SMTPException as exc:
        raise ValueError(f"Erreur SMTP pendant l'envoi: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Erreur reseau pendant l'envoi Gmail: {exc}") from exc
    except UnicodeError as exc:
        raise ValueError(f"Erreur d'encodage pendant la preparation de l'email: {exc}") from exc
