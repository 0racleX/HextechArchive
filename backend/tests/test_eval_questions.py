import json
from pathlib import Path

import pytest

from scripts.run_eval import format_row, score, should_fail

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


def test_format_row_none_top_is_na():
    assert "top_sim=n/a" in format_row("refuse", "refuse", None, "q")


def test_format_row_error_detail():
    row = format_row("answer", "ERROR", None, "q", "ConnectionError: boom")
    assert row.startswith("FAIL") and "ConnectionError: boom" in row


def test_score_all_correct_and_empty():
    assert score(["answer", "refuse"], ["answer", "refuse"]) == (2, 2)
    assert score([], []) == (0, 0)


def test_score_mismatched_lengths_raise():
    with pytest.raises(AssertionError):
        score(["answer"], ["answer", "refuse"])


def test_should_fail_cases():
    exp = ["answer"] * 9 + ["refuse"]
    assert should_fail(list(exp), exp) == []
    assert should_fail(["answer"] * 10, exp)  # refuse respondida
    assert should_fail(["ERROR"] + exp[1:], exp)  # error + 90%
    assert should_fail(["refuse"] * 2 + exp[2:], exp)  # 80% < 85%
