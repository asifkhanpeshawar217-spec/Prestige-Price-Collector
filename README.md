# Prestige Price Collector

A standalone Windows desktop app that scans the visible Minecraft prestige menu. It is separate from the Fabric mod.

## Download the Windows app (no Python setup)

Every push to the `main` branch starts a GitHub Actions build.

1. Open the repository's **Actions** tab.
2. Select the latest successful **Build Windows EXE** run.
3. Under **Artifacts**, download `Prestige-Price-Collector-Windows`.
4. Extract the ZIP file.
5. Double-click `PrestigePriceCollector.exe`.

The EXE bundles the Python runtime, required Python libraries, Tesseract OCR, and its English language data. You do not need to install Python, Tesseract, or run Command Prompt.

If GitHub shows that the build is still running, wait for it to finish. Download the artifact only after the workflow succeeds.

## What it does

- F8 calibration learns the center of the top-left slot and the bottom-right Next-page arrow.
- Uses the **9 columns × 6 rows** menu layout shown in the screenshots.
- Hovers each menu slot, reads the tooltip with OCR, and saves only prices it actually reads.
- Clicks Next and repeats while the menu visibly changes.
- Autosaves `prestige_prices.json`; supports JSON import and export.
- Stores individual cost and bracketed cumulative spent separately. It never estimates missing prices.

## How to scan

1. Open Minecraft and the server's `/prestige` menu.
2. Open `PrestigePriceCollector.exe`.
3. Click **Capture first (F8)**, move the mouse to the **center of the top-left slot**, and press F8.
4. Click **Capture Next (F8)**, move the mouse to the **center of the bottom-right Next arrow**, and press F8 again.
5. Set hover delay to 0.4–0.6 seconds; increase it if tooltips are missed.
6. Start automatic scan. Keep Minecraft visible and do not move the mouse while scanning.
7. Stop at any time. Progress is saved in `prestige_prices.json`.

The scanner uses the whole desktop for OCR, so Minecraft must remain visible. PyAutoGUI's emergency stop is triggered by moving the mouse to the top-left screen corner.

## Accuracy notes

OCR depends on screen resolution, GUI scale, tooltip contrast, and hover delay. Check the OCR panel and several saved records during a short test before leaving a long scan. Pagination ends when the calibrated Next click produces no visible change in the menu grid. If the server layout changes, the 9×6 assumption must be updated. Only explicit tooltip prices are saved; unreadable values remain missing.

## Output JSON

The export matches the mod's `prestige_prices.json` format, with `prices`, `priceCount`, and `pagesScanned`. Each record contains `rebirth`, `prestige`, `individualCost`, and `cumulativeSpent`.

## Developer instructions

To run from source instead of the EXE, install Python 3.10+, Tesseract OCR, and the packages in `requirements.txt`, then run `py app.py`.
