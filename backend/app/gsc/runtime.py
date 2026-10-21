from functools import lru_cache

from app.db.database import Database
from app.gsc.client import FixtureGSCClient, GoogleGSCClient
from app.gsc.oauth import OAuthService
from app.gsc.sync import SyncManager
from app.gsc.vault import CredentialVault


class Runtime:
    def __init__(self, db=None, vault=None, client_factory=None):
        self.db = db or Database()
        self.db.migrate()
        self.oauth = OAuthService(self.db, vault or CredentialVault())
        self.sync = SyncManager(self.db, client_factory or self.client)

    def client(self, prop, on_retry=None):
        return FixtureGSCClient() if prop.source_type == "fixture" else GoogleGSCClient(self.oauth, prop.connection_id, on_retry)


@lru_cache
def get_runtime() -> Runtime:
    return Runtime()
