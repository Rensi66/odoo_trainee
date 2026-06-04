import os
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ODOO_URL = os.environ["ODOO_URL"]
ODOO_DB = os.environ["ODOO_DB"]
ODOO_USER = os.environ["ODOO_USER"]
ODOO_PASSWORD = os.environ["ODOO_PASSWORD"]
