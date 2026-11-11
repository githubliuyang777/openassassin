"""Certificate maintenance provider registry.

New providers implement the same small interface and register here; domain rows only
store the provider key and a JSON config, so no Domain schema change is needed.
"""
from app.services import baota_service


class BaotaProvider:
    key = "baota"
    name = "宝塔面板"

    def validate_config(self, db, config: dict) -> dict:
        return baota_service.validate_domain_config(db, config)

    def start_renewal(self, domain_name: str, config: dict) -> dict:
        return baota_service.start_renewal(domain_name, config)

    def deploy(self, domain_name: str, config: dict, renewal: dict) -> None:
        baota_service.deploy_order(domain_name, config, renewal)


PROVIDERS = {provider.key: provider for provider in [BaotaProvider()]}


def list_providers() -> list[dict]:
    return [
        {"key": provider.key, "name": provider.name, "enabled": True}
        for provider in PROVIDERS.values()
    ]


def get_provider(key: str):
    return PROVIDERS.get(key) if key and key != "none" else None


def validate_domain_config(db, key: str, config: dict | None) -> dict:
    if key in ("", "none"):
        return {}
    provider = get_provider(key)
    if not provider:
        raise ValueError("不支持的证书维护平台")
    return provider.validate_config(db, config or {})
