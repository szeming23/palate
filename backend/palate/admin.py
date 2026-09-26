"""Manage access codes and check configured keys.

python -m palate.admin keys
python -m palate.admin codes add my-phone --key anthropic-main --daily-usd 3
python -m palate.admin codes add friend --user friend --key anthropic-main --models claude-haiku-4-5 --daily-messages 50
python -m palate.admin codes list
python -m palate.admin codes remove friend
"""

import argparse
import sqlite3
import sys

from . import access, config, db
from .llm import MODELS


def cmd_keys(_args) -> None:
    if not config.LLM_KEYS:
        print("No LLM keys configured. Add PALATE_KEY_<NAME>=<provider>:<secret> to .env")
        return
    for name, (provider, secret) in sorted(config.LLM_KEYS.items()):
        print(f"{name:24} {provider:12} ...{secret[-4:]}")


def cmd_add(args) -> None:
    unknown_keys = [k for k in args.key if k not in config.LLM_KEYS]
    if unknown_keys:
        sys.exit(f"Unknown key name(s): {', '.join(unknown_keys)}. Run `python -m palate.admin keys`.")
    models = args.models.split(",") if args.models else None
    if models:
        valid = {m.id for m in MODELS}
        bad = [m for m in models if m not in valid]
        if bad:
            sys.exit(f"Unknown model(s): {', '.join(bad)}. Valid: {', '.join(sorted(valid))}")

    code = access.generate_code()
    try:
        db.add_access_code(
            name=args.name,
            code_hash=access.hash_code(code),
            user_id=args.user,
            key_names=args.key,
            allowed_models=models,
            daily_messages=args.daily_messages,
            daily_usd=args.daily_usd,
        )
    except sqlite3.IntegrityError:
        sys.exit(f"An access code named '{args.name}' already exists.")

    print(f"Created access code '{args.name}' for user '{args.user}'.")
    print()
    print(f"    {code}")
    print()
    print("Enter it in the app under Settings → Access code. It won't be shown again.")


def cmd_list(_args) -> None:
    codes = db.list_access_codes()
    if not codes:
        print("No access codes yet. Create one with `codes add <name> --key <key-name>`.")
        return
    for c in codes:
        used = access.today_usage(c)
        limits = []
        if c["daily_messages"] is not None:
            limits.append(f"{used['messages']}/{c['daily_messages']} msgs")
        else:
            limits.append(f"{used['messages']} msgs")
        if c["daily_usd"] is not None:
            limits.append(f"${used['cost_usd']:.2f}/${c['daily_usd']:.2f}")
        else:
            limits.append(f"${used['cost_usd']:.2f}")
        models = ",".join(c["allowed_models"]) if c["allowed_models"] else "all models"
        print(
            f"{c['name']:18} user={c['user_id']:10} keys={','.join(c['key_names']):22} {models:28} today: {' '.join(limits)}"
        )


def cmd_remove(args) -> None:
    if db.delete_access_code(args.name):
        print(f"Removed '{args.name}'. Clients using it are locked out immediately.")
    else:
        sys.exit(f"No access code named '{args.name}'.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m palate.admin", description="Manage Palate access codes.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("keys", help="List LLM keys configured in .env").set_defaults(func=cmd_keys)

    codes = sub.add_parser("codes", help="Manage access codes").add_subparsers(dest="action", required=True)

    add = codes.add_parser("add", help="Create an access code")
    add.add_argument("name", help="Label, e.g. my-phone, dev-laptop, friend")
    add.add_argument("--key", action="append", required=True, help="LLM key name to use (repeatable, one per provider)")
    add.add_argument("--user", default="me", help="Whose memory/history this code uses (default: me)")
    add.add_argument("--models", help="Comma-separated allowed models (default: all)")
    add.add_argument("--daily-messages", type=int, help="Max messages per day")
    add.add_argument("--daily-usd", type=float, help="Max server-paid LLM spend per day, in USD")
    add.set_defaults(func=cmd_add)

    codes.add_parser("list", help="List access codes and today's usage").set_defaults(func=cmd_list)

    rm = codes.add_parser("remove", help="Revoke an access code")
    rm.add_argument("name")
    rm.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    db.init()
    args.func(args)


if __name__ == "__main__":
    main()
