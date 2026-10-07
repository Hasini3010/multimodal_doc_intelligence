from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.query_pipeline import ask
from app.schemas import AskResponse, Claim, Citation


def test_ask_abstains_without_index(monkeypatch, tmp_path):
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "empty"))
    from app.config import get_settings

    get_settings.cache_clear()
    resp = ask("What is Q4 efficiency?")
    assert resp.abstained
    assert "not found" in resp.answer.lower()


@patch("agent.query_pipeline.get_llm_client")
@patch("agent.query_pipeline.load_document_index")
@patch("agent.query_pipeline.plan_question")
@patch("agent.query_pipeline.hybrid_search")
@patch("agent.query_pipeline.rerank_hits")
@patch("agent.query_pipeline.answer_question")
@patch("agent.query_pipeline.verify_response")
def test_ask_wires_pipeline(
    mock_verify,
    mock_answer,
    mock_rerank,
    mock_hybrid,
    mock_plan,
    mock_load,
    mock_client,
):
    mock_client.return_value = MagicMock()
    mock_load.return_value = MagicMock(elements=[MagicMock(element_id="e1")])
    mock_plan.return_value = [MagicMock(text="q", modality="any", needs_math=False)]
    hit = MagicMock(element_id="e1", score=0.5, element=MagicMock())
    mock_hybrid.return_value = [hit]
    mock_rerank.return_value = [hit]
    mock_answer.return_value = AskResponse(answer="89.2", confidence=0.8, claims=[])
    mock_verify.return_value = AskResponse(
        answer="89.2",
        confidence=0.8,
        claims=[
            Claim(
                text="Q4 efficiency",
                citations=[Citation(doc_id="d", page=1, element_id="e1")],
            )
        ],
    )
    resp = ask("Q4 efficiency?")
    assert resp.answer == "89.2"
    assert len(resp.claims) == 1
