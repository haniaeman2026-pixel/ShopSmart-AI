"""
Comprehensive Test Suite for AI-Powered FAQ Assistant
Validates all requirements:
1. Accept customer question.
2. Identify category (FAQ Classifier - Question Classification Specialist).
3. Search predefined FAQ knowledge base (Knowledge Agent - FAQ Knowledge Specialist).
4. Generate grounded response (Response Agent - Customer Support Specialist).
5. Avoid inventing answers when information is unavailable (Strict Anti-Hallucination).
6. Tests the 6 specific customer scenarios from Section 9.
7. Tests LLM client and individual agent APIs.
"""

import unittest
import os
import sys
import json

# Ensure parent directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assistant import FAQAssistant
from agents.classifier_agent import FAQClassifierAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.response_agent import ResponseAgent
from agents.llm_client import llm_client


class TestFAQClassifierAgent(unittest.TestCase):
    """Unit tests for the FAQ Classifier Agent (Question Classification Specialist)."""

    def setUp(self):
        self.classifier = FAQClassifierAgent()

    def test_classify_orders(self):
        result = self.classifier.process("How can I track my order?")
        self.assertEqual(result.category, "orders")
        self.assertTrue(result.is_supported_category)
        self.assertGreater(result.confidence, 0.5)

    def test_classify_cancellation(self):
        result = self.classifier.process("I want to cancel my order immediately")
        self.assertEqual(result.category, "orders")
        self.assertTrue(result.is_supported_category)

    def test_classify_payments(self):
        result = self.classifier.process("Do you accept PayPal or credit cards?")
        self.assertEqual(result.category, "payments")
        self.assertTrue(result.is_supported_category)

    def test_classify_payment_declined(self):
        result = self.classifier.process("Why was my card payment declined at checkout?")
        self.assertEqual(result.category, "payments")
        self.assertTrue(result.is_supported_category)

    def test_classify_deliveries(self):
        result = self.classifier.process("How long does standard delivery take?")
        self.assertEqual(result.category, "deliveries")
        self.assertTrue(result.is_supported_category)

    def test_classify_delivery_delay(self):
        result = self.classifier.process("My delivery is delayed. What should I do?")
        self.assertEqual(result.category, "deliveries")
        self.assertTrue(result.is_supported_category)

    def test_classify_shipping_cost(self):
        result = self.classifier.process("What are the shipping fees for fast delivery?")
        self.assertEqual(result.category, "deliveries")
        self.assertTrue(result.is_supported_category)

    def test_classify_returns(self):
        result = self.classifier.process("What is your 30 day return policy?")
        self.assertEqual(result.category, "returns")
        self.assertTrue(result.is_supported_category)

    def test_classify_return_exceptions(self):
        result = self.classifier.process("Can I return underwear or opened earrings?")
        self.assertEqual(result.category, "returns")
        self.assertTrue(result.is_supported_category)

    def test_classify_refunds(self):
        result = self.classifier.process("When will I get my refund back?")
        self.assertEqual(result.category, "refunds")
        self.assertTrue(result.is_supported_category)

    def test_classify_store_credit(self):
        result = self.classifier.process("Can I receive store credit instead of a refund?")
        self.assertEqual(result.category, "refunds")
        self.assertTrue(result.is_supported_category)

    def test_classify_general_queries(self):
        result = self.classifier.process("How can I contact customer support and what are your hours?")
        self.assertEqual(result.category, "general")
        self.assertTrue(result.is_supported_category)

    def test_classify_out_of_scope(self):
        result = self.classifier.process("Who is the prime minister of Canada?")
        self.assertEqual(result.category, "out_of_scope")
        self.assertFalse(result.is_supported_category)

    def test_classify_empty_string(self):
        result = self.classifier.process("   ")
        self.assertEqual(result.category, "out_of_scope")
        self.assertFalse(result.is_supported_category)


