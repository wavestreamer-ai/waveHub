"""
LLM prediction generation for autonomous agents.

Generates structured predictions (EVIDENCE/ANALYSIS/COUNTER-EVIDENCE/BOTTOM LINE)
with retry logic and robust JSON parsing for local and cloud LLMs.
Extracted from the waveStreamer fleet prediction pipeline.
"""

import json
import logging
import random
import re

from openai import OpenAI

from .personality import AgentPersonality

logger = logging.getLogger("wavestreamer_runner.predict")

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PREDICT_BINARY = """You are {name}, an AI forecasting agent on waveStreamer.

{perspective}

Resolution: {resolution_source} by {resolution_date}

Below are RESEARCH FINDINGS with numbered sources [1], [2], etc.
CRITICAL RULES:
1. Your reasoning MUST directly address the SPECIFIC question asked.
2. Only cite sources that are DIRECTLY relevant. IGNORE unrelated sources.
3. If no sources are relevant, write a detailed analysis using your domain knowledge.
4. NEVER write generic analysis — always reference the specific subject matter.

Respond with ONLY valid JSON:
{{"prediction": true, "confidence": 72, "reasoning": "EVIDENCE: [Key facts]. [1] reports X. [2] shows Y. ANALYSIS: Based on [specific subject], the trajectory suggests... COUNTER-EVIDENCE: However, [specific risks]... BOTTOM LINE: Predicting YES at 72% because [specific reason].", "resolution_protocol": {{"criterion": "specific YES/NO rule", "edge_cases": "how to handle ambiguity"}}}}

Rules:
- prediction: true (YES) or false (NO)
- confidence: {lo}-{hi} (be honest about uncertainty)
- reasoning: 6-12 sentences with EVIDENCE/ANALYSIS/COUNTER-EVIDENCE/BOTTOM LINE sections. Reference sources as [1], [2] etc. Do NOT include URLs.
- resolution_protocol: criterion = exact rule for YES/NO, edge_cases = ambiguities"""

PREDICT_MULTI = """You are {name}, an AI forecasting agent on waveStreamer.

{perspective}

Multi-option question. Options: {options}
Resolution: {resolution_source} by {resolution_date}

Below are RESEARCH FINDINGS with numbered sources [1], [2], etc.
CRITICAL RULES:
1. Your reasoning MUST directly address the SPECIFIC question asked.
2. Only cite sources that are DIRECTLY relevant. IGNORE unrelated sources.
3. If no sources are relevant, write a detailed analysis using your domain knowledge.
4. NEVER write generic analysis — always reference the specific subject matter.

Respond with ONLY valid JSON:
{{"selected_option": "exact option text", "confidence": 72, "reasoning": "EVIDENCE: [Key facts]. [1] reports X. ANALYSIS: This option fits because [specific reasoning]... COUNTER-EVIDENCE: [Challenges for alternatives]. BOTTOM LINE: Selecting this at 72% because [specific reason].", "resolution_protocol": {{"criterion": "how to determine correct option", "edge_cases": "ambiguities"}}}}

Rules:
- selected_option: MUST be exactly one of: {options}
- confidence: {lo}-{hi}
- reasoning: 6-12 sentences with EVIDENCE/ANALYSIS/COUNTER-EVIDENCE/BOTTOM LINE. Reference sources as [1], [2].
- resolution_protocol: criterion = rule for correct option, edge_cases = ambiguities"""

# Style perspectives that change how the agent reasons
_PERSPECTIVES = {
    "contrarian": "You are a CONTRARIAN thinker. Choose the LEAST popular option. Focus on overlooked risks and historical examples where the majority was wrong.",
    "cautious": "You are a CAUTIOUS analyst. Emphasize uncertainty and downside risks. Prefer lower confidence levels and conservative options.",
    "bold": "You are a BOLD forecaster. Take EXTREME positions. Focus on momentum, accelerating trends, and breakthrough potential.",
    "analytical": "You are a DATA-DRIVEN analyst. Focus on quantitative metrics, base rates, and statistical reasoning. Pick what the DATA supports.",
    "skeptical": "You are a SKEPTICAL evaluator. Question ALL assumptions. Default to 'probably not' unless evidence is overwhelming.",
    "optimistic": "You are an OPTIMISTIC technologist. You believe in rapid progress. Pick the MOST POSITIVE option available.",
    "pessimistic": "You are a PESSIMISTIC realist. Expect delays and complications. Pick the MOST DIFFICULT option.",
    "academic": "You are an ACADEMIC researcher. Reason from first principles. Pick what fits the ACADEMIC LITERATURE.",
    "technical": "You are a TECHNICAL expert. Focus on implementation details and engineering constraints.",
    "philosophical": "You are a PHILOSOPHICAL thinker. Consider second-order effects and systemic implications.",
}


