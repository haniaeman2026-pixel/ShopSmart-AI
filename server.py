"""
Web and API Server for AI-Powered FAQ Assistant
Zero external dependencies (uses standard library http.server).
Exposes endpoints for full pipeline as well as individual agent testing.
"""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from assistant import FAQAssistant
from agents.llm_client import llm_client
from agents.classifier_agent import ClassificationResult


PORT = 8000
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
assistant = FAQAssistant()

# In-memory history of recent customer inquiries (for live dashboard display)
SESSION_HISTORY: List[Dict[str, Any]] = []
MAX_HISTORY = 50


class AssistantHTTPRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the web UI and REST API."""

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        """Preflight CORS handling."""
        self._set_headers(200, "application/json")

    def _read_json_body(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Parses incoming request JSON body with error safety."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}, None
            raw_body = self.rfile.read(content_length).decode("utf-8")
            if not raw_body.strip():
                return {}, None
            payload = json.loads(raw_body)
            if not isinstance(payload, dict):
                return None, "JSON request body must be an object."
            return payload, None
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON payload: {str(e)}"
        except Exception as e:
            return None, f"Error reading request body: {str(e)}"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/favicon.ico":
            self._set_headers(204, "image/x-icon")
            return

        if path in ["/", "/index.html"]:
            index_path = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content)
            else:
                self._set_headers(404, "text/plain")
                self.wfile.write(b"index.html not found")

        elif path == "/api/health":
            llm_status = llm_client.get_status()
            health_data = {
                "status": "healthy",
                "service": "ShopSmart AI FAQ Assistant",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "agents": {
                    "classifier": {
                        "name": assistant.classifier_agent.name,
                        "role": assistant.classifier_agent.role,
                        "status": "active",
                        "supported_categories": assistant.classifier_agent.SUPPORTED_CATEGORIES,
                    },
                    "knowledge": {
                        "name": assistant.knowledge_agent.name,
                        "role": assistant.knowledge_agent.role,
                        "status": "active",
                        "total_faqs": len(assistant.knowledge_agent.faqs),
                        "categories": assistant.knowledge_agent.metadata.get("categories", []),
                    },
                    "response": {
                        "name": assistant.response_agent.name,
                        "role": assistant.response_agent.role,
                        "status": "active",
                        "grounding_enforced": True,
                        "anti_hallucination_enabled": True,
                    },
                },
                "llm_provider": llm_status,
                "history_count": len(SESSION_HISTORY),
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(health_data, indent=2).encode("utf-8"))

        elif path == "/api/kb":
            kb_data = {
                "metadata": assistant.knowledge_agent.metadata,
                "total_faqs": len(assistant.knowledge_agent.faqs),
                "faqs": assistant.knowledge_agent.faqs,
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(kb_data).encode("utf-8"))

        elif path == "/api/history":
            self._set_headers(200)
            self.wfile.write(json.dumps({"history": SESSION_HISTORY}).encode("utf-8"))

        else:
            self._set_headers(404, "application/json")
            self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}"}).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body, err = self._read_json_body()

        if err:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": err}).encode("utf-8"))
            return

        body = body or {}

        # 1. Pipeline Endpoint: POST /api/ask
        if path == "/api/ask":
            question = str(body.get("question") or "").strip()
            if not question:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty question provided. Please submit a valid question string."}).encode("utf-8"))
                return

            try:
                result = assistant.ask(question)
                data = result.to_dict()

                # Record in session history
                history_entry = {
                    "id": len(SESSION_HISTORY) + 1,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "question": question,
                    "category": data["category"],
                    "is_grounded": data["is_grounded"],
                    "source_id": data["grounding_source_id"],
                    "latency_ms": data["total_time_ms"],
                    "response_text": data["response_text"],
                }
                SESSION_HISTORY.insert(0, history_entry)
                if len(SESSION_HISTORY) > MAX_HISTORY:
                    SESSION_HISTORY.pop()

                self._set_headers(200)
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": f"Internal execution error: {str(e)}"}).encode("utf-8"))

        # 2. Agent 1 Independent Endpoint: POST /api/classify
        elif path == "/api/classify":
            question = str(body.get("question") or "").strip()
            if not question:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Question field is required for classification."}).encode("utf-8"))
                return

            classification = assistant.classifier_agent.process(question)
            self._set_headers(200)
            self.wfile.write(json.dumps(classification.to_dict()).encode("utf-8"))

        # 3. Agent 2 Independent Endpoint: POST /api/retrieve
        elif path == "/api/retrieve":
            query = str(body.get("query") or "").strip()
            category = body.get("category", None)
            if not query:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Query field is required for knowledge retrieval."}).encode("utf-8"))
                return

            knowledge = assistant.knowledge_agent.process(query=query, category=category)
            self._set_headers(200)
            self.wfile.write(json.dumps(knowledge.to_dict()).encode("utf-8"))

        # 4. Agent 3 Independent Endpoint: POST /api/respond
        elif path == "/api/respond":
            question = str(body.get("question") or "").strip()
            if not question:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Question field is required for response generation."}).encode("utf-8"))
                return

            # Never trust a client-supplied FAQ answer. Retrieve the match from
            # the server-owned knowledge base to preserve the grounding guarantee.
            classification = assistant.classifier_agent.process(question)
            knowledge = assistant.knowledge_agent.process(
                query=question,
                category=classification.category,
            )
            response = assistant.response_agent.process(question, classification, knowledge)
            self._set_headers(200)
            self.wfile.write(json.dumps(response.to_dict()).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}"}).encode("utf-8"))

    def log_message(self, format, *args):
        # Clean terminal logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run(port: int = PORT):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, AssistantHTTPRequestHandler)
    print(f"============================================================")
    print(f"  ShopSmart FAQ Assistant Server Running")
    print(f"  URL: http://localhost:{port}")
    print(f"  Endpoints:")
    print(f"    - GET  /api/health")
    print(f"    - GET  /api/kb")
    print(f"    - GET  /api/history")
    print(f"    - POST /api/ask")
    print(f"    - POST /api/classify")
    print(f"    - POST /api/retrieve")
    print(f"    - POST /api/respond")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run(port_arg)
