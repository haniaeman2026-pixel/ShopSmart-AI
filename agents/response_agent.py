"""
Response Agent
Role: Customer Support Specialist
Responsibility: Generate a clear, helpful response grounded in retrieved information.
Crucial Rule: Avoid inventing answers when information is unavailable.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, AgentTrace
from .classifier_agent import ClassificationResult
from .knowledge_agent import KnowledgeResult, KnowledgeMatch


@dataclass
class ResponseResult:
    """Output structure returned by the Response Agent."""
    response_text: str
    is_grounded: bool
    grounding_source_id: Optional[str]
    category: str
    support_escalation_provided: bool
    related_faq_suggestions: List[Dict[str, str]] = field(default_factory=list)
    trace: Optional[AgentTrace] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_text": self.response_text,
            "is_grounded": self.is_grounded,
            "grounding_source_id": self.grounding_source_id,
            "category": self.category,
            "support_escalation_provided": self.support_escalation_provided,
            "related_faq_suggestions": self.related_faq_suggestions,
            "trace": self.trace.to_dict() if self.trace else None,
        }


class ResponseAgent(BaseAgent):
    """
    Specialized agent responsible for generating the final customer support answer.
    Enforces strict grounding against the knowledge base and transparently declines
    to invent answers when knowledge is unavailable.
    """

    SUPPORT_EMAIL = "support@shopsmart.example.com"
    SUPPORT_PHONE = "1-800-555-SHOP (09:00 - 18:00 EST)"

    AVAILABLE_TOPICS = [
        "Orders (placing, tracking, modifying, cancellation, invoices, confirmation)",
        "Payments (payment methods, card security, declines, COD, installments)",
        "Deliveries (shipping times, delays, express delivery, rates, international shipping)",
        "Returns (return policy, 30-day window, return shipping labels, conditions)",
        "Refunds (processing times, payout methods, store credit, discount adjustments)",
        "General Inquiries (support hours, customer service contact, account creation)",
    ]

    def __init__(self):
        super().__init__(
            name="Response Agent",
            role="Customer Support Specialist",
            responsibility="Generate a clear, helpful response grounded in retrieved information",
        )

    def _generate_grounded_response(
        self,
        customer_question: str,
        match: KnowledgeMatch,
        related_matches: List[KnowledgeMatch],
    ) -> str:
        """
        Synthesizes a polite, customer-centric response strictly grounded in the FAQ data.
        """
        parts = []
        # Polite opening acknowledging the topic
        parts.append(f"Hello! Thank you for reaching out regarding **{match.category.capitalize()}**.")
        parts.append("")
        
        # Grounded answer directly from verified knowledge base
        parts.append(match.answer)
        
        # Policy condition / important requirement if present
        if match.conditions:
            parts.append("")
            parts.append(f"> **Important Policy Notice:** {match.conditions}")
            
        # Suggested related topics if available
        if related_matches:
            parts.append("")
            parts.append("**Related Information You Might Find Helpful:**")
            for rel in related_matches[:2]:
                parts.append(f"- *{rel.question}* (Reference: {rel.id})")

        # Standard helpful closing
        parts.append("")
        parts.append(
            f"If you need further assistance with your specific order, please feel free to reach "
            f"our customer care team at {self.SUPPORT_EMAIL} or call {self.SUPPORT_PHONE}."
        )

        return "\n".join(parts)

    def _generate_unsupported_response(
        self,
        customer_question: str,
        reason: str,
        category: Optional[str] = None,
    ) -> str:
        """
        Gracefully declines to answer when information is unavailable or out-of-scope.
        STRICT REQUIREMENT: Avoid inventing answers when information is unavailable.
        """
        parts = []
        parts.append("Hello! Thank you for contacting ShopSmart Customer Support.")
        parts.append("")

        if category and category in ["orders", "payments", "deliveries", "returns", "refunds", "general"]:
            parts.append(
                f"While your inquiry appears related to **{category.capitalize()}**, our predefined "
                f"FAQ knowledge base does not contain verified information specifically addressing: "
                f"\"*{customer_question.strip()}*\"."
            )
        else:
            parts.append(
                f"I apologize, but our predefined FAQ knowledge base does not contain verified information "
                f"to answer: \"*{customer_question.strip()}*\"."
            )

        parts.append("")
        parts.append(
            "To ensure you receive strictly accurate information, I avoid guessing or estimating "
            "unverified policies."
        )
        parts.append("")
        parts.append("**How We Can Help You Right Now:**")
        parts.append(
            f"1. **Speak with a Human Representative:** Email us at **{self.SUPPORT_EMAIL}** "
            f"or call **{self.SUPPORT_PHONE}**."
        )
        parts.append(
            f"2. **Explore Supported Topics:** I can provide instant, verified answers on:"
        )
        for topic in self.AVAILABLE_TOPICS:
            parts.append(f"   - {topic}")

        return "\n".join(parts)

    def process(
        self,
        customer_question: str,
        classification: ClassificationResult,
        knowledge: KnowledgeResult,
    ) -> ResponseResult:
        """
        Processes the outputs of previous agents and generates the final grounded customer answer.
        """
        start_time = time.perf_counter()

        # Case 1: Knowledge was successfully retrieved
        if knowledge.status in ["found", "low_confidence"] and knowledge.best_match is not None:
            best_match = knowledge.best_match
            response_text = self._generate_grounded_response(
                customer_question=customer_question,
                match=best_match,
                related_matches=knowledge.related_matches,
            )

            suggestions = [
                {"id": m.id, "question": m.question, "category": m.category}
                for m in knowledge.related_matches
            ]

            trace = self.create_trace(
                start_time=start_time,
                status="success",
                decision_summary=(
                    f"Generated fully grounded response using knowledge base record {best_match.id} "
                    f"({best_match.category})."
                ),
                details={
                    "grounding_faq_id": best_match.id,
                    "category": best_match.category,
                    "relevance_score": best_match.relevance_score,
                },
            )

            return ResponseResult(
                response_text=response_text,
                is_grounded=True,
                grounding_source_id=best_match.id,
                category=best_match.category,
                support_escalation_provided=True,
                related_faq_suggestions=suggestions,
                trace=trace,
            )

        # Case 2: Information unavailable or out of scope (Req 5: Avoid inventing answers)
        reason = (
            "No matching FAQ found in knowledge base"
            if classification.is_supported_category
            else "Question is outside of supported FAQ domains"
        )

        response_text = self._generate_unsupported_response(
            customer_question=customer_question,
            reason=reason,
            category=classification.category if classification.is_supported_category else None,
        )

        trace = self.create_trace(
            start_time=start_time,
            status="warning",
            decision_summary=(
                "Enforced grounding boundary: Information is unavailable in knowledge base. "
                "Provided transparent escalation rather than hallucinating an answer."
            ),
            details={
                "reason": reason,
                "category_classified": classification.category,
                "hallucination_prevented": True,
            },
        )

        return ResponseResult(
            response_text=response_text,
            is_grounded=False,
            grounding_source_id=None,
            category=classification.category,
            support_escalation_provided=True,
            related_faq_suggestions=[],
            trace=trace,
        )
