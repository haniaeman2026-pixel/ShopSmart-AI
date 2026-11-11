"""
CLI Entry Point for AI-Powered FAQ Assistant
Usage:
    python main.py                       # Runs predefined demonstration suite
    python main.py --interactive         # Enters interactive chat session
    python main.py --question "..."      # Asks a single customer question
    python main.py --demo                # Runs comprehensive demo across all categories
"""

import argparse
import json
import sys
from assistant import FAQAssistant


DEMO_QUESTIONS = [
    # Six Primary Assignment Scenarios (Section 9)
    ("Scenario 1: Orders (Tracking)", "How can I track my order?"),
    ("Scenario 2: Payments (Methods)", "Which payment methods do you accept?"),
    ("Scenario 3: Delivery (Delays)", "My delivery is delayed. What should I do?"),
    ("Scenario 4: Returns (Procedures)", "How can I return a product?"),
    ("Scenario 5: Refunds (Timeline)", "When will I receive my refund?"),
    ("Scenario 6: Missing Policy (Anti-Hallucination)", "Can you deliver my order via spaceship to Mars?"),

    # Additional Domain and Edge Cases
    ("Orders (Cancellation)", "Can I cancel my order that was placed 15 minutes ago?"),
    ("Payments (Decline)", "Why was my credit card declined during checkout?"),
    ("Returns (Exceptions)", "Can I return opened earrings or intimate apparel?"),
    ("Refunds (Store Credit)", "Can I choose store credit instead of a card refund?"),
    ("General (Customer Support)", "What are your customer service hours and how can I contact support?"),
    ("Out-of-Scope (Refusal)", "What is the capital of France and what's the weather today?"),
]


def run_demo(assistant: FAQAssistant):
    """Executes a series of representative customer inquiries demonstrating all agent roles."""
    print("\n" + "=" * 80)
    print("  AI-POWERED FAQ ASSISTANT - MULTI-AGENT DEMONSTRATION")
    print("  Demonstrating:")
    print("    1. FAQ Classifier   (Question Classification Specialist)")
    print("    2. Knowledge Agent   (FAQ Knowledge Specialist)")
    print("    3. Response Agent    (Customer Support Specialist - Grounded / No Hallucinations)")
    print("=" * 80 + "\n")

    for i, (label, question) in enumerate(DEMO_QUESTIONS, 1):
        print(f"\n--- [DEMO CASE {i}/{len(DEMO_QUESTIONS)}: {label}] ---")
        response = assistant.ask(question)
        print(response.format_cli_output(show_traces=True))


def run_interactive(assistant: FAQAssistant):
    """Starts an interactive customer inquiry loop."""
    print("\n" + "=" * 70)
    print("  ShopSmart AI FAQ Assistant - Interactive Customer Support")
    print("  Type your question below. Type 'exit', 'quit', or 'q' to stop.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("\nCustomer: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Thank you for using ShopSmart Support. Have a great day!")
                break

            response = assistant.ask(user_input)
            print("\n" + response.format_cli_output(show_traces=True))

        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="AI-Powered FAQ Assistant Multi-Agent Pipeline")
    parser.add_argument(
        "--question", "-q",
        type=str,
        help="A single customer question to process",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start an interactive chat session",
    )
    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run comprehensive demo showcasing all 5 categories & edge cases",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text (useful for API pipelines)",
    )

    args = parser.parse_args()
    assistant = FAQAssistant()

    if args.question:
        response = assistant.ask(args.question)
        if args.json:
            print(json.dumps(response.to_dict(), indent=2))
        else:
            print(response.format_cli_output(show_traces=True))
    elif args.interactive:
        run_interactive(assistant)
    else:
        # Default to running the full demo
        run_demo(assistant)


if __name__ == "__main__":
    main()
