"""
Frontend DOM & Script Unit Tests
Validates index.html structure, required DOM IDs, accessibility, and JavaScript syntax.
"""

from html.parser import HTMLParser
import os
import re
import subprocess
import unittest


class DOMValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids_found = set()
        self.tags = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for attr, val in attrs:
            if attr.lower() == "id":
                if val in self.ids_found:
                    self.errors.append(f"Duplicate element id found: {val}")
                self.ids_found.add(val)


class TestFrontendIntegrity(unittest.TestCase):
    REQUIRED_ELEMENT_IDS = [
        "questionInput",
        "submitBtn",
        "faqCountLabel",
        "engineModeLabel",
        "topLatencyLabel",
        "tClassifier",
        "tKnowledge",
        "tResponse",
        "categoryPill",
        "confidenceText",
        "classifierReasoning",
        "classifierKeywords",
        "knowledgeStatus",
        "knowledgeScore",
        "knowledgeSummary",
        "knowledgeMatchedFaq",
        "responseStatus",
        "responseSummary",
        "groundingBanner",
        "groundingText",
        "faqSourceTag",
        "responseTextBox",
        "historyList",
        "historyCount",
        "jsonDebugView",
    ]

    def setUp(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.html_path = os.path.join(base_dir, "web", "index.html")

    def test_html_file_exists(self):
        self.assertTrue(os.path.exists(self.html_path), "index.html should exist in web/ directory")

    def test_dom_elements_present_and_unique(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = DOMValidator()
        parser.feed(content)

        self.assertEqual(len(parser.errors), 0, f"HTML parsing errors found: {parser.errors}")

        for req_id in self.REQUIRED_ELEMENT_IDS:
            self.assertIn(req_id, parser.ids_found, f"Missing required element ID: {req_id}")

    def test_javascript_syntax_with_node(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            content = f.read()

        script_match = re.search(r"<script>(.*?)</script>", content, re.DOTALL)
        self.assertIsNotNone(script_match, "No <script> tag found in index.html")

        js_code = script_match.group(1)
        temp_js = os.path.join(os.path.dirname(__file__), "_temp_js_check.js")

        stubs = (
            "const window = { addEventListener: () => {} };\n"
            "const document = { getElementById: () => ({ addEventListener: () => {}, textContent: '', value: '', style: {}, disabled: false }) };\n"
            "const navigator = { clipboard: { writeText: () => Promise.resolve() } };\n"
            "const alert = () => {};\n"
            "const fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) });\n"
        )

        with open(temp_js, "w", encoding="utf-8") as f:
            f.write(stubs + js_code)

        try:
            res = subprocess.run(["node", "--check", temp_js], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Node.js syntax check failed: {res.stderr}")
        finally:
            if os.path.exists(temp_js):
                os.remove(temp_js)


if __name__ == "__main__":
    unittest.main()
