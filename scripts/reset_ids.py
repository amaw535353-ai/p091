"""After explicit Compose volume reset, clear only store IDs and seed marker."""
from bootstrap_live import read_env, write_env

values = read_env()
values["FGA_STORE_ID"] = ""
values["FGA_MODEL_ID"] = ""
values["FGA_SEEDED"] = "false"
values["NEXTCLOUD_ENABLED"] = "false"
write_env(values)
print("Cleared local service IDs. Secrets retained; no external systems touched.")
