"""Carga el corpus compartido: campeones (Data Dragon, es_MX) y regiones (wiki de LoL en español)."""
import argparse
import html
import re
import time
from pathlib import Path

import httpx

DDRAGON = "https://ddragon.leagueoflegends.com"
LOCALE = "es_MX"
WIKI_API = "https://leagueoflegends.fandom.com/es/api.php"
REGIONS = [
    "Demacia", "Noxus", "Piltóver", "Zaun", "Freljord", "Jonia", "Islas de la Sombra",
    "Targon", "Shurima", "Aguas Estancadas", "Ixtal", "El Vacío", "Bandle City",
]
DEMO_DIR = Path(__file__).resolve().parents[1] / "demo_docs"


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


def fetch_champions(client: httpx.Client) -> dict[str, dict]:
    version = client.get(f"{DDRAGON}/api/versions.json").json()[0]
    index = client.get(f"{DDRAGON}/cdn/{version}/data/{LOCALE}/champion.json").json()["data"]
    out = {}
    for champ_id in index:
        detail = client.get(f"{DDRAGON}/cdn/{version}/data/{LOCALE}/champion/{champ_id}.json").json()
        out[champ_id] = detail["data"][champ_id]
        time.sleep(0.05)
    return out


def fetch_region(client: httpx.Client, title: str) -> str | None:
    # La wiki en español no tiene TextExtracts: se usa action=parse y se limpia el HTML.
    params = {"action": "parse", "prop": "text", "format": "json", "redirects": 1,
              "page": title, "disablelimitreport": 1}
    data = client.get(WIKI_API, params=params).json()
    if "parse" not in data:
        return None
    raw = re.sub(r"(?is)<style.*?</style>|<script.*?</script>", "", data["parse"]["text"]["*"])
    text = strip_html(raw)
    return f"# {title}\n\n{text}" if len(text) > 200 else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", default="Briar,Hwei",
                        help="IDs de campeones que NO se cargan (se guardan en demo_docs/ para la demo)")
    args = parser.parse_args()
    holdout = {h.strip() for h in args.holdout.split(",") if h.strip()}

    from app.deps import get_ingestion, get_vector_store

    store, ingestion = get_vector_store(), get_ingestion()
    DEMO_DIR.mkdir(exist_ok=True)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        docs: list[tuple[str, str]] = []
        for champ_id, champ in fetch_champions(client).items():
            md = champion_markdown(champ)
            if champ_id in holdout:
                (DEMO_DIR / f"{champ_id}.md").write_text(md, encoding="utf-8")
                print(f"HOLDOUT {champ_id} -> demo_docs/{champ_id}.md")
                continue
            docs.append((f"{champ_id}.md", md))
        for title in REGIONS:
            text = fetch_region(client, title)
            if text is None:
                print(f"MISSING región: {title} (revisa el título en la wiki)")
                continue
            docs.append((f"Region-{title}.md", text))

    for name, text in docs:
        if store.find_shared(name):
            print(f"SKIP {name} (ya existe)")
            continue
        doc_id = store.create_document(None, name, "md")
        ingestion.ingest(doc_id, name, text.encode("utf-8"))
        print(f"OK {name}")


if __name__ == "__main__":
    main()
