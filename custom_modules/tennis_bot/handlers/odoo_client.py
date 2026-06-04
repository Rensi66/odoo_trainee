import logging

import config
from xmlrpc.client import ServerProxy

_logger = logging.getLogger(__name__)

class OdooClient:
    def __init__(self):
        self.url = config.ODOO_URL
        self.username = config.ODOO_USER
        self.password = config.ODOO_PASSWORD
        self.db = config.ODOO_DB
        self.uid = None
        self.model = None

    def connect(self):
        if not self.uid:
            try:
                common = ServerProxy(f"{self.url}/xmlrpc/2/common")
                self.uid = common.authenticate(self.db, self.username, self.password, {})
                self.model = ServerProxy(f"{self.url}/xmlrpc/2/object")
            except Exception as e:
                _logger.exception(e)

    def execute(self, model, method, *args, **kwargs):
        self.connect()
        return self.model.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs)


odoo = OdooClient()