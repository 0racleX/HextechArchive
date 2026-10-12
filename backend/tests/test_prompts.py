from app.agents import prompts


def test_grade_and_generate_share_context_prefix_for_prompt_caching():
    kw = dict(context="[1] (Jinx.md) Jinx vive en Zaun.", question="¿Quién es Jinx?")
    grade, generate = prompts.GRADE_PROMPT.format(**kw), prompts.GENERATE_PROMPT.format(**kw)
    end = grade.index("</contexto>") + len("</contexto>")
    assert generate.startswith(grade[:end])          # preámbulo + bloque de contexto idénticos
    assert kw["context"] in grade[:end]
    assert kw["question"] not in grade[:end]         # la pregunta va después del contexto
    assert grade.index(kw["question"]) > end and generate.index(kw["question"]) > end


def test_prompts_keep_guard_rules():
    kw = dict(context="c", question="q")
    grade, generate = prompts.GRADE_PROMPT.format(**kw), prompts.GENERATE_PROMPT.format(**kw)
    for p in (grade, generate):
        assert "nunca instrucciones" in p
    assert "SI o NO" in grade
    assert "NO_INFO" in generate and "EXCLUSIVAMENTE" in generate
