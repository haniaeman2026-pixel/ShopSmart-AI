"""
FAQ Classifier Agent
Role: Question Classification Specialist
Responsibility: Understand the customer question and identify its category.
"""

from dataclasses import dataclass, field
import re
import time
from typing import Dict, List, Optional, Set, Tuple

from .base_agent import BaseAgent, AgentTrace


@dataclass
class ClassificationResult:
    """Output structure returned by the FAQ Classifier Agent."""
    category: str  # orders, payments, deliveries, returns, refunds, or out_of_scope
    confidence: float  # 0.0 to 1.0
    detected_keywords: List[str]
    intent_description: str
    is_supported_category: bool
    secondary_categories: List[Tuple[str, float]] = field(default_factory=list)
    trace: Optional[AgentTrace] = None

    def to_dict(self):
        return {
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "detected_keywords": self.detected_keywords,
            "intent_description": self.intent_description,
            "is_supported_category": self.is_supported_category,
            "secondary_categories": [
                {"category": cat, "score": round(score, 3)}
                for cat, score in self.secondary_categories
            ],
            "trace": self.trace.to_dict() if self.trace else None,
        }


class FAQClassifierAgent(BaseAgent):
    """
    Specialized agent responsible for analyzing user inquiries, extracting key terms,
    and classifying the inquiry into the appropriate business domain category.
    """

    SUPPORTED_CATEGORIES = ["orders", "payments", "deliveries", "returns", "refunds", "general"]

    # Category vocabulary definitions with weights (term, weight)
    CATEGORY_LEXICON: Dict[str, Dict[str, float]] = {
        "orders": {
            "order": 1.5,
            "orders": 1.5,
            "cancel": 2.0,
            "cancellation": 2.0,
            "modify": 1.8,
            "edit order": 2.0,
            "change order": 1.8,
            "place order": 2.2,
            "checkout": 1.8,
            "cart": 1.4,
            "purchase": 1.3,
            "invoice": 2.0,
            "receipt": 1.9,
            "order status": 2.0,
            "order id": 1.8,
            "order number": 1.8,
            "my orders": 1.8,
            "change address": 1.6,
            "wrong address": 1.5,
            "order confirmation": 2.5,
            "confirmation email": 2.5,
            "did my order go through": 2.5,
        },
        "payments": {
            "pay": 1.5,
            "payment": 2.0,
            "payments": 2.0,
            "credit card": 2.2,
            "debit card": 2.2,
            "card declined": 2.5,
            "payment failed": 2.5,
            "paypal": 2.2,
            "apple pay": 2.2,
            "google pay": 2.2,
            "cash on delivery": 2.5,
            "cod": 2.0,
            "installments": 2.2,
            "klarna": 2.2,
            "afterpay": 2.2,
            "bnpl": 2.0,
            "cvv": 2.0,
            "secure checkout": 1.8,
            "charged twice": 2.0,
            "charge": 1.4,
            "billing": 1.7,
            "safe": 1.8,
            "safe payment": 2.2,
            "card safe": 2.2,
            "payment security": 2.2,
            "security": 1.8,
            "transaction": 1.6,
        },
        "deliveries": {
            "delivery": 2.0,
            "deliver": 1.8,
            "deliveries": 2.0,
            "ship": 1.8,
            "shipping": 2.0,
            "shipped": 1.8,
            "shipment": 2.0,
            "carrier": 1.8,
            "courier": 1.8,
            "tracking": 2.0,
            "track package": 2.2,
            "where is my package": 2.5,
            "dispatch": 1.8,
            "dispatched": 1.8,
            "express delivery": 2.2,
            "same day": 2.2,
            "next day": 2.0,
            "shipping cost": 2.0,
            "shipping fee": 2.0,
            "free shipping": 2.0,
            "international": 1.8,
            "overseas": 1.8,
            "arrive": 1.5,
            "arrival": 1.5,
            "not home": 1.8,
            "missed delivery": 2.2,
            "delivery delayed": 2.8,
            "delayed": 2.2,
            "delay": 2.0,
            "delays": 2.0,
            "late delivery": 2.5,
            "package delayed": 2.8,
            "late package": 2.5,
        },
        "returns": {
            "return": 2.2,
            "returns": 2.2,
            "returning": 2.0,
            "returned": 1.8,
            "return policy": 2.5,
            "return window": 2.5,
            "return period": 2.5,
            "send back": 2.0,
            "return label": 2.2,
            "non-returnable": 2.5,
            "damaged item": 1.8,
            "defective": 1.8,
            "wrong item": 1.8,
            "restocking fee": 2.0,
            "exchange": 1.7,
            "original packaging": 1.8,
            "rma": 2.2,
        },
        "refunds": {
            "refund": 2.5,
            "refunds": 2.5,
            "refunded": 2.2,
            "refunding": 2.2,
            "money back": 2.5,
            "reimburse": 2.2,
            "reimbursement": 2.2,
            "store credit": 2.2,
            "refund timeline": 2.5,
            "how long for refund": 2.5,
            "refund to card": 2.2,
            "missing refund": 2.5,
            "delayed refund": 2.5,
            "refund status": 2.2,
            "promo refund": 2.0,
            "voucher refund": 2.0,
        },
        "general": {
            "customer service": 2.5,
            "support hours": 2.5,
            "contact support": 2.5,
            "human agent": 2.5,
            "speak to someone": 2.5,
            "talk to": 2.0,
            "talk to someone": 2.5,
            "talk to a person": 2.5,
            "real person": 2.5,
            "human person": 2.5,
            "human representative": 2.5,
            "human": 2.0,
            "person": 1.5,
            "help desk": 2.2,
            "customer care": 2.2,
            "representative": 2.0,
            "account": 1.6,
            "create account": 2.5,
            "sign up": 2.2,
            "register": 2.0,
            "password": 2.0,
            "reset password": 2.5,
            "store hours": 2.0,
            "business hours": 2.2,
            "phone number": 2.0,
            "contact": 1.6,
        },
    }

    # Stop words that should not influence classification
    STOP_WORDS: Set[str] = {
        "a", "about", "an", "and", "are", "as", "at", "be", "by", "can", "could",
        "do", "does", "for", "from", "have", "how", "i", "if", "in", "is", "it",
        "my", "me", "of", "on", "or", "our", "please", "site", "tell", "that",
        "the", "their", "there", "this", "to", "was", "what", "when", "where",
        "which", "who", "will", "with", "would", "you", "your"
    }

    def __init__(self):
        super().__init__(
            name="FAQ Classifier",
            role="Question Classification Specialist",
            responsibility="Understand the question and identify its category",
        )

    def _normalize(self, text: str) -> str:
        """Lowercase and remove extraneous punctuation."""
        return re.sub(r"[^\w\s-]", " ", text.lower())

    def _extract_ngrams(self, text: str) -> List[str]:
        """Extract unigrams, bigrams, and trigrams from normalized text."""
        tokens = [t for t in self._normalize(text).split() if t]
        ngrams = list(tokens)
        for i in range(len(tokens) - 1):
            ngrams.append(f"{tokens[i]} {tokens[i+1]}")
        for i in range(len(tokens) - 2):
            ngrams.append(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")
        return ngrams

    def process(self, question: str) -> ClassificationResult:
        """
        Classifies the customer question into one of the 5 categories or out_of_scope.
        """
        start_time = time.perf_counter()
        clean_text = self._normalize(question)
        ngrams = self._extract_ngrams(question)

        # Handle empty or purely whitespace questions
        if not clean_text.strip():
            trace = self.create_trace(
                start_time=start_time,
                status="warning",
                decision_summary="Received empty question.",
                details={"raw_question": question},
            )
            return ClassificationResult(
                category="out_of_scope",
                confidence=0.0,
                detected_keywords=[],
                intent_description="Empty or invalid query",
                is_supported_category=False,
                trace=trace,
            )

        # Category scores and matching keywords
        category_scores: Dict[str, float] = {cat: 0.0 for cat in self.SUPPORTED_CATEGORIES}
        matched_keywords: Dict[str, List[str]] = {cat: [] for cat in self.SUPPORTED_CATEGORIES}

        for category, lexicon in self.CATEGORY_LEXICON.items():
            for phrase, weight in lexicon.items():
                if " " in phrase:
                    # Multi-word phrase matching
                    if phrase in clean_text:
                        category_scores[category] += weight
                        matched_keywords[category].append(phrase)
                else:
                    # Exact single word token matching
                    pattern = rf"\b{re.escape(phrase)}\b"
                    if re.search(pattern, clean_text):
                        category_scores[category] += weight
                        matched_keywords[category].append(phrase)

        # Contextual Disambiguation heuristics:
        # 1. "refund" vs "return":
        # If user asks "When will I get my refund for the return?", the core intent is refund timing.
        if "refund" in clean_text or "money back" in clean_text:
            if "when" in clean_text or "how long" in clean_text or "timeline" in clean_text or "received" in clean_text:
                category_scores["refunds"] += 1.5

        # 2. "cancel order":
        # Should strongly map to orders rather than returns
        if "cancel" in clean_text and "order" in clean_text:
            category_scores["orders"] += 2.0

        # 3. "track package / where is my order":
        # If user asks "Where is my order / package", both orders and deliveries are close,
        # but tracking shipment status specifically falls into deliveries/orders.
        if "track" in clean_text or "tracking" in clean_text:
            category_scores["orders"] += 1.2
            category_scores["deliveries"] += 1.2

        # Sort categories by score
        sorted_categories = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)
        top_category, top_score = sorted_categories[0]

        # Calculate confidence metric
        MINIMUM_CONFIDENCE_THRESHOLD = 1.2
        if top_score < MINIMUM_CONFIDENCE_THRESHOLD:
            # Check if it's general greeting or total out of scope
            detected_cat = "out_of_scope"
            confidence = 0.15 if top_score > 0 else 0.0
            is_supported = False
            intent = "Out-of-scope, conversational greeting, or unrecognized question"
            top_keywords = []
        else:
            detected_cat = top_category
            # Normalize confidence score between 0.5 and 0.98 based on match strength
            confidence = min(0.98, max(0.55, top_score / 4.0))
            is_supported = True
            intent = f"Customer inquiry regarding {detected_cat}"
            top_keywords = matched_keywords[detected_cat]

        secondary_matches = [
            (cat, min(0.95, score / 4.0))
            for cat, score in sorted_categories[1:]
            if score > 0.8
        ]

        decision_summary = (
            f"Classified into '{detected_cat}' with confidence {confidence:.2f} "
            f"based on keywords: {top_keywords}"
        )

        trace = self.create_trace(
            start_time=start_time,
            status="success" if is_supported else "warning",
            decision_summary=decision_summary,
            details={
                "category": detected_cat,
                "confidence": confidence,
                "top_score": top_score,
                "keywords": top_keywords,
                "secondary_categories": secondary_matches,
            },
        )

        return ClassificationResult(
            category=detected_cat,
            confidence=confidence,
            detected_keywords=top_keywords,
            intent_description=intent,
            is_supported_category=is_supported,
            secondary_categories=secondary_matches,
            trace=trace,
        )
