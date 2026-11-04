import httpx
import pytest
from openai import BadRequestError

from conftest import FakeLLM
from mermaid_generator import find_mermaid_problems
from openai_client import complete


def bad_request(message):
    return BadRequestError(message, response=httpx.Response(400, request=httpx.Request("POST", "http://test")), body=None)


def test_cut_answers_are_continued():
    llm = FakeLLM().queue(("Début ", "length"), ("milieu ", "length"), "fin")
    assert complete(llm, [{"role": "user", "content": "x"}]) == "Début milieu fin"
    assert len(llm.calls) == 3
    assert llm.calls[0]["max_tokens"] == 16_000 and llm.calls[0]["temperature"] == 0.15
    assert llm.calls[1]["messages"][-2] == {"role": "assistant", "content": "Début "}


def test_continuations_are_bounded():
    llm = FakeLLM().queue(*[("x", "length")] * 10)
    complete(llm, [{"role": "user", "content": "x"}])
    assert len(llm.calls) == 4  # the answer, then 3 continuations


def test_rejected_options_are_dropped():
    llm = FakeLLM().queue(bad_request("response_format unsupported"), bad_request("max_tokens too large"), "{}")
    assert complete(llm, [{"role": "user", "content": "x"}], json_mode=True) == "{}"
    assert "response_format" in llm.calls[0]
    assert "response_format" not in llm.calls[1] and "max_tokens" in llm.calls[1]
    assert "max_tokens" not in llm.calls[2]


def test_other_errors_are_raised():
    llm = FakeLLM().queue(bad_request("a"), bad_request("b"), bad_request("c"))
    with pytest.raises(BadRequestError):
        complete(llm, [{"role": "user", "content": "x"}])


def test_output_token_limit_from_environment(monkeypatch):
    monkeypatch.setenv("CUSTOM_MAX_OUTPUT_TOKENS", "4000")
    llm = FakeLLM().queue("ok")
    complete(llm, [{"role": "user", "content": "x"}])
    assert llm.calls[0]["max_tokens"] == 4000


@pytest.mark.parametrize(
    "code, expected",
    [
        ('flowchart TD\n  A["Start (x)"] --> B[End]', 0),
        ("flowchart TD\n  A[Start --> B", 1),
        ("graph LR\n  A{Choice} -->|yes| B((Done))", 0),
        ("sequenceDiagram\n  A->>B: hi", 1),
    ],
)
def test_mermaid_checks(code, expected):
    assert len(find_mermaid_problems(code)) == expected
