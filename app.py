from __future__ import annotations
import json, os, re, sys, threading, time, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

try:
    import mss, pyautogui, pytesseract
    from PIL import Image, ImageChops, ImageEnhance, ImageOps
    from pynput import keyboard
except ImportError as exc:
    raise SystemExit("Missing packages. Run: py -m pip install -r requirements.txt") from exc

TITLE = "Prestige Price Collector"
OUT = "prestige_prices.json"
COLS, ROWS = 9, 6
REBIRTH = re.compile(r"\bRebirth\s*(?:level\s*)?[:#-]?\s*(\d+)\b", re.I)
PRESTIGE = re.compile(r"\bPrestige\s*(?:level\s*)?[:#-]?\s*(\d+)\b", re.I)
COST = re.compile(r"\bCost\s*:\s*\$?\s*([0-9][0-9,.]*)\s*(qt|q|t|b|m|k)?\b", re.I)
TOTAL = re.compile(r"\[\s*([0-9][0-9,.]*)\s*(qt|q|t|b|m|k)\s*\]", re.I)

def parse_tooltip(text, current_rb):
    rb = REBIRTH.search(text)
    p = PRESTIGE.search(text)
    c = COST.search(text)
    total = TOTAL.search(text)
    if rb:
        current_rb = int(rb.group(1))
    record = None
    if p and c and current_rb is not None:
        unit = (c.group(2) or "T").upper()
        if unit == "QT":
            unit = "qt"
        cost = "$" + c.group(1).replace(",", "") + unit
        cumulative = ""
        if total:
            cumulative = total.group(1).replace(",", "") + total.group(2).lower()
        record = {"rebirth": current_rb, "prestige": int(p.group(1)),
                  "individualCost": cost, "cumulativeSpent": cumulative}
    return record, current_rb

