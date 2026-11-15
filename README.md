# Prestige Price Collector

A standalone Windows desktop companion for collecting **real in-game prestige prices** and exporting them for the separate [Prestige Calculator mod](https://github.com/asifkhanpeshawar217-spec/Prestige-calc).

## Planned workflow

1. Open Minecraft and navigate to the server's `/prestige` GUI.
2. Run Prestige Price Collector separately.
3. The collector reads visible game text using screen capture and OCR (no Fabric mod or Minecraft code injection).
4. It records only prices it can actually read. It never invents prices from a pattern.
5. Export `prestige_prices.json` and import that file into the Minecraft mod.

## Current development status

This repository is the **standalone collector project**. The first milestone is the desktop OCR prototype and price-data format. Reliable unattended scanning still needs calibration against screenshots of the actual Minecraft GUI: item-grid positions, tooltip placement, and the Next-page control vary with GUI scale and screen resolution.

The confirmed maximum-prestige pattern is used only to identify expected/missing entries, never to calculate missing prices:

- RB0–RB6: max prestige = `75 + 25 × RB`
- RB7 onward: max prestige = `300 + 50 × (RB - 7)`

Expected entries are P2 through the maximum prestige for each rebirth.

## Requirements

- Windows 10/11
- Python 3.10+ for running from source
- Tesseract OCR installed and available on PATH
- Minecraft must remain open and visible during screen reading

Install dependencies:

```bat
py -m pip install -r requirements.txt
```

Install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki if it is not already installed.

Run:

```bat
py app.py
```

## Price data format

The exported JSON remains compatible with the mod's price database:

```json
{
  "prices": [
    {
      "rebirth": 24,
      "prestige": 1142,
      "individualCost": "$11.880T",
      "cumulativeSpent": "44.860qt"
    }
  ],
  "priceCount": 1,
  "pagesScanned": 1
}
```

The bracketed cumulative amount in the server tooltip is stored separately; it is not treated as the individual price.

## Safety and accuracy

- The collector reads the visible screen; it does not inject code into Minecraft.
- Only observed price text is saved.
- Duplicate (rebirth, prestige) records are updated rather than duplicated.
- Unreadable or missing prices are reported for review.
