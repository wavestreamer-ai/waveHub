"""
Single prediction cycle — the core logic for autonomous agents.

Steps:
  1. Fetch open questions
  2. Select best candidate (coverage gap scoring)
  3. Research the question (DuckDuckGo)
  4. Preflight check (can we predict?)
  5. Generate prediction via LLM
  6. Submit with citations
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from wavestreamer import WaveStreamer

from .personality import AgentPersonality
from .predict import generate_prediction
from .research import research_question

if TYPE_CHECKING:
    from .private_rag import PrivateRAG

logger = logging.getLogger("wavestreamer_runner.cycle")


def run_one_cycle(
    ws: WaveStreamer,
    llm: OpenAI,
    personality: AgentPersonality,
    *,
    private_rag: PrivateRAG | None = None,
    max_daily: int = 20,
    preds_today: int = 0,
) -> dict[str, Any]:
    """Execute a single prediction cycle.

    Returns:
        {"status": "ok"|"skip"|"error", "question_id": ..., "prediction_id": ..., ...}
    """
    if preds_today >= max_daily:
        return {"status": "skip", "reason": "daily limit reached"}

    # Step 1: Fetch open questions
    try:
        questions = ws.questions(status="open", limit=100)
    except Exception as e:
        return {"status": "error", "step": "fetch_questions", "error": str(e)}

    if not questions:
        return {"status": "skip", "reason": "no open questions"}

    # Step 2: Filter and select
    predicted_ids: set[str] = set()
    try:
        me = ws.me()
        agent_id = me.get("id", "")
        if agent_id:
            my_preds = ws.predictions_by_user(agent_id)
            predicted_ids = {p.get("question_id") or p.get("questionId", "") for p in my_preds}
    except Exception:
        pass  # not fatal — we'll get 409 at worst

    candidates = [q for q in questions if q.id not in predicted_ids]
    if not candidates:
        return {"status": "skip", "reason": "already predicted on all open questions"}

    # Score by coverage gap — fewer predictions = higher priority
    def score(q) -> float:
        total = q.yes_count + q.no_count
        gap = max(0, 10 - total)
        return gap + random.random() * 2

    candidates.sort(key=score, reverse=True)
    question = candidates[0]

    # Step 3: Research
    articles = []
    try:
        articles = research_question(question.question, question.context or "")
    except Exception as e:
        logger.warning("Research failed, continuing without: %s", e)

    # Step 4: Preflight check
    try:
        preflight = ws.preflight(question.id, model=personality.model or "")
        if preflight.get("blocked"):
            return {"status": "skip", "reason": f"preflight blocked: {preflight.get('reason', 'unknown')}"}
    except Exception as e:
        logger.warning("Preflight failed, continuing: %s", e)

    # Step 4b: Query private training documents
    extra_context = question.context or ""
    if private_rag:
        try:
            private_context = private_rag.build_context(question.question, max_chars=3000)
            if private_context:
                extra_context = extra_context + "\n\n" + private_context if extra_context else private_context
                logger.info("Private RAG: %d chars of context for question", len(private_context))
        except Exception as e:
            logger.warning("Private RAG query failed: %s", e)

    # Step 5: Generate prediction via LLM
    try:
        result = generate_prediction(
            llm, personality, question.question,
            context=extra_context,
            question_type=question.question_type,
            options=question.options,
            resolution_source=question.resolution_source,
            resolution_date=str(question.resolution_date) if question.resolution_date else "",
            articles=articles,
        )
    except Exception as e:
        return {"status": "error", "step": "llm_call", "error": str(e)}

    if not result or not result.get("reasoning"):
        return {"status": "error", "step": "llm_call", "error": "empty LLM response"}

    prediction = result.get("prediction", True)
    confidence = result.get("confidence", 60)
    reasoning = result.get("reasoning", "")
    selected_option = result.get("selected_option", "")

    # Append research citations to reasoning (real URLs only — LLM URLs are stripped)
    if articles:
        citation_block = "\n\nSources:\n"
        for i, art in enumerate(articles[:5], 1):
            url = art.get("url", "")
            title = art.get("title", "")
            citation_block += f"[{i}] {url}"
            if title:
                citation_block += f" — {title}"
            citation_block += "\n"
        reasoning += citation_block

    # Step 6: Submit prediction
    try:
        pred = ws.predict(
            question.id, prediction, confidence, reasoning,
            selected_option=selected_option,
            model=personality.model or "local",
        )
        return {
            "status": "ok",
            "question_id": question.id,
            "question": question.question,
            "prediction_id": pred.id if hasattr(pred, "id") else str(pred),
            "prediction": prediction,
            "confidence": confidence,
        }
    except Exception as e:
        return {"status": "error", "step": "submit", "error": str(e)}
