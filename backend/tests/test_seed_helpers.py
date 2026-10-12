from scripts.seed_corpus import champion_markdown, strip_html


def test_strip_html_removes_tags_and_entities():
    assert strip_html("Daña <b>50</b> &amp; frena<br>al enemigo") == "Daña 50 & frena al enemigo"


def test_champion_markdown_contains_lore_and_spells():
    champ = {
        "name": "Jinx", "title": "el Gatillo Alegre", "tags": ["Marksman"],
        "lore": "Una criminal impulsiva de Zaun.",
        "passive": {"name": "¡Qué emoción!", "description": "Gana <b>velocidad</b>."},
        "spells": [{"name": "Zap!", "description": "Dispara una bala eléctrica."}],
        "allytips": ["Cambia de arma."], "enemytips": ["Cuidado con los cohetes."],
    }
    md = champion_markdown(champ)
    assert md.startswith("# Jinx, el Gatillo Alegre")
    assert "Una criminal impulsiva de Zaun." in md
    assert "Zap!" in md and "Gana velocidad." in md
    assert "Cambia de arma." in md


# --- Resiliencia de red (offline, httpx.MockTransport) ---

import httpx
import pytest

from scripts import seed_corpus


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(seed_corpus.time, "sleep", lambda _s: None)


def _champ(name):
    return {"data": {name: {"name": name, "title": "t", "tags": ["Mage"], "lore": "l",
                            "passive": {"name": "p", "description": "d"},
                            "spells": [{"name": "Q", "description": "q"}]}}}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ddragon_handler(fail):
    def handler(request):
        path = request.url.path
        if path.endswith("versions.json"):
            return httpx.Response(200, json=["1.0.0"])
        if path.endswith("/champion.json"):
            return httpx.Response(200, json={"data": {"Ahri": {}, "Bard": {}}})
        name = path.rsplit("/", 1)[1].removesuffix(".json")
        return fail(name) or httpx.Response(200, json=_champ(name))
    return handler


def test_fetch_champions_retries_after_500():
    calls = {"Ahri": 0}

    def fail(name):
        if name == "Ahri":
            calls["Ahri"] += 1
            if calls["Ahri"] == 1:
                return httpx.Response(500)

    champs, failed = seed_corpus.fetch_champions(_client(_ddragon_handler(fail)))
    assert set(champs) == {"Ahri", "Bard"} and failed == [] and calls["Ahri"] == 2


def test_fetch_champions_permanent_failure_does_not_abort_others():
    def fail(name):
        if name == "Ahri":
            return httpx.Response(503)

    champs, failed = seed_corpus.fetch_champions(_client(_ddragon_handler(fail)))
    assert set(champs) == {"Bard"} and failed == ["Ahri"]


def test_fetch_champions_non_json_is_skipped():
    def fail(name):
        if name == "Bard":
            return httpx.Response(200, text="<html>oops</html>")

    champs, failed = seed_corpus.fetch_champions(_client(_ddragon_handler(fail)))
    assert set(champs) == {"Ahri"} and failed == ["Bard"]


def test_champion_markdown_without_tips_and_empty_spells():
    md = seed_corpus.champion_markdown({
        "name": "X", "title": "Y", "tags": [], "lore": "l",
        "passive": {"name": "p", "description": "d"}, "spells": [],
    })
    assert md.startswith("# X, Y")
    assert "Consejos" not in md


def _region_client(body):
    return _client(lambda request: httpx.Response(200, json=body))


def test_fetch_region_strips_script_and_style():
    html_body = "<style>.a{color:red}</style><script>var x=1;</script><p>" + "Texto útil. " * 30 + "</p>"
    text = seed_corpus.fetch_region(_region_client({"parse": {"text": {"*": html_body}}}), "Zaun")
    assert text.startswith("# Zaun")
    assert "color:red" not in text and "var x" not in text and "Texto útil." in text


def test_fetch_region_short_or_missing_page_returns_none():
    assert seed_corpus.fetch_region(_region_client({"parse": {"text": {"*": "<p>corto</p>"}}}), "Z") is None
    assert seed_corpus.fetch_region(_region_client({"error": {"code": "missingtitle"}}), "Z") is None


# --- Carga de documentos: un ingest fallido cuenta como fallo ---

class _FakeStore:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.purged = []
        self.created = []

    def purge_failed_shared(self, name):
        self.purged.append(name)
        return 0

    def find_shared(self, name):
        return "x" if name in self.existing else None

    def create_document(self, user_id, name, type_):
        self.created.append(name)
        return f"id-{name}"


class _FakeIngestion:
    def __init__(self, results):
        self.results = results

    def ingest(self, document_id, filename, data):
        result = self.results[filename]
        if isinstance(result, Exception):
            raise result
        return result


def test_load_documents_counts_failed_ingest_and_not_ok(capsys):
    store = _FakeStore(existing={"C.md"})
    ingestion = _FakeIngestion({"A.md": True, "B.md": False, "D.md": RuntimeError("boom")})
    docs = [("A.md", "a"), ("B.md", "b"), ("C.md", "c"), ("D.md", "d")]
    ok, skipped, failed = seed_corpus.load_documents(store, ingestion, docs)
    out = capsys.readouterr().out
    assert (ok, skipped, failed) == (1, 1, 2)
    assert "OK A.md" in out and "OK B.md" not in out
    assert "FAIL B.md: ingest ended in error" in out
    assert store.purged == ["A.md", "B.md", "C.md", "D.md"]


def test_main_exits_nonzero_when_ingest_fails(monkeypatch):
    import sys
    import types

    store, ingestion = _FakeStore(), _FakeIngestion({"Region-Zaun.md": False})
    monkeypatch.setitem(sys.modules, "app.deps", types.SimpleNamespace(
        get_vector_store=lambda: store, get_ingestion=lambda: ingestion))
    monkeypatch.setattr(seed_corpus, "fetch_champions", lambda client: ({}, []))
    monkeypatch.setattr(seed_corpus, "fetch_region", lambda client, title: "texto" if title == "Zaun" else None)
    monkeypatch.setattr(seed_corpus, "REGIONS", ["Zaun"])
    monkeypatch.setattr(seed_corpus, "DEMO_DIR", seed_corpus.Path(__file__).parent)
    monkeypatch.setattr(sys, "argv", ["seed_corpus"])
    with pytest.raises(SystemExit) as exc:
        seed_corpus.main()
    assert exc.value.code == 1
