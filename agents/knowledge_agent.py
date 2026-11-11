"""
Knowledge Agent
Role: FAQ Knowledge Specialist
Responsibility: Retrieve relevant information from the predefined knowledge base.
"""

from dataclasses import dataclass, field
import difflib
import json
import math
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .base_agent import BaseAgent, AgentTrace


@dataclass
class KnowledgeMatch:
    """Details of a single matched FAQ item."""
    id: str
    category: str
    question: str
    answer: str
    conditions: str
    relevance_score: float
    match_source: str  # "primary_question", "alternative_question", "keyword", "answer"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "conditions": self.conditions,
            "relevance_score": round(self.relevance_score, 3),
            "match_source": self.match_source,
        }


@dataclass
class KnowledgeResult:
    """Output structure returned by the Knowledge Agent."""
    status: str  # "found", "low_confidence", "not_found", "empty_query"
    best_match: Optional[KnowledgeMatch]
    related_matches: List[KnowledgeMatch] = field(default_factory=list)
    top_score: float = 0.0
    category_searched: str = ""
    total_kb_items: int = 0
    trace: Optional[AgentTrace] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "top_score": round(self.top_score, 3),
            "category_searched": self.category_searched,
            "total_kb_items": self.total_kb_items,
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "related_matches": [m.to_dict() for m in self.related_matches],
            "trace": self.trace.to_dict() if self.trace else None,
        }


