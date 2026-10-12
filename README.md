# bingo-card-generator
Takes categories with questions from a JSON, picks a select number of questions from each category and generates a DIN-A4 pdf-file containing 2 bingo-cards


## Installation
python3 -m venv venv
.\venv\Scripts\activate (Windows) / source ./venv/bin/activate (Linux/Mac)
python3 -m pip install reportlab

## Usage

python3 make_bingo_cards.py                         # 5 A4-Seiten = 10 Karten
python3 make_bingo_cards.py --pages 15 --seed 42    # 30 Karten, reproduzierbar
python3 make_bingo_cards.py --show-category         # Kategorie klein in jedem Feld