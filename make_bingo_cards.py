#!/usr/bin/env python3
"""Erzeugt Bingo-Karten als PDF: DIN A4 (hochkant) mit je 2 Karten im Format DIN A5 (quer).

Liest Kategorien, Fragen und Blueprints aus einer JSON-Datei (siehe questions.json).

Beispiele:
    python make_bingo_cards.py
    python make_bingo_cards.py --pages 10 --seed 42 --output party.pdf
    python make_bingo_cards.py --show-category

Benötigt: pip install reportlab
"""
import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
GRID = 5


# --------------------------------------------------------------------------- #
# Konfiguration laden und prüfen
# --------------------------------------------------------------------------- #
def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["categories"] = {c["code"]: c for c in cfg["categories"]}
    free = cfg.get("free_code", "F")
    cfg["free_code"] = free
    cfg["blueprints"] = [[row.split() for row in bp] for bp in cfg["blueprints"]]

    errors = []
    for code, cat in cfg["categories"].items():
        if len(cat["questions"]) != len(set(cat["questions"])):
            errors.append(f"Kategorie '{cat['name']}' enthält doppelte Fragen.")

    for i, bp in enumerate(cfg["blueprints"], start=1):
        if len(bp) != GRID or any(len(row) != GRID for row in bp):
            errors.append(f"Blueprint {i}: muss {GRID}x{GRID} Felder haben.")
            continue
        counts = Counter(code for row in bp for code in row)
        for code, n in counts.items():
            if code == free:
                continue
            if code not in cfg["categories"]:
                errors.append(f"Blueprint {i}: unbekanntes Kürzel '{code}'.")
            elif n > len(cfg["categories"][code]["questions"]):
                cat = cfg["categories"][code]
                errors.append(
                    f"Blueprint {i}: {n} Felder für '{cat['name']}', "
                    f"aber nur {len(cat['questions'])} Fragen vorhanden."
                )
    if errors:
        sys.exit("Fehler in der JSON-Datei:\n  - " + "\n  - ".join(errors))
    return cfg


# --------------------------------------------------------------------------- #
# Fragen auf eine Karte verteilen
# --------------------------------------------------------------------------- #
def build_card(blueprint, cfg, usage: Counter, rng: random.Random):
    """Gibt ein 5x5-Raster zurück: None (Freifeld) oder (Kategoriename, Frage).

    Pro Feld wird aus der passenden Kategorie eine Frage gezogen, die auf dieser
    Karte noch nicht vorkommt. Unter allen Kandidaten werden bevorzugt die
    Fragen gewählt, die bisher am seltensten verwendet wurden, damit alle
    Fragen über alle Karten hinweg ungefähr gleich oft vorkommen.
    """
    used_on_card = set()
    grid = []
    for row in blueprint:
        out_row = []
        for code in row:
            if code == cfg["free_code"]:
                out_row.append(None)
                continue
            cat = cfg["categories"][code]
            candidates = [q for q in cat["questions"] if q not in used_on_card]
            least = min(usage[q] for q in candidates)
            question = rng.choice([q for q in candidates if usage[q] == least])
            usage[question] += 1
            used_on_card.add(question)
            out_row.append((cat["name"], question))
        grid.append(out_row)
    return grid


# --------------------------------------------------------------------------- #
# Zeichnen
# --------------------------------------------------------------------------- #
def fit_text(text, font, max_w, max_h, start=11.0, minimum=6.0):
    """Findet die größte Schriftgröße, bei der der Text in die Box passt."""
    size = start
    while size >= minimum:
        lines = simpleSplit(text, font, size, max_w)
        if len(lines) * size * 1.15 <= max_h:
            return size, lines
        size -= 0.5
    return minimum, simpleSplit(text, font, minimum, max_w)


def draw_star(c, cx, cy, r_outer, fill):
    r_inner = r_outer * 0.42
    path = c.beginPath()
    for i in range(10):
        r = r_outer if i % 2 == 0 else r_inner
        angle = math.pi / 2 + i * math.pi / 5
        x, y = cx + r * math.cos(angle), cy + r * math.sin(angle)
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    path.close()
    c.setFillColor(fill)
    c.setStrokeColor(black)
    c.setLineWidth(0.6)
    c.drawPath(path, fill=1, stroke=1)


