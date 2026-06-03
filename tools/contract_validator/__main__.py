"""CLI do validador de contrato.

    python -m tools.contract_validator --url http://localhost:8000
    python -m tools.contract_validator --spec openapi.json --min-score 90
"""

import argparse
import os
import sys

from . import checks, loader, report, scoring


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate-contract",
        description="Valida a qualidade do contrato OpenAPI e atribui uma nota 0-100.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--url", help="URL base da app rodando (busca {url}/openapi.json).")
    src.add_argument("--spec", help="Caminho de um arquivo openapi.json local.")
    p.add_argument(
        "--min-score", type=int, default=80, help="Nota minima para PASS (default: 80)."
    )
    p.add_argument("--no-color", action="store_true", help="Desativa cores ANSI.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    color = not args.no_color and not os.environ.get("NO_COLOR") and sys.stdout.isatty()

    try:
        if args.spec:
            spec = loader.from_file(args.spec)
        else:
            spec = loader.from_url(args.url or "http://localhost:8000")
    except loader.SpecLoadError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    results = checks.run_all(spec)
    score = scoring.total_score(results)
    ok = scoring.passed(results, score, args.min_score)
    print(report.render(results, score, ok, color=color))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
