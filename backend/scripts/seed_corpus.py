"""Carga el corpus compartido: campeones (Data Dragon, es_MX) y regiones (wiki de LoL en español)."""
import argparse
import html
import re
import sys
import time
from pathlib import Path

import httpx

DDRAGON = "https://ddragon.leagueoflegends.com"
LOCALE = "es_MX"
WIKI_API = "https://leagueoflegends.fandom.com/es/api.php"
USER_AGENT = "HextechArchive/0.1 (educational project)"
REGIONS = [
    "Demacia", "Noxus", "Piltóver", "Zaun", "Freljord", "Jonia", "Islas de la Sombra",
    "Targón", "Shurima", "Aguas Estancadas", "Ixtal", "El Vacío", "Ciudad Bandle",
]
DEMO_DIR = Path(__file__).resolve().parents[1] / "demo_docs"
MAX_ATTEMPTS = 3
FETCH_ERRORS = (httpx.HTTPError, ValueError, KeyError)


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def champion_markdown(c: dict) -> str:
    spells = "\n".join(f"- {s['name']}: {strip_html(s['description'])}" for s in c["spells"])
    lines = [
        f"# {c['name']}, {c['title']}",
        f"Roles: {', '.join(c['tags'])}",
        "## Historia",
        strip_html(c["lore"]),
        f"## Pasiva: {c['passive']['name']}",
        strip_html(c["passive"]["description"]),
        "## Habilidades",
        spells,
    ]
    if c.get("allytips"):
        lines += ["## Consejos para jugar con él/ella", "\n".join(f"- {t}" for t in c["allytips"])]
    if c.get("enemytips"):
        lines += ["## Consejos para enfrentarlo", "\n".join(f"- {t}" for t in c["enemytips"])]
    return "\n\n".join(lines)


def get_json(client: httpx.Client, url: str, params: dict | None = None):
    """GET con raise_for_status y hasta 3 intentos (backoff 1s, 2s) para 429/5xx/errores de red."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = isinstance(exc, httpx.TransportError) or (
                exc.response.status_code == 429 or exc.response.status_code >= 500
            )
            if not retryable or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(attempt)


def fetch_champions(client: httpx.Client) -> tuple[dict[str, dict], list[str]]:
    """Devuelve (campeones obtenidos, ids fallidos). Fallar en versions/index es fatal."""
    version = get_json(client, f"{DDRAGON}/api/versions.json")[0]
    index = get_json(client, f"{DDRAGON}/cdn/{version}/data/{LOCALE}/champion.json")["data"]
    out: dict[str, dict] = {}
    failed: list[str] = []
    for champ_id in index:
        try:
            detail = get_json(client, f"{DDRAGON}/cdn/{version}/data/{LOCALE}/champion/{champ_id}.json")
            out[champ_id] = detail["data"][champ_id]
        except FETCH_ERRORS as exc:
            print(f"FAIL {champ_id}: {exc!r}")
            failed.append(champ_id)
        time.sleep(0.05)
    return out, failed


def fetch_region(client: httpx.Client, title: str) -> str | None:
    # La wiki en español no tiene TextExtracts: se usa action=parse y se limpia el HTML.
    params = {"action": "parse", "prop": "text", "format": "json", "redirects": 1,
              "page": title, "disablelimitreport": 1}
    data = get_json(client, WIKI_API, params=params)
    if "parse" not in data:
        return None
    raw = re.sub(r"(?is)<style.*?</style>|<script.*?</script>", "", data["parse"]["text"]["*"])
    text = strip_html(raw)
    return f"# {title}\n\n{text}" if len(text) > 200 else None


def load_documents(store, ingestion, docs: list[tuple[str, str]]) -> tuple[int, int, int]:
    """Ingesta cada documento compartido. Devuelve (ok, skipped, failed)."""
    ok = skipped = failed = 0
    for name, text in docs:
        store.purge_failed_shared(name)  # un intento previo fallido no debe saltarse para siempre
        if store.find_shared(name):
            print(f"SKIP {name} (ya existe)")
            skipped += 1
            continue
        try:
            doc_id = store.create_document(None, name, "md")
            ready = ingestion.ingest(doc_id, name, text.encode("utf-8"))
        except Exception as exc:  # un documento malo no debe abortar la carga
            print(f"FAIL {name}: {exc!r}")
            failed += 1
            continue
        if not ready:
            print(f"FAIL {name}: ingest ended in error")
            failed += 1
            continue
        print(f"OK {name}")
        ok += 1
    return ok, skipped, failed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", default="Briar,Hwei",
                        help="IDs de campeones que NO se cargan (se guardan en demo_docs/ para la demo)")
    args = parser.parse_args()
    holdout = {h.strip() for h in args.holdout.split(",") if h.strip()}

    from app.deps import get_ingestion, get_vector_store

    store, ingestion = get_vector_store(), get_ingestion()
    DEMO_DIR.mkdir(exist_ok=True)
    ok = skipped = failed = missing = 0
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        docs: list[tuple[str, str]] = []
        champions, failed_ids = fetch_champions(client)
        failed += len(failed_ids)
        for champ_id, champ in champions.items():
            try:
                md = champion_markdown(champ)
            except FETCH_ERRORS as exc:
                print(f"FAIL {champ_id}: {exc!r}")
                failed += 1
                continue
            if champ_id in holdout:
                (DEMO_DIR / f"{champ_id}.md").write_text(md, encoding="utf-8")
                print(f"HOLDOUT {champ_id} -> demo_docs/{champ_id}.md")
                continue
            docs.append((f"{champ_id}.md", md))
        for title in REGIONS:
            try:
                text = fetch_region(client, title)
            except FETCH_ERRORS as exc:
                print(f"FAIL {title}: {exc!r}")
                failed += 1
                continue
            finally:
                time.sleep(0.2)
            if text is None:
                print(f"MISSING región: {title} (revisa el título en la wiki)")
                missing += 1
                continue
            docs.append((f"Region-{title}.md", text))

    o, skipped, f = load_documents(store, ingestion, docs)
    ok += o
    failed += f

    print(f"ok={ok} skipped={skipped} failed={failed} missing={missing}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