class KnowledgeAgent(BaseAgent):
    """
    Specialized agent responsible for loading, indexing, and querying the FAQ knowledge base.
    """

    STOP_WORDS = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "up", "about", "into", "through", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did", "can",
        "could", "should", "would", "may", "might", "will", "i", "you", "my", "your",
        "it", "its", "we", "they", "this", "that", "how", "what", "when", "where",
        "why", "who", "which", "please", "tell", "me"
    }

    # Minimum relevance score required to consider a match valid
    RELEVANCE_THRESHOLD = 0.25
    HIGH_CONFIDENCE_THRESHOLD = 0.50

    def __init__(self, knowledge_base_path: Optional[str] = None):
        super().__init__(
            name="Knowledge Agent",
            role="FAQ Knowledge Specialist",
            responsibility="Retrieve relevant information from the knowledge base",
        )
        if knowledge_base_path is None:
            # Default to knowledge_base/faq_data.json relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            knowledge_base_path = os.path.join(base_dir, "knowledge_base", "faq_data.json")

        self.kb_path = knowledge_base_path
        self.metadata: Dict[str, Any] = {}
        self.faqs: List[Dict[str, Any]] = []
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Loads and indexes the JSON knowledge base file."""
        if not os.path.exists(self.kb_path):
            raise FileNotFoundError(f"Knowledge base file not found at: {self.kb_path}")

        with open(self.kb_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.metadata = data.get("metadata", {})
        self.faqs = data.get("faqs", [])

    def _tokenize(self, text: str) -> List[str]:
        """Normalize, strip punctuation, tokenize, and remove stop words."""
        cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
        tokens = [t.strip("-") for t in cleaned.split() if t.strip("-")]
        # Stemming-like suffix truncation for common variants (e.g. tracking -> track)
        stemmed = []
        for t in tokens:
            if t not in self.STOP_WORDS and len(t) > 2:
                t_stem = t
                for suffix in ["ing", "ies", "es", "ed", "s"]:
                    if t_stem.endswith(suffix) and len(t_stem) - len(suffix) >= 3:
                        t_stem = t_stem[:-len(suffix)]
                        break
                stemmed.append(t_stem)
        return stemmed

    def _calculate_jaccard_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculates Jaccard similarity between two token sets."""
        if not tokens_a or not tokens_b:
            return 0.0
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def _calculate_score(self, query: str, query_tokens: List[str], faq: Dict[str, Any]) -> Tuple[float, str]:
        """
        Calculates multi-aspect relevance score for a given FAQ item against the user query.
        Returns (relevance_score, match_source).
        """
        best_score = 0.0
        best_source = "none"
        query_norm = re.sub(r"[^\w\s]", "", query.lower()).strip()

        # 1. Primary question comparison
        primary_q = faq.get("question", "")
        primary_norm = re.sub(r"[^\w\s]", "", primary_q.lower()).strip()
        if query_norm == primary_norm:
            return 1.0, "primary_question"

        seq_sim_primary = difflib.SequenceMatcher(None, query_norm, primary_norm).ratio()
        if seq_sim_primary >= 0.60 and seq_sim_primary > best_score:
            best_score = seq_sim_primary
            best_source = "primary_question"

        q_tokens = self._tokenize(primary_q)
        q_sim = self._calculate_jaccard_similarity(query_tokens, q_tokens)
        if q_sim > best_score and len(query_tokens) > 1:
            best_score = q_sim
            best_source = "primary_question"

        # 2. Alternative questions comparison
        for alt_q in faq.get("alternative_questions", []):
            alt_norm = re.sub(r"[^\w\s]", "", alt_q.lower()).strip()
            if query_norm == alt_norm:
                return 1.0, "alternative_question"

            seq_sim_alt = difflib.SequenceMatcher(None, query_norm, alt_norm).ratio()
            if seq_sim_alt >= 0.60 and seq_sim_alt > best_score:
                best_score = seq_sim_alt
                best_source = "alternative_question"

            alt_tokens = self._tokenize(alt_q)
            alt_sim = self._calculate_jaccard_similarity(query_tokens, alt_tokens)
            if alt_sim > best_score and len(query_tokens) > 1:
                best_score = alt_sim
                best_source = "alternative_question"

        # 3. Keyword list matching
        faq_keywords = [k.lower() for k in faq.get("keywords", [])]
        query_lower = query.lower()
        matched_kw_count = 0
        for kw in faq_keywords:
            if kw in query_lower:
                matched_kw_count += 1
                # Exact phrase matching bonus
                if len(kw.split()) >= 2:
                    matched_kw_count += 1

        if matched_kw_count > 0:
            kw_boost = min(0.45, matched_kw_count * 0.20)
            if best_score + kw_boost > best_score:
                best_score = min(1.0, best_score + kw_boost)
                if best_source == "none":
                    best_source = "keyword"

        # 4. Substring in answer check
        ans_tokens = set(self._tokenize(faq.get("answer", "")))
        ans_overlap = len(set(query_tokens).intersection(ans_tokens))
        if ans_overlap >= 3 and best_score < 0.30:
            best_score = max(best_score, 0.32)
            if best_source == "none":
                best_source = "answer"

        return best_score, best_source

    def process(self, query: str, category: Optional[str] = None) -> KnowledgeResult:
        """
        Searches the knowledge base for FAQs matching the query and category.
        """
        start_time = time.perf_counter()
        query_tokens = self._tokenize(query)

        if not query.strip() or not query_tokens:
            trace = self.create_trace(
                start_time=start_time,
                status="warning",
                decision_summary="Empty query received by Knowledge Agent.",
                details={"query": query},
            )
            return KnowledgeResult(
                status="empty_query",
                best_match=None,
                related_matches=[],
                top_score=0.0,
                category_searched=category or "none",
                total_kb_items=len(self.faqs),
                trace=trace,
            )

        if category == "out_of_scope":
            trace = self.create_trace(
                start_time=start_time,
                status="warning",
                decision_summary="Query categorized as out_of_scope. Predefined knowledge search safely bypassed.",
                details={"category": "out_of_scope", "status": "not_found"},
            )
            return KnowledgeResult(
                status="not_found",
                best_match=None,
                related_matches=[],
                top_score=0.0,
                category_searched="out_of_scope",
                total_kb_items=len(self.faqs),
                trace=trace,
            )

        # Candidate selection:
        # Prioritize FAQs belonging to the detected category, but if no category or out_of_scope,
        # inspect all FAQs.
        target_category = category if category in self.metadata.get("categories", []) else None

        scored_matches: List[KnowledgeMatch] = []

        for faq in self.faqs:
            faq_cat = faq.get("category", "")
            # Apply category filtering with slight bonus for matching category
            if target_category and faq_cat != target_category:
                category_multiplier = 0.55  # penalize cross-category
            else:
                category_multiplier = 1.0

            raw_score, match_source = self._calculate_score(query, query_tokens, faq)
            adjusted_score = raw_score * category_multiplier

            if adjusted_score > 0.05:
                scored_matches.append(
                    KnowledgeMatch(
                        id=faq.get("id", ""),
                        category=faq_cat,
                        question=faq.get("question", ""),
                        answer=faq.get("answer", ""),
                        conditions=faq.get("conditions", ""),
                        relevance_score=adjusted_score,
                        match_source=match_source,
                    )
                )

        # Sort matches by score descending
        scored_matches.sort(key=lambda m: m.relevance_score, reverse=True)

        if not scored_matches or scored_matches[0].relevance_score < self.RELEVANCE_THRESHOLD:
            # No adequate match found in knowledge base
            top_score = scored_matches[0].relevance_score if scored_matches else 0.0
            trace = self.create_trace(
                start_time=start_time,
                status="warning",
                decision_summary=(
                    f"No knowledge base record met the relevance threshold "
                    f"({self.RELEVANCE_THRESHOLD}). Top score was {top_score:.3f}."
                ),
                details={
                    "query": query,
                    "category": category,
                    "top_score": top_score,
                    "status": "not_found",
                },
            )
            return KnowledgeResult(
                status="not_found",
                best_match=None,
                related_matches=[],
                top_score=top_score,
                category_searched=target_category or "all",
                total_kb_items=len(self.faqs),
                trace=trace,
            )

        best = scored_matches[0]
        status = "found" if best.relevance_score >= self.HIGH_CONFIDENCE_THRESHOLD else "low_confidence"
        related = [m for m in scored_matches[1:4] if m.relevance_score >= self.RELEVANCE_THRESHOLD]

        trace = self.create_trace(
            start_time=start_time,
            status="success",
            decision_summary=(
                f"Retrieved FAQ '{best.id}' ({best.question}) with score "
                f"{best.relevance_score:.3f} via {best.match_source}."
            ),
            details={
                "retrieved_id": best.id,
                "retrieved_question": best.question,
                "relevance_score": best.relevance_score,
                "related_count": len(related),
            },
        )

        return KnowledgeResult(
            status=status,
            best_match=best,
            related_matches=related,
            top_score=best.relevance_score,
            category_searched=target_category or "all",
            total_kb_items=len(self.faqs),
            trace=trace,
        )
