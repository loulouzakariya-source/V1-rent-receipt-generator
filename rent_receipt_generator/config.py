from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = APP_DIR / "Quittance_Template.docx"
DATABASE_PATH = APP_DIR / "rent_receipt_generator.db"
OUTPUT_DIR = APP_DIR / "quittances"

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
GMAIL_KEYRING_SERVICE = "Rent Receipt Generator Gmail"