class TestKnowledgeAgent(unittest.TestCase):
    """Unit tests for the Knowledge Agent (FAQ Knowledge Specialist)."""

    def setUp(self):
        self.knowledge_agent = KnowledgeAgent()

    def test_kb_loaded_successfully(self):
        self.assertGreaterEqual(len(self.knowledge_agent.faqs), 25)
        self.assertIn("orders", self.knowledge_agent.metadata["categories"])
        self.assertIn("general", self.knowledge_agent.metadata["categories"])

    def test_retrieve_exact_order_tracking(self):
        result = self.knowledge_agent.process(
            query="How do I track my order status?",
            category="orders",
        )
        self.assertEqual(result.status, "found")
        self.assertIsNotNone(result.best_match)
        self.assertEqual(result.best_match.id, "ORD-003")

    def test_retrieve_delivery_delay_faq(self):
        result = self.knowledge_agent.process(
            query="My delivery is delayed. What should I do?",
            category="deliveries",
        )
        self.assertIn(result.status, ["found", "low_confidence"])
        self.assertIsNotNone(result.best_match)
        self.assertEqual(result.best_match.id, "DEL-006")

    def test_retrieve_payment_methods(self):
        result = self.knowledge_agent.process(
            query="Which payment methods do you accept?",
            category="payments",
        )
        self.assertEqual(result.status, "found")
        self.assertEqual(result.best_match.id, "PAY-001")

    def test_retrieve_unmatched_query_returns_not_found(self):
        result = self.knowledge_agent.process(
            query="Do you fly personal rockets to Saturn with alien passengers?",
            category="orders",
        )
        self.assertEqual(result.status, "not_found")
        self.assertIsNone(result.best_match)

    def test_empty_query(self):
        result = self.knowledge_agent.process(query="")
        self.assertEqual(result.status, "empty_query")


class TestResponseAgent(unittest.TestCase):
    """Unit tests for Response Agent (Customer Support Specialist & Anti-Hallucination)."""

    def setUp(self):
        self.classifier = FAQClassifierAgent()
        self.knowledge_agent = KnowledgeAgent()
        self.response_agent = ResponseAgent()

    def test_grounded_response_generated(self):
        q = "What payment methods do you accept?"
        c = self.classifier.process(q)
        k = self.knowledge_agent.process(q, category=c.category)
        res = self.response_agent.process(q, c, k)

        self.assertTrue(res.is_grounded)
        self.assertEqual(res.grounding_source_id, "PAY-001")
        self.assertIn("Visa", res.response_text)
        self.assertIn("PayPal", res.response_text)

    def test_refusal_and_no_hallucination_on_unavailable_knowledge(self):
        # Requirement 5: Avoid inventing answers when information is unavailable
        q = "Do you deliver via trained dolphins across the Atlantic?"
        c = self.classifier.process(q)
        k = self.knowledge_agent.process(q, category=c.category)
        res = self.response_agent.process(q, c, k)

        self.assertFalse(res.is_grounded)
        self.assertIsNone(res.grounding_source_id)
        # Verify it acknowledges lack of information rather than inventing an answer
        self.assertIn("does not contain verified information", res.response_text)
        self.assertIn("support@shopsmart.example.com", res.response_text)
        self.assertIn("1-800-555-SHOP", res.response_text)


