"""Enable local extended source adapter without sourcing executable dotenv text."""
from bootstrap_live import read_env, write_env

values = read_env()
values["NEXTCLOUD_ENABLED"] = "true"
write_env(values)
print("Nextcloud source enabled; recreate only the local API service.")
