import json
from pathlib import Path

from scripts.run_eval import format_row, score

QUESTIONS = Path(__file__).parent / "eval" / "questions.json"


def test_questions_file_is_well_formed():
    rows = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    assert len(rows) == 20
    for item in rows:
        assert isinstance(item["q"], str) and item["q"].strip()
        assert item["expect"] in {"answer", "refuse"}
    assert {r["expect"] for r in rows} == {"answer", "refuse"}
    qs = [r["q"] for r in rows]
    assert len(qs) == len(set(qs))


def test_score_counts_matches():
    expected = ["answer", "refuse", "answer"]
    got = ["answer", "answer", "answer"]
    assert score(got, expected) == (2, 3)


def test_format_row_ok_and_fail():
    ok = format_row("answer", "answer", 0.71, "¿Quién es Jinx?")
    bad = format_row("refuse", "answer", 0.5, "x")
    assert ok.startswith("OK ") and "top_sim=0.71" in ok and "¿Quién es Jinx?" in ok
    assert bad.startswith("FAIL") and "esperado=refuse" in bad and "obtenido=answer" in bad