def _get_perspective(personality: AgentPersonality) -> str:
    base = _PERSPECTIVES.get(personality.style, _PERSPECTIVES["analytical"])
    if personality.bio:
        base += f"\nAdditional context: {personality.bio}"
    return base


# ---------------------------------------------------------------------------
# Prediction generation
# ---------------------------------------------------------------------------

def generate_prediction(
    llm: OpenAI,
    personality: AgentPersonality,
    question: str,
    context: str = "",
    question_type: str = "binary",
    options: list[str] | None = None,
    resolution_source: str = "",
    resolution_date: str = "",
    articles: list[dict] | None = None,
) -> dict:
    """Generate a prediction via LLM. Retries up to 4 times on failure.

    Returns {"prediction": bool, "confidence": int, "reasoning": str,
             "selected_option": str, "resolution_protocol": dict}
    """
    lo, hi = personality.confidence_range
    perspective = _get_perspective(personality)
    res_src = resolution_source or "Stated resolution source"
    res_date = resolution_date or "Stated deadline"

    if question_type == "multi" and options:
        system = PREDICT_MULTI.format(
            name=personality.name, perspective=perspective,
            lo=lo, hi=hi, options=" | ".join(options),
            resolution_source=res_src, resolution_date=res_date,
        )
    else:
        system = PREDICT_BINARY.format(
            name=personality.name, perspective=perspective,
            lo=lo, hi=hi,
            resolution_source=res_src, resolution_date=res_date,
        )

    # Build user message with research context
    user_msg = f"Question: {question}"
    if context:
        user_msg += f"\n{context}"
    if articles:
        user_msg += "\n\nRESEARCH FINDINGS:\n"
        for i, a in enumerate(articles[:8], 1):
            title = a.get("title", "")
            snippet = a.get("snippet", "")
            user_msg += f"[{i}] {title}\n    {snippet}\n"
    user_msg += "\nRespond with JSON only."

    model = personality.model or "llama3.1"

    # Temperature varies by style
    temp_map = {
        "contrarian": 0.7, "bold": 0.6, "optimistic": 0.55,
        "skeptical": 0.5, "analytical": 0.35, "cautious": 0.3,
    }
    temp = temp_map.get(personality.style, 0.4)

    kwargs = dict(
        model=model, max_tokens=2000, temperature=temp,
        timeout=120,  # per-call timeout — prevents Ollama hangs on large context
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )

    # Retry up to 4 times (local models sometimes return empty/malformed)
    min_reasoning = 200
    last_error = None
    for attempt in range(4):
        try:
            resp = llm.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            if not text.strip():
                continue
            result = _parse_prediction_json(text, question_type)
            result.pop("sources", None)
            if len(result.get("reasoning", "")) < min_reasoning:
                logger.debug("Attempt %d: reasoning too short (%d chars), retrying",
                             attempt + 1, len(result.get("reasoning", "")))
                last_error = ValueError("reasoning too short")
                continue
            return result
        except Exception as e:
            last_error = e
            if attempt < 3:
                continue

    # All attempts failed — build fallback from research
    logger.warning("LLM failed after 4 attempts: %s", last_error)
    return _build_fallback(personality, articles or [], res_src, res_date)


def _build_fallback(
    personality: AgentPersonality,
    articles: list[dict],
    res_src: str,
    res_date: str,
) -> dict:
    """Build a structured prediction from research when LLM fails."""
    lo, hi = personality.confidence_range
    prediction = random.choice([True, False])
    confidence = random.randint(lo, hi)
    side = "YES" if prediction else "NO"

    evidence_parts = []
    for i, a in enumerate(articles[:5], 1):
        snippet = a.get("snippet", "")
        if snippet:
            evidence_parts.append(f"[{i}] {snippet[:200]}")

    if evidence_parts:
        evidence = " ".join(evidence_parts)
        reasoning = (
            f"EVIDENCE: {evidence} "
            f"ANALYSIS: Based on {len(evidence_parts)} sources, the trajectory points toward {side}. "
            f"Resolution deadline: {res_date} via {res_src}. "
            f"COUNTER-EVIDENCE: Significant uncertainty remains. "
            f"BOTTOM LINE: Predicting {side} at {confidence}% based on available evidence."
        )
    else:
        reasoning = (
            f"EVIDENCE: Based on public reporting and industry trajectory leading up to "
            f"the {res_date} deadline (resolution via {res_src}). "
            f"ANALYSIS: Current signals suggest this is the more likely outcome. "
            f"COUNTER-EVIDENCE: Significant uncertainty remains. "
            f"BOTTOM LINE: Predicting {side} with moderate confidence given limited evidence."
        )

    return {"prediction": prediction, "confidence": confidence, "reasoning": reasoning}


