"""Administrative local bootstrap; uses the same service adapters as reindex."""
from p091.config import Settings
from p091.seed import seed_store
from p091.services import Services
from p091.store import Store


def main() -> None:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    seed_store(store)
    services = Services(store, settings)
    indexed = 0
    with store.lock:
        for document in store.documents():
            if not document["deleted"]:
                services.reindex(document)
                indexed += 1
    print(f"Indexed {indexed} active synthetic documents; mode={settings.mode}; source={'nextcloud' if settings.nextcloud_enabled else 'fixture'}")
    store.close()


if __name__ == "__main__":
    main()
