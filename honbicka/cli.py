"""CLI vstupní bod (spec §8).

    honbicka gen zadani/hra.yaml       # jedna hra (vyrobí 30+60)
    honbicka batch zadani/plan.yaml    # dávka: N her přes noc
    honbicka new                       # interaktivní pomocník → YAML
    honbicka feedback <slug>           # zápis šablony playtestu
    honbicka export <slug>             # .twee (Twine) + Mermaid mapa hry
    honbicka status                    # přehled běhů, failů, registru
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import yaml

from honbicka import __version__


def _vytvor_klienta():
    """Tovární funkce klienta (testy monkeypatchnou na mock)."""
    from honbicka.llm import OllamaKlient
    return OllamaKlient()


def sestav_yaml(odpovedi: dict) -> str:
    """Sestaví YAML zadání z odpovědí pomocníka (spec §8)."""
    cistky = {k: v for k, v in odpovedi.items() if v not in (None, "", [])}
    return yaml.safe_dump(cistky, allow_unicode=True, sort_keys=False)


def _cmd_gen(args: argparse.Namespace) -> int:
    from honbicka.davka import nacti_zadani
    from honbicka.orchestrator import vyrob_hru
    zadani = nacti_zadani(args.zadani)
    hra = vyrob_hru(zadani, _vytvor_klienta(), copypaste=args.copypaste)
    print(f"Hra: {hra.slug} — {hra.report.stav.value} (seed {hra.report.seed})")
    for c in hra.report.chyby:
        print(f"  ! {c}")
    return 0 if hra.report.stav.value == "OK" else 1


def _cmd_batch(args: argparse.Namespace) -> int:
    from honbicka.davka import nacti_plan, spust_davku
    plan = nacti_plan(args.plan)
    report = spust_davku(plan, _vytvor_klienta(), copypaste=args.copypaste)
    print(f"Dávka: {report.uspesnych}/{report.celkem} OK, {report.failed} FAILED")
    for v in report.vysledky:
        print(f"  [{v.stav}] {v.slug} (seed {v.seed})")
    return 0 if report.failed == 0 else 1


def _cmd_new(args: argparse.Namespace) -> int:
    print("Interaktivní pomocník (Enter = přeskočit).")
    try:
        tema = input("Téma (prázdné = auto): ").strip()
        vek = input("Věk [04-06/06-09/09-12/12-15/16plus]: ").strip() or "06-09"
        fmt = input("Formát [volny_format/jednotlivci/dvojice/tymy_NxM]: ").strip()
        fmt = fmt or "volny_format"
        prostredi = input("Prostředí (čárkami): ").strip()
        obtiznost = input("Obtížnost [lehka/stredni/tezka]: ").strip() or "lehka"
        ton = input("Tón: ").strip()
    except EOFError:
        print("Vstup ukončen.", file=sys.stderr)
        return 2
    odpovedi = {
        "tema": tema or None, "vek": vek, "format_hracu": fmt,
        "prostredi": [p.strip() for p in prostredi.split(",") if p.strip()],
        "obtiznost": obtiznost, "ton": ton or None,
    }
    os.makedirs("zadani", exist_ok=True)
    cesta = os.path.join("zadani", (args.vystup or "nova_hra.yaml"))
    with open(cesta, "w", encoding="utf-8") as f:
        f.write(sestav_yaml(odpovedi))
    print(f"Zapsáno: {cesta}")
    return 0


def _cmd_feedback(args: argparse.Namespace) -> int:
    from honbicka.feedback import zapis_sablonu
    cesta = zapis_sablonu(args.slug)
    print(f"Šablona playtestu: {cesta}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Export hry do .twee (kontrola proklikem v Twine) a Mermaid (mapa)."""
    import json

    from honbicka.export import export_mermaid, export_twee
    from honbicka.modely import Karta, Mapa

    skin = os.path.join(args.skiny_dir, args.slug)
    mapa_cesta = os.path.join(skin, "mapa.json")
    if not os.path.isfile(mapa_cesta):
        print(f"Nenalezeno: {mapa_cesta}", file=sys.stderr)
        return 1
    with open(mapa_cesta, encoding="utf-8") as f:
        mapa = Mapa.model_validate_json(f.read())
    karty = None
    karty_cesta = os.path.join(skin, "karty.json")
    if os.path.isfile(karty_cesta):
        with open(karty_cesta, encoding="utf-8") as f:
            karty = [Karta.model_validate(k) for k in json.load(f)]
    vystupy = []
    if args.format in ("twee", "vse"):
        cesta = os.path.join(skin, f"{args.slug}.twee")
        with open(cesta, "w", encoding="utf-8") as f:
            f.write(export_twee(mapa, karty, nazev=args.slug))
        vystupy.append(cesta)
    if args.format in ("mermaid", "vse"):
        cesta = os.path.join(skin, "mapa.mmd")
        with open(cesta, "w", encoding="utf-8") as f:
            f.write(export_mermaid(mapa))
        vystupy.append(cesta)
    for v in vystupy:
        print(f"Zapsáno: {v}")
    print("Tip: .twee soubor přetáhni do Twine (twinery.org) — hra se zobrazí "
          "jako klikatelný graf.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from honbicka.registr import nacti_registr
    print(f"HONBIČKA FACTORY v{__version__}")
    zaznamy = nacti_registr()
    print(f"Registr: {len(zaznamy)} her")
    for z in zaznamy[-5:]:
        print(f"  {z.datum} · {z.slug} · {z.archetyp} · seed {z.seed}")
    return 0


def vytvor_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="honbicka", description="HONBIČKA FACTORY")
    p.add_argument("--version", action="version", version=f"honbicka {__version__}")
    sub = p.add_subparsers(dest="prikaz", required=True)

    g = sub.add_parser("gen", help="vyrob jednu hru (30+60) z YAML zadání")
    g.add_argument("zadani", help="cesta k YAML zadání")
    g.add_argument("-c", "--copypaste", action="store_true", help="spustit v copy-paste rezimu pro placene LLM")
    g.set_defaults(func=_cmd_gen)

    b = sub.add_parser("batch", help="dávka her z plánu")
    b.add_argument("plan", help="cesta k YAML batch plánu")
    b.add_argument("-c", "--copypaste", action="store_true", help="spustit v copy-paste rezimu pro placene LLM")
    b.set_defaults(func=_cmd_batch)

    n = sub.add_parser("new", help="interaktivní pomocník → YAML")
    n.add_argument("--vystup", help="název výstupního YAML v zadani/", default=None)
    n.set_defaults(func=_cmd_new)

    f = sub.add_parser("feedback", help="zápis šablony playtestu")
    f.add_argument("slug", help="slug hry")
    f.set_defaults(func=_cmd_feedback)

    e = sub.add_parser("export", help="export hry do .twee (Twine) a Mermaid mapy")
    e.add_argument("slug", help="slug hry ve skiny/")
    e.add_argument("--format", choices=["twee", "mermaid", "vse"], default="vse")
    e.add_argument("--skiny-dir", default="skiny")
    e.set_defaults(func=_cmd_export)

    s = sub.add_parser("status", help="přehled běhů, failů, registru")
    s.set_defaults(func=_cmd_status)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = vytvor_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except NotImplementedError as exc:
        print(f"[zatím neimplementováno] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