def draw_card(c, grid, x0, y0, w, h, cfg, show_category):
    """Zeichnet eine Karte in das Rechteck (x0, y0, w, h) – Ursprung unten links."""
    margin_x, margin_top, margin_bottom, header_h = 8 * mm, 7 * mm, 7 * mm, 17 * mm

    gx = x0 + margin_x
    gw = w - 2 * margin_x
    gtop = y0 + h - margin_top - header_h
    gh = gtop - (y0 + margin_bottom)
    cw, ch = gw / GRID, gh / GRID

    # Kopfzeile
    c.setFillColor(black)
    c.setFont(FONT_BOLD, 20)
    c.drawString(gx, y0 + h - margin_top - 7 * mm, cfg.get("title", "Find somebody who…"))

    rules = cfg.get("rules", "")
    if rules:
        c.setFillColor(Color(0.35, 0.35, 0.35))
        c.setFont(FONT, 8)
        lines = simpleSplit(rules, FONT, 8, gw * 0.62)[:2]
        for i, line in enumerate(lines):
            c.drawString(gx, y0 + h - margin_top - 12.5 * mm - i * 3.6 * mm, line)

    c.setFillColor(black)
    c.setFont(FONT, 10)
    c.drawRightString(gx + gw, y0 + h - margin_top - 7 * mm, "Team Name: ______________________")

    # Felder
    for r, row in enumerate(grid):
        for col, cell in enumerate(row):
            x = gx + col * cw
            y = gtop - (r + 1) * ch

            c.setStrokeColor(Color(0.35, 0.35, 0.35))
            c.setLineWidth(0.8)

            if cell is None:  # Freifeld
                c.setFillColor(Color(0.92, 0.92, 0.92))
                c.rect(x, y, cw, ch, fill=1, stroke=1)
                draw_star(c, x + cw / 2, y + ch / 2 + 2 * mm, 6.5 * mm, Color(1, 1, 1))
                c.setFillColor(black)
                c.setFont(FONT_BOLD, 9)
                c.drawCentredString(x + cw / 2, y + 3.5 * mm, "FREE")
                continue

            category, question = cell
            c.setFillColor(Color(1, 1, 1))
            c.rect(x, y, cw, ch, fill=1, stroke=1)

            pad = 2 * mm
            bottom_reserved = 6.5 * mm      # Platz für die Unterschriftszeile
            top_reserved = 3.2 * mm if show_category else 0
            text_top = y + ch - pad - top_reserved
            text_bottom = y + bottom_reserved
            box_h = text_top - text_bottom

            if show_category:
                c.setFillColor(Color(0.5, 0.5, 0.5))
                c.setFont(FONT, 5.5)
                c.drawString(x + pad, y + ch - pad - 4, category.upper())

            size, lines = fit_text(question, FONT, cw - 2 * pad, box_h)
            leading = size * 1.15
            block_h = len(lines) * leading
            ty = text_bottom + (box_h + block_h) / 2 - size  # vertikal zentriert
            c.setFillColor(black)
            c.setFont(FONT, size)
            for line in lines:
                c.drawCentredString(x + cw / 2, ty, line)
                ty -= leading

            # Unterschriftszeile
            c.setStrokeColor(Color(0.6, 0.6, 0.6))
            c.setLineWidth(0.5)
            c.line(x + 3 * mm, y + 4.3 * mm, x + cw - 3 * mm, y + 4.3 * mm)
            c.setFillColor(Color(0.55, 0.55, 0.55))
            c.setFont(FONT, 5)
            c.drawString(x + 3 * mm, y + 1.7 * mm, "name")


def build_pdf(cfg, output: Path, pages: int, seed, show_category: bool):
    rng = random.Random(seed)
    usage = Counter()
    for cat in cfg["categories"].values():
        for q in cat["questions"]:
            usage[q] = 0

    page_w, page_h = A4
    card_h = page_h / 2  # 148,5 mm -> zusammen mit 210 mm Breite exakt A5 quer

    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle("Bingo-Karten")
    c.setAuthor("Bingo-Generator")

    card_index = 0
    for _ in range(pages):
        for slot in range(2):
            blueprint = cfg["blueprints"][card_index % len(cfg["blueprints"])]
            grid = build_card(blueprint, cfg, usage, rng)
            y0 = page_h / 2 if slot == 0 else 0
            draw_card(c, grid, 0, y0, page_w, card_h, cfg, show_category)
            card_index += 1

        # Schnittlinie zwischen den beiden Karten
        c.setStrokeColor(Color(0.6, 0.6, 0.6))
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        c.line(0, page_h / 2, page_w, page_h / 2)
        c.setDash()
        c.showPage()

    c.save()
    return card_index, usage


def main():
    default_json = Path(__file__).with_name("questions.json")
    ap = argparse.ArgumentParser(description="Bingo-Karten (2x A5 pro A4-Seite) als PDF erzeugen.")
    ap.add_argument("--json", type=Path, default=default_json, help="Pfad zur JSON-Datei")
    ap.add_argument("--output", type=Path, default=Path("bingo_cards.pdf"), help="Ausgabe-PDF")
    ap.add_argument("--pages", type=int, default=5,
                    help="Anzahl A4-Seiten (je 2 Karten). Standard: 5 = 10 Karten, eine pro Blueprint")
    ap.add_argument("--seed", type=int, default=None, help="Zufalls-Seed für reproduzierbare Karten")
    ap.add_argument("--show-category", action="store_true",
                    help="Kategorie klein in jedes Feld drucken")
    args = ap.parse_args()

    if args.pages < 1:
        sys.exit("--pages muss mindestens 1 sein.")

    cfg = load_config(args.json)
    n_cards, usage = build_pdf(cfg, args.output, args.pages, args.seed, args.show_category)

    counts = usage.values()
    print(f"{n_cards} Karten auf {args.pages} A4-Seiten -> {args.output}")
    print(f"Fragen: {len(usage)} | Verwendung pro Frage: min {min(counts)}, max {max(counts)}")


if __name__ == "__main__":
    main()