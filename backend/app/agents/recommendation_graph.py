"""LangGraph 分析師與風控審查員的可重試推薦狀態機。"""

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.recommendation import (
    DailyRecommendationDraft,
    RecommendationAuditResult,
)

Analyst = Callable[[dict[str, Any], str], DailyRecommendationDraft]
Auditor = Callable[[DailyRecommendationDraft, dict[str, Any]], RecommendationAuditResult]
MAX_RETRIES = 2


class RecommendationState(TypedDict, total=False):
    context: dict[str, Any]
    audit_data: dict[str, Any]
    audit_feedback: str
    retry_count: int
    draft: DailyRecommendationDraft
    audit_approved: bool
    audit_note: str


def build_recommendation_graph(analyst: Analyst, auditor: Auditor):
    """建置 StateGraph；分析與審查 callable 可在測試中替換。"""

    def analyst_node(state: RecommendationState) -> dict[str, Any]:
        draft = analyst(state["context"], state.get("audit_feedback", ""))
        return {"draft": draft}

    def risk_auditor_node(state: RecommendationState) -> dict[str, Any]:
        result = auditor(state["draft"], state.get("audit_data", {}))
        failed_attempts = state.get("retry_count", 0) + (0 if result.approved else 1)
        return {
            "audit_approved": result.approved,
            "audit_feedback": result.feedback,
            "audit_note": result.note,
            "retry_count": failed_attempts,
        }

    def should_retry(state: RecommendationState) -> str:
        if state.get("audit_approved", False) or state.get("retry_count", 0) >= MAX_RETRIES:
            return END
        return "analyst_node"

    graph = StateGraph(RecommendationState)
    graph.add_node("analyst_node", analyst_node)
    graph.add_node("risk_auditor_node", risk_auditor_node)
    graph.add_edge(START, "analyst_node")
    graph.add_edge("analyst_node", "risk_auditor_node")
    graph.add_conditional_edges("risk_auditor_node", should_retry)
    return graph.compile()
