from __future__ import annotations

import argparse
import asyncio
import sys

from theseus.bootstrap import build_registry, create_all_tables
from theseus.database import async_session_factory
from theseus.keel.seed.loader import seed_pack


async def run_seed(packs: str) -> dict:
    """Build the schema, then seed each comma-separated pack. Commits once."""
    registry = build_registry()
    await create_all_tables(registry)
    merged: dict = {}
    async with async_session_factory() as session:
        for pack in [p.strip() for p in packs.split(",") if p.strip()]:
            merged.update(await seed_pack(session, registry, pack))
        await session.commit()
    for full_name, counts in merged.items():
        print(f"[seed] {full_name}: +{counts['created']} created, {counts['skipped']} skipped")
    return merged


async def run_export(out: str) -> str:
    from theseus.keel.export.exporter import export_all  # Task 5 (lazy import)

    registry = build_registry()
    async with async_session_factory() as session:
        await export_all(session, registry, out)
    print(f"[export] wrote {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="theseus", description="Theseus ERP admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    seed_p = sub.add_parser("seed", help="Seed default lookups for one or more packs")
    seed_p.add_argument("--packs", required=True, help="comma-separated pack names, e.g. maker")

    export_p = sub.add_parser("export", help="Export all data to a zip (CSV + asset files)")
    export_p.add_argument("--out", required=True, help="output .zip path")

    args = parser.parse_args(argv)
    if args.command == "seed":
        asyncio.run(run_seed(args.packs))
    elif args.command == "export":
        asyncio.run(run_export(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
