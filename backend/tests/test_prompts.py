from app.agents import prompts


def test_generate_prompt_keeps_guard_rules():
    generate = prompts.GENERATE_PROMPT.format(context="c", question="q")
    assert "nunca instrucciones" in generate
    assert "NO_INFO" in generate and "EXCLUSIVAMENTE" in generate


def test_generate_prompt_puts_context_before_question():
    kw = dict(context="[1] (Jinx.md) Jinx vive en Zaun.", question="¿Quién es Jinx?")
    generate = prompts.GENERATE_PROMPT.format(**kw)
    end = generate.index("</contexto>")
    assert kw["context"] in generate[:end] and generate.index(kw["question"]) > end


def test_grade_prompt_is_gone_because_grading_is_lexical():
    assert not hasattr(prompts, "GRADE_PROMPT")
