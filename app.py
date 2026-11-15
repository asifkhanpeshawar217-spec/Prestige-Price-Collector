from __future__ import annotations

import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from decimal import Decimal, InvalidOperation

try:
    import mss
    from PIL import Image, ImageTk
    import pytesseract
except ImportError as exc:
    raise SystemExit(
        "Missing packages. Run: py -m pip install -r requirements.txt"
    ) from exc

APP_TITLE = "Prestige Price Collector"
OUTPUT_FILE = "prestige_prices.json"

# Matches examples such as:
# Rebirth 24 Prestige 1142
# Cost: $11.880 [44.860qt]
PRICE_RE = re.compile(
    r"Cost\s*:\s*\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([TQ]?|QT)?",
    re.IGNORECASE,
)
REBIRTH_RE = re.compile(r"Rebirth\s*(\d+)", re.IGNORECASE)
PRESTIGE_RE = re.compile(r"Prestige\s*(\d+)", re.IGNORECASE)
CUMULATIVE_RE = re.compile(
    r"\[\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(qt|q|t)\s*\]",
    re.IGNORECASE,
)


def maximum_prestige(rebirth: int) -> int:
    if rebirth <= 6:
        return 75 + 25 * rebirth
    return 300 + 50 * (rebirth - 7)


def normalize_cost(number: str, unit: str | None) -> str:
    cleaned = number.replace(",", "")
    suffix = (unit or "T").upper()
    if suffix == "QT":
        suffix = "qt"
    return f"${cleaned}{suffix}"


def parse_ocr_text(text: str, current_rebirth: int | None):
    """Parse only explicit OCR observations; never estimate a price."""
    results = []
    rebirth = current_rebirth
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)

    for line in lines:
        marker = REBIRTH_RE.search(line)
        if marker and "Prestige" not in line:
            rebirth = int(marker.group(1))

    prestige_match = PRESTIGE_RE.search(joined)
    cost_match = PRICE_RE.search(joined)
    if prestige_match and cost_match and rebirth is not None:
        prestige = int(prestige_match.group(1))
        cumulative = CUMULATIVE_RE.search(joined)
        results.append({
            "rebirth": rebirth,
            "prestige": prestige,
            "individualCost": normalize_cost(
                cost_match.group(1), cost_match.group(2)
            ),
            "cumulativeSpent": (
                f"{cumulative.group(1).replace(',', '')}{cumulative.group(2)}"
                if cumulative else ""
            ),
        })
    return results, rebirth


class CollectorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("940x680")
        self.records: dict[tuple[int, int], dict] = {}
        self.current_rebirth: int | None = None
        self.pages_scanned = 0
        self.last_image = None
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="Prestige Price Collector",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Standalone screen-reading prototype — no Minecraft mod required.",
        ).pack(anchor="w", pady=(0, 10))

        controls = ttk.LabelFrame(outer, text="Screen capture", padding=10)
        controls.pack(fill="x")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.w_var = tk.StringVar(value="1280")
        self.h_var = tk.StringVar(value="720")
        for label, var, width in (
            ("Left", self.x_var, 7), ("Top", self.y_var, 7),
            ("Width", self.w_var, 8), ("Height", self.h_var, 8),
        ):
            ttk.Label(controls, text=label).pack(side="left", padx=(0, 4))
            ttk.Entry(controls, textvariable=var, width=width).pack(
                side="left", padx=(0, 12)
            )
        ttk.Button(
            controls, text="Capture screen and read OCR",
            command=self.capture_and_read
        ).pack(side="left", padx=4)
        ttk.Button(
            controls, text="Import JSON", command=self.import_json
        ).pack(side="right", padx=4)
        ttk.Button(
            controls, text="Export JSON", command=self.export_json
        ).pack(side="right", padx=4)

        stats = ttk.Frame(outer)
        stats.pack(fill="x", pady=10)
        self.stats_var = tk.StringVar()
        ttk.Label(stats, textvariable=self.stats_var).pack(anchor="w")

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=2)

        ttk.Label(left, text="Collected prices").pack(anchor="w")
        columns = ("rebirth", "prestige", "cost", "cumulative")
        self.table = ttk.Treeview(left, columns=columns, show="headings")
        for col, title, width in (
            ("rebirth", "Rebirth", 75), ("prestige", "Prestige", 85),
            ("cost", "Individual cost", 150),
            ("cumulative", "Cumulative spent", 150),
        ):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor="center")
        self.table.pack(fill="both", expand=True)

        ttk.Label(right, text="OCR text (review before trusting)").pack(anchor="w")
        self.ocr_text = tk.Text(right, wrap="word", height=20)
        self.ocr_text.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="Ready. Open the /prestige GUI first.")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def capture_and_read(self):
        try:
            region = {
                "left": int(self.x_var.get()),
                "top": int(self.y_var.get()),
                "width": int(self.w_var.get()),
                "height": int(self.h_var.get()),
            }
            if region["width"] <= 0 or region["height"] <= 0:
                raise ValueError("Width and height must be positive.")
            with mss.mss() as sct:
                shot = sct.grab(region)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
            text = pytesseract.image_to_string(image, config="--psm 6")
            self.ocr_text.delete("1.0", "end")
            self.ocr_text.insert("1.0", text)
            found, self.current_rebirth = parse_ocr_text(
                text, self.current_rebirth
            )
            if found:
                for item in found:
                    key = (item["rebirth"], item["prestige"])
                    self.records[key] = item
                self.pages_scanned += 1
                self.status_var.set(
                    f"Read {len(found)} price record(s). Check the OCR text and export when ready."
                )
            else:
                self.status_var.set(
                    "No complete Rebirth/Prestige/Cost record detected. Adjust the capture area or check the OCR text."
                )
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Capture/OCR error", str(exc))

    def import_json(self):
        path = filedialog.askopenfilename(
            title="Import prestige_prices.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            count = 0
            for item in data.get("prices", []):
                key = (int(item["rebirth"]), int(item["prestige"]))
                self.records[key] = {
                    "rebirth": key[0],
                    "prestige": key[1],
                    "individualCost": str(item["individualCost"]),
                    "cumulativeSpent": str(item.get("cumulativeSpent", "")),
                }
                count += 1
            self.pages_scanned = max(
                self.pages_scanned, int(data.get("pagesScanned", 0))
            )
            self.status_var.set(f"Imported {count} price record(s).")
            self._refresh()
        except Exception as exc:
            messagebox.showerror("Import error", str(exc))

    def export_json(self):
        path = filedialog.asksaveasfilename(
            title="Export prestige_prices.json",
            initialfile=OUTPUT_FILE,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return
        prices = sorted(
            self.records.values(),
            key=lambda x: (x["rebirth"], x["prestige"])
        )
        payload = {
            "prices": prices,
            "priceCount": len(prices),
            "pagesScanned": self.pages_scanned,
        }
        try:
            Path(path).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            self.status_var.set(f"Exported {len(prices)} records to {path}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def _refresh(self):
        for row in self.table.get_children():
            self.table.delete(row)
        for item in sorted(
            self.records.values(),
            key=lambda x: (x["rebirth"], x["prestige"])
        ):
            self.table.insert("", "end", values=(
                item["rebirth"], item["prestige"],
                item["individualCost"], item["cumulativeSpent"]
            ))
        rebirths = sorted({key[0] for key in self.records})
        missing = 0
        for rb in rebirths:
            expected = set(range(2, maximum_prestige(rb) + 1))
            found = {p for r, p in self.records if r == rb}
            missing += len(expected - found)
        self.stats_var.set(
            f"Prices: {len(self.records)}    Pages captured: {self.pages_scanned}    "
            f"Rebirths: {len(rebirths)}    Missing expected entries: {missing}"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = CollectorApp(root)
    root.mainloop()
