from app.controllers.ratelimit import SlidingWindowLimiter
from app.deps import CatalogCache, make_catalog
from tests.fakes import FakeStore


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_sliding_window_blocks_and_recovers():
    clock = Clock()
    lim = SlidingWindowLimiter(clock)
    assert lim.check("u", 2) is None
    clock.t = 10
    assert lim.check("u", 2) is None
    assert lim.check("u", 2) == 50
    assert lim.check("otro", 2) is None
    clock.t = 60
    assert lim.check("u", 2) is None  # la primera salió de la ventana


def test_limit_zero_disables():
    lim = SlidingWindowLimiter(Clock())
    assert all(lim.check("u", 0) is None for _ in range(100))


def test_catalog_cache_ttl_and_invalidation():
    clock = Clock()
    cache = CatalogCache(clock)
    store = FakeStore()
    catalog = make_catalog(store, 30, cache)
    assert catalog("u") == []
    doc = store.create_document("u", "a.md", "md")
    store.set_status(doc, "ready")
    assert catalog("u") == []  # sigue en caché
    clock.t = 31
    assert catalog("u") == ["a.md"]  # expiró
    store.create_document("u", "b.md", "md")
    store.set_status(next(i for i, d in store.docs.items() if d["name"] == "b.md"), "ready")
    cache.invalidate("u")
    assert sorted(catalog("u")) == ["a.md", "b.md"]


def test_catalog_cache_is_per_user_and_ttl_zero_disables():
    store = FakeStore()
    catalog = make_catalog(store, 0, CatalogCache())
    assert catalog("u") == []
    store.set_status(store.create_document("u", "a.md", "md"), "ready")
    assert catalog("u") == ["a.md"]
    assert catalog("v") == []
