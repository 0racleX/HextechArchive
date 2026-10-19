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


def test_generate_prompt_requires_bracketed_citations():
    generate = prompts.GENERATE_PROMPT.format(context="c", question="q")
    assert "[1]" in generate and "Cita cada dato" in generate
    assert "Usa solo los números" in generate  # no inventar citas fuera del contexto


def test_generate_prompt_answers_in_the_language_of_the_question():
    generate = prompts.GENERATE_PROMPT.format(context="c", question="q")
    assert "Responde en español" not in generate  # antes forzaba español aunque preguntaran en inglés
    assert "mismo idioma de la pregunta" in generate and "inglés" in generate
    assert "NO_INFO (sin traducirlo" in generate  # el centinela de rechazo no cambia con el idioma


def test_generate_prompt_formats_an_english_question():
    kw = dict(context="[1] (Jinx.md) Jinx es la hermana menor de Vi.", question="Who is Jinx's sister?")
    generate = prompts.GENERATE_PROMPT.format(**kw)
    assert generate.rstrip().endswith("Respuesta:")
    assert generate.index(kw["question"]) > generate.index("</contexto>")


def test_grade_prompt_is_gone_because_grading_is_lexical():
    assert not hasattr(prompts, "GRADE_PROMPT")
