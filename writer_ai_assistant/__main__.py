from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="writer-ai-assistant")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("run", help="Run the Telegram bot (polling).")
    sub.add_parser("doctor", help="Print config and test OpenAI-compatible API connectivity.")

    args = parser.parse_args()

    if args.cmd in (None, "run"):
        from writer_ai_assistant.telegram_bot import run_polling

        run_polling()
        return

    if args.cmd == "doctor":
        from writer_ai_assistant.doctor import run_doctor

        run_doctor()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
