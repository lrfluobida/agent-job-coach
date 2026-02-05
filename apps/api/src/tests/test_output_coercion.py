from src.core.output_coercion import coerce_model_output, strip_code_fence


def test_coerce_code_fenced_json():
    text = '```json {"answer":"hi","citations":[{"id":"c1","quote":"q"}]} ```'
    answer, citations = coerce_model_output(text)
    assert answer == "hi"
    assert isinstance(citations, list)


def test_coerce_leading_json_token():
    text = '"json {\"answer\":\"ok\",\"citations\":[]}'
    answer, citations = coerce_model_output(text)
    assert answer == "ok"
    assert citations == []


def test_coerce_plain_text():
    text = "普通文本回答"
    answer, citations = coerce_model_output(text)
    assert answer == text
    assert citations == []