def setup_tesseract():
    # In the packaged EXE, Tesseract and its English OCR data are bundled
    # beside the application inside PyInstaller's temporary extraction folder.
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / "tesseract"
        exe = bundle / "tesseract.exe"
        if exe.exists():
            pytesseract.pytesseract.tesseract_cmd = str(exe)
            os.environ["TESSDATA_PREFIX"] = str(bundle)
            return

    # Development fallback when running app.py directly.
    for p in (Path(r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"),
              Path(r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe")):
        if p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(p)
            return

class App:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.geometry("980x690")
        root.minsize(850, 580)
        self.records = {}
        self.current_rb: Optional[int] = None
        self.pages = 0
        self.unreadable = 0
        self.first = None
        self.last = None
        self.capture_request = None
        self.armed_target = None
        self.stop_event = threading.Event()
        self.worker = None
        self.delay = tk.StringVar(value="0.4")
        self.first_text = tk.StringVar(value="Not set")
        self.last_text = tk.StringVar(value="Not set")
        self.status = tk.StringVar(value="Open Minecraft's prestige menu, then calibrate.")
        self.stats = tk.StringVar()
        setup_tesseract()
        self.build_ui()
        self.listener = keyboard.Listener(on_press=self.on_key)
        self.listener.daemon = True
        self.listener.start()
        root.after(100, self.process_capture)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text=TITLE, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="Standalone scanner: hovers menu slots, reads tooltips, and turns pages.").pack(anchor="w", pady=(0, 10))
        cal = ttk.LabelFrame(main, text="1. Calibrate the menu grid", padding=10)
        cal.pack(fill="x", pady=5)
        ttk.Label(cal, text="Move mouse to the CENTER of the top-left grid slot, then press F8.", wraplength=900).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(cal, text="Move to the CENTER of the bottom-right Next arrow slot, then press F8.", wraplength=900).grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Label(cal, text="First slot:").grid(row=2, column=0, sticky="w")
        ttk.Label(cal, textvariable=self.first_text).grid(row=2, column=1, sticky="w")
        ttk.Button(cal, text="Capture first (F8)", command=lambda: self.arm("first")).grid(row=2, column=2, padx=8)
        ttk.Label(cal, text="Next arrow:").grid(row=3, column=0, sticky="w")
        ttk.Label(cal, textvariable=self.last_text).grid(row=3, column=1, sticky="w")
        ttk.Button(cal, text="Capture Next (F8)", command=lambda: self.arm("last")).grid(row=3, column=2, padx=8)
        settings = ttk.LabelFrame(main, text="2. Scan", padding=10)
        settings.pack(fill="x", pady=5)
        ttk.Label(settings, text="Hover delay (seconds):").pack(side="left")
        ttk.Entry(settings, textvariable=self.delay, width=7).pack(side="left", padx=8)
        ttk.Label(settings, text="Grid: 9 columns × 6 rows").pack(side="left", padx=12)
        ttk.Button(settings, text="Start automatic scan", command=self.start).pack(side="right", padx=4)
        ttk.Button(settings, text="Stop", command=self.stop).pack(side="right", padx=4)
        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=5)
        ttk.Button(actions, text="Export JSON", command=self.export).pack(side="right", padx=3)
        ttk.Button(actions, text="Import JSON", command=self.import_file).pack(side="right", padx=3)
        ttk.Button(actions, text="Save now", command=self.save_default).pack(side="right", padx=3)
        ttk.Label(main, textvariable=self.stats, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 0))
        ttk.Label(main, textvariable=self.status, wraplength=940).pack(anchor="w", pady=5)
        split = ttk.Panedwindow(main, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=3); split.add(right, weight=2)
        ttk.Label(left, text="Collected prices").pack(anchor="w")
        cols = ("rb", "p", "cost", "total")
        self.table = ttk.Treeview(left, columns=cols, show="headings")
        for key, title, width in (("rb","Rebirth",70),("p","Prestige",80),("cost","Individual cost",140),("total","Cumulative spent",145)):
            self.table.heading(key, text=title); self.table.column(key, width=width, anchor="center")
        self.table.pack(fill="both", expand=True)
        ttk.Label(right, text="Latest OCR text (check this if a price is missed)").pack(anchor="w")
        self.ocr = tk.Text(right, wrap="word", font=("Consolas", 9))
        self.ocr.pack(fill="both", expand=True)

    def on_key(self, key):
        if key == keyboard.Key.f8:
            self.capture_request = self.armed_target or "hotkey"

    def arm(self, target):
        self.armed_target = target
        self.status.set("Move the mouse onto the requested Minecraft slot, then press F8 to capture it.")

    def process_capture(self):
        req = self.capture_request
        if req:
            self.capture_request = None
            if req == "hotkey":
                req = "first" if self.first is None else ("last" if self.last is None else None)
            if req:
                self.armed_target = None
                pos = tuple(map(int, pyautogui.position()))
                if req == "first":
                    self.first = pos; self.first_text.set(str(pos))
                    self.status.set("First point saved. Capture the center of the bottom-right Next arrow.")
                else:
                    self.last = pos; self.last_text.set(str(pos))
                    self.status.set("Calibration complete. Ready to scan.")
            else:
                self.status.set("Both points are set. Use the calibration buttons to recapture.")
        self.root.after(100, self.process_capture)

    def geometry(self):
        if not self.first or not self.last:
            raise ValueError("Calibrate the first slot and bottom-right Next arrow with F8.")
        x1,y1 = self.first; x2,y2 = self.last
        if x2 <= x1 or y2 <= y1 or x2-x1 < 96 or y2-y1 < 60:
            raise ValueError("Calibration points are invalid. Select the centers of the first and last grid slots.")
        return x1,y1,(x2-x1)/(COLS-1),(y2-y1)/(ROWS-1)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            self.geometry()
            d = float(self.delay.get())
            if not 0.15 <= d <= 5:
                raise ValueError("Hover delay must be between 0.15 and 5 seconds.")
            pytesseract.get_tesseract_version()
        except Exception as e:
            messagebox.showerror("Cannot start", str(e)); return
        self.stop_event.clear()
        self.worker = threading.Thread(target=self.scan_worker, daemon=True)
        self.worker.start()
        self.status.set("Scan started. Keep Minecraft visible and do not move the mouse.")

    def stop(self):
        self.stop_event.set()
        self.status.set("Stop requested; finishing the current tooltip read.")

    def capture(self):
        with mss.mss() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
        return img, mon

    def read_screen(self):
        img, _ = self.capture()
        img = ImageOps.autocontrast(ImageOps.grayscale(img))
        img = img.resize((img.width*2, img.height*2))
        img = ImageEnhance.Contrast(img).enhance(1.4)
        return pytesseract.image_to_string(img, config="--psm 11")

    def crop_grid(self, img, mon):
        x1,y1 = self.first; x2,y2 = self.last
        box = (max(0,min(x1,x2)-mon["left"]-18),
               max(0,min(y1,y2)-mon["top"]-18),
               min(img.width,max(x1,x2)-mon["left"]+18),
               min(img.height,max(y1,y2)-mon["top"]+18))
        return img.crop(box)

    @staticmethod
    def changed(a,b):
        if a.size != b.size: return True
        hist = ImageChops.difference(a.convert("RGB"),b.convert("RGB")).convert("L").histogram()
        return sum(hist[21:]) / max(1,a.width*a.height) > 0.008

    def scan_worker(self):
        try:
            x1,y1,dx,dy = self.geometry()
            delay = float(self.delay.get())
            pyautogui.FAILSAFE = True
            for _ in range(1000):
                if self.stop_event.is_set(): break
                found_on_page = 0
                for row in range(ROWS):
                    for col in range(COLS):
                        if self.stop_event.is_set(): break
                        if row == ROWS-1 and col == COLS-1:
                            continue
                        px,py = round(x1+col*dx),round(y1+row*dy)
                        pyautogui.moveTo(px,py,duration=0.04)
                        time.sleep(delay)
                        text = self.read_screen()
                        record,self.current_rb = parse_tooltip(text,self.current_rb)
                        self.set_ocr(text)
                        if record:
                            self.records[(record["rebirth"],record["prestige"])] = record
                            found_on_page += 1
                            self.save_silent()
                            self.root.after(0,self.refresh)
                        elif PRESTIGE.search(text):
                            self.unreadable += 1
                        self.set_status(f"Scanning page {self.pages+1}: slot {row*COLS+col+1}/54; found {found_on_page} prices.")
                    if self.stop_event.is_set(): break
                if self.stop_event.is_set(): break
                self.pages += 1
                self.save_silent()
                self.root.after(0,self.refresh)
                pyautogui.moveTo(0,0,duration=0.04); time.sleep(0.2)
                before,mon = self.capture()
                before = self.crop_grid(before,mon)
                pyautogui.click(self.last[0],self.last[1])
                time.sleep(max(1.2,delay*2))
                pyautogui.moveTo(0,0,duration=0.04); time.sleep(0.2)
                after,mon2 = self.capture()
                after = self.crop_grid(after,mon2)
                if not self.changed(before,after):
                    self.set_status("No visible page change after clicking Next. Stopped; saved all collected prices.")
                    break
            else:
                self.set_status("Stopped at the 1000-page safety limit.")
        except pyautogui.FailSafeException:
            self.set_status("Emergency stop triggered (mouse moved to top-left corner).")
        except Exception as e:
            self.set_status("Scan stopped: " + str(e))
        finally:
            self.save_silent()
            self.set_status("Scan stopped. Progress saved to prestige_prices.json.")

    def payload(self):
        vals = sorted(self.records.values(),key=lambda v:(v["rebirth"],v["prestige"]))
        return {"prices":vals,"priceCount":len(vals),"pagesScanned":self.pages}

    def save_silent(self):
        try:
            Path(OUT).write_text(json.dumps(self.payload(),indent=2),encoding="utf-8")
        except Exception as e:
            self.set_status("Save failed: "+str(e))

    def save_default(self):
        self.save_silent()
        self.status.set(f"Saved {len(self.records)} prices to {Path(OUT).resolve()}.")

    def export(self):
        path = filedialog.asksaveasfilename(title="Export prestige_prices.json",initialfile=OUT,defaultextension=".json",filetypes=[("JSON files","*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps(self.payload(),indent=2),encoding="utf-8")
                self.status.set(f"Exported {len(self.records)} prices to {path}.")
            except Exception as e: messagebox.showerror("Export error",str(e))

    def import_file(self):
        path = filedialog.askopenfilename(title="Import prestige_prices.json",filetypes=[("JSON files","*.json"),("All files","*.*")])
        if not path: return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            for item in data.get("prices",[]):
                rb,p=int(item["rebirth"]),int(item["prestige"])
                cost=str(item.get("individualCost",""))
                if rb>=0 and p>=0 and cost:
                    self.records[(rb,p)]={"rebirth":rb,"prestige":p,"individualCost":cost,"cumulativeSpent":str(item.get("cumulativeSpent",""))}
            self.pages=max(self.pages,int(data.get("pagesScanned",0)))
            self.refresh()
            self.status.set("Imported JSON successfully.")
        except Exception as e: messagebox.showerror("Import error",str(e))

    def refresh(self):
        rebirths=sorted({rb for rb,_ in self.records})
        missing=0
        for rb in rebirths:
            max_p=75+25*rb if rb<=6 else 300+50*(rb-7)
            present={p for r,p in self.records if r==rb and 2<=p<=max_p}
            missing += max(0,max_p-1-len(present))
        self.stats.set(f"Prices: {len(self.records)}    Pages: {self.pages}    Rebirths: {len(rebirths)}    Missing expected: {missing}    Unreadable tooltips: {self.unreadable}")
        for row in self.table.get_children(): self.table.delete(row)
        for item in sorted(self.records.values(),key=lambda v:(v["rebirth"],v["prestige"])):
            self.table.insert("","end",values=(item["rebirth"],item["prestige"],item["individualCost"],item["cumulativeSpent"]))

    def set_status(self,text):
        self.root.after(0,lambda:self.status.set(text))

    def set_ocr(self,text):
        def update():
            self.ocr.delete("1.0","end"); self.ocr.insert("1.0",text[:10000])
        self.root.after(0,update)

    def close(self):
        self.stop_event.set()
        try: self.listener.stop()
        except Exception: pass
        self.root.destroy()

if __name__ == "__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