class TestAssignmentSixScenarios(unittest.TestCase):
    """
    Validates the 6 explicit customer scenarios mandated in Section 9 of the prompt.
    """

    def setUp(self):
        self.assistant = FAQAssistant()

    def test_scenario_1_order_tracking(self):
        # Scenario 1: Customer: "How can I track my order?"
        # Expected: Orders category, relevant tracking FAQ, grounded answer.
        question = "How can I track my order?"
        resp = self.assistant.ask(question)

        self.assertEqual(resp.category, "orders")
        self.assertTrue(resp.is_grounded)
        self.assertEqual(resp.grounding_source_id, "ORD-003")
        self.assertIn("Track Package", resp.response_text)
        self.assertIn("tracking number", resp.response_text.lower())

    def test_scenario_2_payment_methods(self):
        # Scenario 2: Customer: "Which payment methods do you accept?"
        # Expected: Payments category and answer based on the knowledge base.
        question = "Which payment methods do you accept?"
        resp = self.assistant.ask(question)

        self.assertEqual(resp.category, "payments")
        self.assertTrue(resp.is_grounded)
        self.assertEqual(resp.grounding_source_id, "PAY-001")
        self.assertIn("Visa", resp.response_text)
        self.assertIn("MasterCard", resp.response_text)
        self.assertIn("PayPal", resp.response_text)

    def test_scenario_3_delivery_delayed(self):
        # Scenario 3: Customer: "My delivery is delayed. What should I do?"
        # Expected: Delivery category and relevant FAQ response.
        question = "My delivery is delayed. What should I do?"
        resp = self.assistant.ask(question)

        self.assertEqual(resp.category, "deliveries")
        self.assertTrue(resp.is_grounded)
        self.assertEqual(resp.grounding_source_id, "DEL-006")
        self.assertIn("tracking link", resp.response_text.lower())
        self.assertIn("support@shopsmart.example.com", resp.response_text)

    def test_scenario_4_return_procedures(self):
        # Scenario 4: Customer: "How can I return a product?"
        # Expected: Returns category and relevant return instructions.
        question = "How can I return a product?"
        resp = self.assistant.ask(question)

        self.assertEqual(resp.category, "returns")
        self.assertTrue(resp.is_grounded)
        self.assertIn(resp.grounding_source_id, ["RET-001", "RET-003"])
        self.assertIn("return", resp.response_text.lower())

    def test_scenario_5_refund_timeline(self):
        # Scenario 5: Customer: "When will I receive my refund?"
        # Expected: Refund category and answer based on available refund information.
        question = "When will I receive my refund?"
        resp = self.assistant.ask(question)

        self.assertEqual(resp.category, "refunds")
        self.assertTrue(resp.is_grounded)
        self.assertEqual(resp.grounding_source_id, "REF-001")
        self.assertIn("business days", resp.response_text.lower())
        self.assertIn("original payment method", resp.response_text.lower())

    def test_scenario_6_missing_policy_fallback(self):
        # Scenario 6: Customer: Ask a question about a policy that does not exist in the knowledge base.
        # Expected: The system must not invent an answer. It must return an appropriate fallback response.
        question = "Do you accept barter trades of gold coins or livestock for electronic items?"
        resp = self.assistant.ask(question)

        self.assertFalse(resp.is_grounded)
        self.assertIsNone(resp.grounding_source_id)
        # Verify strict refusal to invent
        self.assertIn("does not contain verified information", resp.response_text)
        self.assertIn("avoid guessing", resp.response_text.lower())
        self.assertIn("support@shopsmart.example.com", resp.response_text)


class TestEndToEndPipeline(unittest.TestCase):
    """Integration tests validating the entire Multi-Agent pipeline."""

    def setUp(self):
        self.assistant = FAQAssistant()

    def test_traces_contain_all_three_specialists(self):
        response = self.assistant.ask("Where is my order tracking number?")
        agent_names = [t.agent_name for t in response.agent_traces]
        self.assertIn("FAQ Classifier", agent_names)
        self.assertIn("Knowledge Agent", agent_names)
        self.assertIn("Response Agent", agent_names)

    def test_latency_is_under_100ms(self):
        response = self.assistant.ask("What is your return policy?")
        self.assertLess(response.total_time_ms, 100.0)

    def test_serialization_to_dict(self):
        response = self.assistant.ask("How to return an item?")
        d = response.to_dict()
        self.assertIn("question", d)
        self.assertIn("category", d)
        self.assertIn("classification", d)
        self.assertIn("knowledge", d)
        self.assertIn("response", d)
        self.assertIn("agent_traces", d)

    def test_llm_client_status_structure(self):
        status = llm_client.get_status()
        self.assertIn("provider", status)
        self.assertIn("model", status)
        self.assertIn("has_key", status)
        self.assertIn("is_online", status)
        self.assertIn("engine_mode", status)
        # API keys should never be unmasked
        if status.get("masked_key"):
            self.assertTrue(status["masked_key"].startswith("***") or "..." in status["masked_key"])


