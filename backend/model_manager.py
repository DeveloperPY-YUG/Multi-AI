from .config import model_entry


class Models:
    def __init__(self, config):
        self.config = config
        self.discovered = {}

    def all(self):
        catalog = {
            (m["provider"], m["id"]): dict(m, discovered=True, saved=False)
            for group in self.discovered.values()
            for m in group
        }
        for m in self.config.data["models"]:
            key = (m["provider"], m["id"])
            catalog[key] = dict(m, discovered=key in catalog, saved=True)
        hidden = {tuple(x) for x in self.config.data.get("hiddenModels", [])}
        return [m for k, m in catalog.items() if k not in hidden]

    def save(self, provider, mid, name):
        entry = model_entry(provider, mid, name, self.config.registry)
        rows = [
            m
            for m in self.config.data["models"]
            if (m["provider"], m["id"]) != (provider, entry["id"])
        ]
        hidden = [x for x in self.config.data.get("hiddenModels", []) if x != [provider, entry["id"]]]
        self.config.update(models=rows + [entry], hiddenModels=hidden)

    def remove(self, provider, mid):
        # Hide the model rather than destroying user-supplied IDs/renames.
        # This allows one-click removal with reliable restore (including manual models).
        visible = next(
            (m for m in self.all() if (m["provider"], m["id"]) == (provider, mid)),
            None,
        )
        if visible is None:
            raise ValueError("This model is no longer available to remove.")
        cfg = self.config.data
        hidden = [x for x in cfg.get("hiddenModels", []) if x != [provider, mid]]
        if len(hidden) >= 10000:
            raise ValueError("The removed-model list is full. Restore some models first.")
        updates = {"hiddenModels": hidden + [[provider, mid]]}
        if not visible["saved"]:
            # Remember a discovered model's ID/name too, so it can be restored
            # immediately after restart, even before the next API catalog refresh.
            updates["models"] = cfg["models"] + [
                model_entry(provider, mid, visible["name"], self.config.registry)
            ]
        if (cfg["defaultProvider"], cfg["defaultModel"]) == (provider, mid):
            updates["defaultModel"] = ""
        self.config.update(**updates)

    def restore(self, provider, mid):
        if provider not in self.config.registry:
            raise ValueError("This provider is no longer installed.")
        hidden = [x for x in self.config.data.get("hiddenModels", []) if x != [provider, mid]]
        self.config.update(hiddenModels=hidden)
