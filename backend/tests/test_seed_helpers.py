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
