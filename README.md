# Prestige Price Collector

A standalone Windows desktop app that scans the visible Minecraft prestige menu. It is separate from the Fabric mod.

## What it does

- F8 calibration learns the center of the top-left slot and the bottom-right Next-page arrow.
- Uses the **9 columns × 6 rows** menu layout shown in the screenshots.
- Hovers each menu slot, reads the tooltip with OCR, and saves only prices it actually reads.
- Clicks Next and repeats while the menu visibly changes.
- Autosaves `prestige_prices.json`; supports JSON import and export.
- Stores individual cost and bracketed cumulative spent separately. It never estimates missing prices.

## Requirements

- Windows 10/11, Python 3.10+, and Tesseract OCR.
- Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
- In this folder run `py -m pip install -r requirements.txt`.
- Start with `py app.py` or double-click `start_collector.bat`.

## How to scan

1. Open Minecraft and the server's `/prestige` menu.
2. Open the collector.
3. Put the mouse at the **center of the top-left slot** and press F8.
4. Put the mouse at the **center of the bottom-right Next arrow** and press F8 again.
5. Set hover delay to 0.4–0.6 seconds; increase it if tooltips are missed.
6. Start automatic scan. Keep Minecraft visible and do not use the mouse while scanning.
7. Stop at any time. Progress is saved in `prestige_prices.json`.

The scanner uses the whole desktop for OCR, so Minecraft must remain visible. PyAutoGUI's emergency stop is triggered by moving the mouse to the top-left screen corner.

## Accuracy notes

OCR depends on screen resolution, GUI scale, tooltip contrast, and hover delay. Check the OCR panel and several saved records during a short test before leaving a long scan. Pagination ends when the calibrated Next click produces no visible change in the menu grid. If the server layout changes, the 9×6 assumption must be updated. Only explicit tooltip prices are saved; unreadable values remain missing.

## JSON format

The export matches the mod's `prestige_prices.json` format, with `prices`, `priceCount`, and `pagesScanned`. Each record contains `rebirth`, `prestige`, `individualCost`, and `cumulativeSpent`.