class MockSocket:
    def __init__(self, request_bytes: bytes):
        from io import BytesIO
        self.rfile = BytesIO(request_bytes)
        self.wfile = BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            else:
                return self.wfile
        raise ValueError("Only binary mode supported")

    def sendall(self, data):
        self.wfile.write(data)


def simulate_http_request(raw_http: str):
    from unittest.mock import MagicMock
    from server import AssistantHTTPRequestHandler

    mock_sock = MockSocket(raw_http.encode("utf-8"))
    mock_server = MagicMock()
    handler = AssistantHTTPRequestHandler(mock_sock, ("127.0.0.1", 8000), mock_server)
    response_bytes = mock_sock.wfile.getvalue()
    response_text = response_bytes.decode("utf-8", errors="replace")

    lines = response_text.split("\r\n")
    status_line = lines[0]
    status_code = int(status_line.split()[1])

    headers = {}
    body_idx = 0
    for i, line in enumerate(lines[1:], 1):
        if line == "":
            body_idx = i + 1
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    body = "\r\n".join(lines[body_idx:])
    return status_code, headers, body


class TestHTTPAPIEndpoints(unittest.TestCase):
    """Directly tests server REST API endpoints and response payloads."""

    def test_get_health(self):
        req = "GET /api/health HTTP/1.1\r\nHost: localhost\r\n\r\n"
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("classifier", data["agents"])
        self.assertIn("knowledge", data["agents"])
        self.assertIn("response", data["agents"])

    def test_get_kb(self):
        req = "GET /api/kb HTTP/1.1\r\nHost: localhost\r\n\r\n"
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["total_faqs"], 25)

    def test_post_ask_scenario_1(self):
        payload = json.dumps({"question": "How can I track my order?"})
        req = (
            f"POST /api/ask HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["category"], "orders")
        self.assertTrue(data["is_grounded"])
        self.assertEqual(data["grounding_source_id"], "ORD-003")

    def test_post_ask_empty_question_returns_400(self):
        payload = json.dumps({"question": "   "})
        req = (
            f"POST /api/ask HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 400)
        data = json.loads(body)
        self.assertIn("error", data)

    def test_post_classify_endpoint(self):
        payload = json.dumps({"question": "Why did my credit card payment fail?"})
        req = (
            f"POST /api/classify HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["category"], "payments")
        self.assertTrue(data["is_supported_category"])

    def test_post_retrieve_endpoint(self):
        payload = json.dumps({"query": "What is the return policy?", "category": "returns"})
        req = (
            f"POST /api/retrieve HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["best_match"]["id"], "RET-001")

    def test_post_respond_endpoint(self):
        payload = json.dumps({"question": "How long does standard delivery take?", "category": "deliveries"})
        req = (
            f"POST /api/respond HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertTrue(data["is_grounded"])
        self.assertEqual(data["grounding_source_id"], "DEL-001")


    def test_post_respond_ignores_untrusted_client_match(self):
        payload = json.dumps({
            "question": "How long does standard delivery take?",
            "match": {
                "id": "FAKE-999",
                "category": "deliveries",
                "question": "Fake question",
                "answer": "Guaranteed delivery in one hour.",
                "relevance_score": 1.0,
            },
        })
        req = (
            f"POST /api/respond HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
            f"{payload}"
        )
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["grounding_source_id"], "DEL-001")
        self.assertNotIn("Guaranteed delivery in one hour", data["response_text"])

    def test_get_history_endpoint(self):
        req = "GET /api/history HTTP/1.1\r\nHost: localhost\r\n\r\n"
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertIn("history", data)

    def test_404_not_found_endpoint(self):
        req = "GET /api/unknown_endpoint HTTP/1.1\r\nHost: localhost\r\n\r\n"
        code, headers, body = simulate_http_request(req)
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
