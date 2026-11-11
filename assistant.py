"""
FAQ Assistant Orchestrator
Coordinates the Multi-Agent pipeline:
1. Accept a customer question.
2. Identify the category (FAQ Classifier Agent).
3. Search the predefined FAQ knowledge base (Knowledge Agent).
4. Generate an appropriate response grounded in retrieved data (Response Agent).
5. Avoid inventing answers when information is unavailable.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from agents.classifier_agent import FAQClassifierAgent, ClassificationResult
from agents.knowledge_agent import KnowledgeAgent, KnowledgeResult
from agents.response_agent import ResponseAgent, ResponseResult
from agents.base_agent import AgentTrace


@dataclass
class AssistantResponse:
    """Consolidated result produced by the Multi-Agent FAQ Assistant."""
    question: str
    category: str
    response_text: str
    is_grounded: bool
    grounding_source_id: Optional[str]
    classification: ClassificationResult
    knowledge: KnowledgeResult
    response_agent_result: ResponseResult
    agent_traces: List[AgentTrace]
    total_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "category": self.category,
            "response_text": self.response_text,
            "is_grounded": self.is_grounded,
            "grounding_source_id": self.grounding_source_id,
            "classification": self.classification.to_dict(),
            "knowledge": self.knowledge.to_dict(),
            "response": self.response_agent_result.to_dict(),
            "agent_traces": [trace.to_dict() for trace in self.agent_traces],
            "total_time_ms": round(self.total_time_ms, 2),
        }

    def format_cli_output(self, show_traces: bool = True) -> str:
        """Formats the response cleanly for terminal viewing."""
        lines = []
        divider = "=" * 70
        lines.append(divider)
        lines.append(f"CUSTOMER QUESTION: \"{self.question}\"")
        lines.append(divider)

        if show_traces:
            lines.append("\n[MULTI-AGENT EXECUTION TRACE]")
            for trace in self.agent_traces:
                status_symbol = "✓" if trace.status == "success" else "⚠"
                lines.append(
                    f" {status_symbol} [{trace.agent_name} | {trace.role}] "
                    f"({trace.execution_time_ms:.1f}ms): {trace.decision_summary}"
                )
            lines.append("")

        lines.append("[ASSISTANT RESPONSE]")
        lines.append(self.response_text)
        lines.append("")
        lines.append(
            f"[METADATA] Grounded: {self.is_grounded} | "
            f"Source FAQ: {self.grounding_source_id or 'None (Refusal/Fallback)'} | "
            f"Total Latency: {self.total_time_ms:.1f}ms"
        )
        lines.append(divider)
        return "\n".join(lines)


class FAQAssistant:
    """
    Main entry point and orchestrator for the AI-Powered FAQ Assistant.
    """

    def __init__(self, knowledge_base_path: Optional[str] = None):
        self.classifier_agent = FAQClassifierAgent()
        self.knowledge_agent = KnowledgeAgent(knowledge_base_path=knowledge_base_path)
        self.response_agent = ResponseAgent()

    def ask(self, question: str) -> AssistantResponse:
        """
        Executes the end-to-end multi-agent workflow for a given customer question.
        """
        start_overall = time.perf_counter()
        agent_traces: List[AgentTrace] = []

        # Step 1 & 2: FAQ Classifier determines question category
        classification = self.classifier_agent.process(question)
        if classification.trace:
            agent_traces.append(classification.trace)

        # Step 3: Knowledge Agent searches the predefined knowledge base
        knowledge = self.knowledge_agent.process(
            query=question,
            category=classification.category,
        )
        if knowledge.trace:
            agent_traces.append(knowledge.trace)

        # Step 4 & 5: Response Agent synthesizes grounded answer or prevents hallucination
        response = self.response_agent.process(
            customer_question=question,
            classification=classification,
            knowledge=knowledge,
        )
        if response.trace:
            agent_traces.append(response.trace)

        total_time_ms = (time.perf_counter() - start_overall) * 1000.0

        return AssistantResponse(
            question=question,
            category=classification.category,
            response_text=response.response_text,
            is_grounded=response.is_grounded,
            grounding_source_id=response.grounding_source_id,
            classification=classification,
            knowledge=knowledge,
            response_agent_result=response,
            agent_traces=agent_traces,
            total_time_ms=total_time_ms,
        )

    def batch_ask(self, questions: List[str]) -> List[AssistantResponse]:
        """Processes a list of customer questions in sequence."""
        return [self.ask(q) for q in questions]