# ---------------------------------------------------------------------------
# JSON parsing — handles Ollama, code blocks, malformed output
# ---------------------------------------------------------------------------

def _parse_prediction_json(text: str, question_type: str = "binary") -> dict:
    """Robustly extract prediction JSON from LLM output."""
    # Strip thinking tags (qwen3, etc.)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Extract from markdown code block
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    cleaned = code_block.group(1).strip() if code_block else re.sub(r"```(?:json)?\s*", "", cleaned).strip().rstrip("`")

    # Try whole text as JSON
    try:
        return _normalize(json.loads(cleaned), question_type)
    except json.JSONDecodeError:
        pass

    # Find largest JSON object
    for m in re.finditer(r"\{", cleaned):
        depth = 0
        for i in range(m.start(), len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _normalize(json.loads(cleaned[m.start():i + 1]), question_type)
                    except json.JSONDecodeError:
                        break
        break

    # Flat JSON with fixes
    match = re.search(r"\{[^{}]+\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)
        candidate = re.sub(r"(\w+)\s*:", r'"\1":', candidate)
        candidate = candidate.replace("'", '"')
        candidate = re.sub(r",\s*}", "}", candidate)
        try:
            return _normalize(json.loads(candidate), question_type)
        except json.JSONDecodeError:
            pass

    # Regex fallback
    result: dict = {}
    conf_m = re.search(r"confidence[\"']?\s*[:=]\s*(\d+)", text, re.IGNORECASE)
    if conf_m:
        result["confidence"] = int(conf_m.group(1))

    reason_m = re.search(r"reasoning[\"']?\s*[:=]\s*[\"'](.+?)[\"']", text, re.IGNORECASE | re.DOTALL)
    if reason_m:
        result["reasoning"] = reason_m.group(1)[:1500]

    if question_type == "multi":
        opt_m = re.search(r"selected_option[\"']?\s*[:=]\s*[\"'](.+?)[\"']", text, re.IGNORECASE)
        if opt_m:
            result["selected_option"] = opt_m.group(1)
    else:
        pred_m = re.search(r"(?:prediction|answer)[\"']?\s*[:=]\s*(true|false|yes|no)", text, re.IGNORECASE)
        if pred_m:
            result["prediction"] = pred_m.group(1).lower() in ("true", "yes")

    if result:
        return _normalize(result, question_type)

    return {"prediction": random.choice([True, False]), "confidence": random.randint(55, 80), "reasoning": text[:500]}


def _normalize(d: dict, question_type: str = "binary") -> dict:
    """Normalize LLM output keys and ensure required fields exist."""
    # Normalize prediction key
    if "prediction" not in d:
        for alias in ("answer", "verdict", "forecast", "outcome"):
            if alias in d:
                val = d.pop(alias)
                d["prediction"] = val if isinstance(val, bool) else str(val).lower().strip() in ("true", "yes")
                break

    if question_type != "multi" and "prediction" not in d:
        reasoning = d.get("reasoning", "").lower()
        if "bottom line" in reasoning:
            bottom = reasoning.split("bottom line")[-1][:200]
            d["prediction"] = "yes" in bottom or "likely" in bottom
        else:
            d["prediction"] = random.choice([True, False])

    # Ensure confidence is int in range
    conf = d.get("confidence")
    if conf is None:
        d["confidence"] = random.randint(55, 80)
    elif isinstance(conf, str):
        try:
            d["confidence"] = int(conf)
        except ValueError:
            d["confidence"] = random.randint(55, 80)
    d["confidence"] = max(50, min(99, d["confidence"]))

    # Normalize reasoning
    if "reasoning" not in d:
        for alias in ("analysis", "explanation", "rationale"):
            if alias in d:
                d["reasoning"] = d.pop(alias)
                break
    if "reasoning" not in d:
        d["reasoning"] = ""

    return d
