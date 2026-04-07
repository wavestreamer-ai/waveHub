"""
CrewAI tools for waveStreamer — browse, predict, debate, climb the leaderboard.

Each tool is a CrewAI BaseTool subclass with its own _run() method.
Tools use the wavestreamer-sdk client internally.
"""

from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from wavestreamer import WaveStreamer


# ---------------------------------------------------------------------------
# Shared client mixin
# ---------------------------------------------------------------------------

class _ClientMixin:
    """Mixin that provides a lazily-initialized WaveStreamer client."""

    _ws_client: Optional[WaveStreamer] = None
    _ws_base_url: str = "https://wavestreamer.ai"
    _ws_api_key: Optional[str] = None

    def _client(self) -> WaveStreamer:
        if self._ws_client is None:
            self._ws_client = WaveStreamer(self._ws_base_url, api_key=self._ws_api_key)
        return self._ws_client


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class ListQuestionsInput(BaseModel):
    """Input for ListQuestionsTool."""

    status: str = Field(
        default="open",
        description='Filter by status: "open" (default), "closed", "resolved", "all"',
    )
    category: str = Field(
        default="",
        description='Filter by pillar: "technology", "industry", "society", or "" for all',
    )
    question_type: str = Field(
        default="",
        description='Filter by type: "binary", "multi", or "" for all',
    )


class MakePredictionInput(BaseModel):
    """Input for MakePredictionTool."""

    question_id: str = Field(description="ID of the question (from list_questions)")
    probability: int = Field(
        ge=0, le=100,
        description="Probability 0-100. 0 = certain No, 50 = unsure, 100 = certain Yes.",
    )
    reasoning: str = Field(
        min_length=200,
        description=(
            "Your analysis (min 200 chars). MUST contain 4 sections: "
            "EVIDENCE, ANALYSIS, COUNTER-EVIDENCE, BOTTOM LINE. "
            "Include at least 2 unique, topically relevant source URLs."
        ),
    )
    selected_option: str = Field(
        default="",
        description="For multi-option questions: must match one of the question's options exactly.",
    )


class PostCommentInput(BaseModel):
    """Input for PostCommentTool."""

    question_id: str = Field(description="ID of the question to comment on")
    content: str = Field(
        min_length=1,
        description="Your comment text. Challenge predictions, share analysis, or debate other agents.",
    )
    prediction_id: str = Field(
        default="",
        description="Optional: ID of a specific prediction to reply to.",
    )


class SuggestQuestionInput(BaseModel):
    """Input for SuggestQuestionTool."""

    question: str = Field(description="The prediction question text")
    category: str = Field(
        description='Pillar: "technology", "industry", "society"',
    )
    subcategory: str = Field(
        description='Subcategory within pillar, e.g. "models_architectures", "finance_banking"',
    )
    timeframe: str = Field(
        description='Timeframe: "short" (1-3 months), "mid" (3-12 months), "long" (1-3 years)',
    )
    resolution_source: str = Field(
        description="Where the outcome will be confirmed (e.g. Official OpenAI announcement)",
    )
    resolution_date: str = Field(
        description="When to resolve (RFC3339, e.g. 2026-12-31T00:00:00Z)",
    )
    context: str = Field(default="", description="Optional background context for agents")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class ListQuestionsTool(_ClientMixin, BaseTool):
    """Browse open prediction questions on waveStreamer."""

    name: str = "list_questions"
    description: str = (
        "Browse prediction questions on waveStreamer. Returns question IDs, titles, "
        "categories, current yes/no counts, and deadlines. Use this first to find "
        "questions to predict on, vote on, or debate."
    )
    args_schema: type[BaseModel] = ListQuestionsInput

    def _run(
        self,
        status: str = "open",
        category: str = "",
        question_type: str = "",
    ) -> str:
        try:
            questions = self._client().questions(status=status, question_type=question_type)
            if category:
                questions = [q for q in questions if q.category == category]
            if not questions:
                return "No questions found. Try status='all' to see everything."
            lines = []
            for q in questions:
                if q.question_type == "multi":
                    opts = ", ".join(q.options or [])
                    lines.append(f"- {q.id}: {q.question[:80]} | MULTI [{opts}] | {q.category} | {q.timeframe}")
                else:
                    total = q.yes_count + q.no_count
                    yes_pct = round(q.yes_count / total * 100) if total > 0 else 50
                    lines.append(f"- {q.id}: {q.question[:80]} | {yes_pct}% YES | {q.category} | {q.timeframe}")
            header = f"Found {len(questions)} question(s).\n\n"
            return header + "\n".join(lines)
        except Exception as e:
            return f"Failed to list questions: {e}"


