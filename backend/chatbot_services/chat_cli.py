"""
Simple CLI chatbot interface for the reconciliation lookup service.
Uses existing modules (`nlp`, `lookup`, `response_formatter`) without modifying them.

Features:
- Enter a free-text query (e.g. "check TXN001" or "rrn 123456789012")
- Commands: `stats`, `reload`, `help`, `exit`/`quit`
- Prints a human-readable summary and JSON of the matched transaction

Run:
    python chat_cli.py

"""
import json
import sys

import nlp
import lookup
import response_formatter


PROMPT = "You> "


def print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def handle_query(text: str):
    info = nlp.extract_identifiers(text)

    if info.get("has_identifier"):
        rrn = info.get("rrn")
        txn = info.get("txn_id")

        if rrn:
            transaction = lookup.search_by_rrn(rrn)
            search_type = "rrn"
            identifier = rrn
        else:
            # normalize txn id to match stored keys (prefix with TXN if needed)
            lookup_txn = txn if txn.upper().startswith("TXN") else f"TXN{txn}"
            transaction = lookup.search_by_txn_id(lookup_txn)
            search_type = "txn_id"
            identifier = lookup_txn

        if transaction is None:
            run_id = lookup.CURRENT_RUN_ID or "UNKNOWN"
            resp = response_formatter.format_not_found_response(identifier, search_type, run_id)
            print("\n[Not Found]")
            print_json(resp)
            return

        # Print both human readable and JSON
        print("\n[Transaction]")
        try:
            pretty = response_formatter.format_human_readable(transaction)
            print(pretty)
        except Exception:
            # fallback to JSON if human formatting fails
            pass

        resp = response_formatter.format_transaction_response(transaction, lookup.CURRENT_RUN_ID or "UNKNOWN")
        print_json(resp)
        return

    # No identifier found — attempt to detect intent and suggest
    intent = info.get("intent")
    confidence = info.get("confidence")
    print(f"Detected intent: {intent} (confidence={confidence:.2f})")
    print("No transaction identifier (RRN/TXN) found in your message.")
    print("Try: 'rrn 636397811101708' or 'txn 001' or use command 'help' for options")


def main():
    print("Chatbot CLI — Reconciliation Lookup")
    print("Type a message to lookup a transaction. Commands: stats, reload, help, exit")

    try:
        while True:
            try:
                text = input(PROMPT).strip()
            except EOFError:
                print("\nExiting.")
                break

            if not text:
                continue

            cmd = text.lower()
            if cmd in ("exit", "quit"):
                print("Goodbye.")
                break
            if cmd == "help":
                print("Commands:")
                print("  stats  - Show loaded reconciliation statistics")
                print("  reload - Reload latest reconciliation run into memory")
                print("  help   - Show this help")
                print("  exit   - Quit the CLI")
                print("Examples:")
                print("  check rrn 636397811101708")
                print("  txn 001")
                continue
            if cmd == "stats":
                stats = lookup.get_statistics()
                print_json(stats)
                continue
            if cmd == "reload":
                ok = lookup.reload_data()
                if ok:
                    print("Reloaded data successfully.")
                else:
                    print("Reload did not change data or failed. See logs.")
                continue

            # Otherwise treat input as a natural query
            handle_query(text)

    except KeyboardInterrupt:
        print("\nInterrupted — goodbye.")


if __name__ == "__main__":
    main()