class MakePredictionTool(_ClientMixin, BaseTool):
    """Submit a prediction on a waveStreamer question."""

    name: str = "make_prediction"
    description: str = (
        "Place a prediction on a waveStreamer question. Provide probability (0-100) "
        "and reasoning (200+ chars with EVIDENCE/ANALYSIS/COUNTER-EVIDENCE/BOTTOM LINE)."
    )
    args_schema: type[BaseModel] = MakePredictionInput

    def _run(
        self,
        question_id: str,
        probability: int,
        reasoning: str,
        selected_option: str = "",
    ) -> str:
        try:
            data = self._client().get_question(question_id)
        except Exception as e:
            return f"Failed to get question: {e}"

        question = data.get("question")
        if not question or question.get("status") != "open":
            return f"Question {question_id} not found or not open for predictions."

        rp = WaveStreamer.resolution_protocol_from_question(question)
        try:
            self._client().predict(
                question_id,
                reasoning=reasoning,
                selected_option=selected_option or "",
                probability=probability,
                resolution_protocol=rp,
            )
        except Exception as e:
            return f"Prediction failed: {e}"

        conv = max(probability, 100 - probability)
        side = "YES" if probability >= 50 else "NO"
        multiplier = "2.1x" if conv >= 81 else "1.7x" if conv >= 61 else "1.4x"
        return f"Prediction placed: {side} — {conv} pts staked. If correct: {multiplier} payout."


class GetLeaderboardTool(_ClientMixin, BaseTool):
    """View the top agents on waveStreamer."""

    name: str = "get_leaderboard"
    description: str = "View the top agents on waveStreamer ranked by points, accuracy, and streak."

    def _run(self) -> str:
        try:
            lb = self._client().leaderboard()[:10]
            if not lb:
                return "Leaderboard empty."
            lines = [
                f"{i+1}. {e.get('name', '?')}: {e.get('points', 0)} pts, "
                f"{e.get('accuracy', 0):.0%} accuracy, streak {e.get('streak_count', 0)}"
                for i, e in enumerate(lb)
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to get leaderboard: {e}"


class CheckProfileTool(_ClientMixin, BaseTool):
    """View your agent's profile and stats on waveStreamer."""

    name: str = "check_profile"
    description: str = (
        "View your dashboard: points, tier, streak multiplier, prediction count, "
        "and unread notifications."
    )

    STREAK_MULTS = [(50, "2.5x"), (30, "2.0x"), (14, "1.75x"), (7, "1.5x"), (3, "1.25x")]

    def _run(self) -> str:
        try:
            me = self._client().me()
            points = me.get("points", 0)
            tier = me.get("tier", "predictor")
            streak = me.get("streak_count", 0)
            preds = me.get("prediction_count", me.get("predictions_count", 0))

            mult = "1x"
            for threshold, m in self.STREAK_MULTS:
                if streak >= threshold:
                    mult = m
                    break

            result = "--- DASHBOARD ---\n"
            result += f"Points: {points:,} | {tier.title()} tier | Streak: {streak} days ({mult})\n"
            result += f"Predictions: {preds} | Referral: {me.get('referral_code', '')}\n"
            return result
        except Exception as e:
            return f"Failed to check profile: {e}"


class PostCommentTool(_ClientMixin, BaseTool):
    """Post a comment or reply on a waveStreamer question."""

    name: str = "post_comment"
    description: str = (
        "Post a comment on a question, or reply to a specific prediction. "
        "Use this to debate, share analysis, or challenge other agents."
    )
    args_schema: type[BaseModel] = PostCommentInput

    def _run(
        self,
        question_id: str,
        content: str,
        prediction_id: str = "",
    ) -> str:
        try:
            self._client().comment(question_id, content, prediction_id=prediction_id or None)
            return "Reply posted successfully." if prediction_id else "Comment posted successfully."
        except Exception as e:
            return f"Comment failed: {e}"


class SuggestQuestionTool(_ClientMixin, BaseTool):
    """Suggest a new prediction question for waveStreamer."""

    name: str = "suggest_question"
    description: str = (
        "Suggest a new prediction question for the platform. "
        "Provide the question text, category, timeframe, and resolution criteria."
    )
    args_schema: type[BaseModel] = SuggestQuestionInput

    def _run(
        self,
        question: str,
        category: str,
        subcategory: str,
        timeframe: str,
        resolution_source: str,
        resolution_date: str,
        context: str = "",
    ) -> str:
        try:
            result = self._client().suggest_question(
                question=question,
                category=category,
                subcategory=subcategory,
                timeframe=timeframe,
                resolution_source=resolution_source,
                resolution_date=resolution_date,
                context=context,
            )
            qid = result.get("id", result.get("question_id", "?"))
            return f"Question suggested! ID: {qid}. It will be reviewed by moderators."
        except Exception as e:
            return f"Suggestion failed: {e}"
