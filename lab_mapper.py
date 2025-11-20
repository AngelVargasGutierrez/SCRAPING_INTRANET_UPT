import sys
import os
import json
import re
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
from scrape_horario import iniciar_navegador, login
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import cv2
import pytesseract

def fetch_html(token):
    url = f"https://net.upt.edu.pe/Academico/website/index.php?sesion={token}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        return r.read()

def fetch_html_selenium(token):
    drv = iniciar_navegador()
    try:
        drv.get(f"https://net.upt.edu.pe/Academico/website/index.php?sesion={token}")
        return drv.page_source
    finally:
        try:
            drv.quit()
        except Exception:
            pass

def parse_labs_dom(token):
    drv = iniciar_navegador()
    try:
        drv.get(f"https://net.upt.edu.pe/Academico/website/index.php?sesion={token}")
        try:
            WebDriverWait(drv, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table//td[contains(., 'LAB ') or contains(., 'P-') or contains(., 'Lab ')]"))
            )
        except Exception:
            pass
        rows = drv.find_elements(By.CSS_SELECTOR, "table tr")
        labs_by_code = {}
        header = []
        day_idxs = []
        if rows:
            header = [c.text.strip() for c in rows[0].find_elements(By.CSS_SELECTOR, "th,td")]
            dias = [d for d in header if d.lower() in ["lunes","martes","miércoles","miercoles","jueves","viernes","sábado","sabado","domingo"]]
            day_idxs = [header.index(d) for d in dias]
        for r in rows[1:]:
            cols = r.find_elements(By.CSS_SELECTOR, "td")
            if not cols:
                continue
            codigo = cols[0].text.strip()
            if not codigo:
                continue
            labs = {}
            for idx, dia in zip(day_idxs, dias):
                if idx < len(cols):
                    txt = cols[idx].text
                    m = re.findall(r"\bLAB\s+[A-Z]\b", txt)
                    if not m:
                        m = re.findall(r"\bP-\d+\b", txt)
                    if m:
                        labs[dia] = " - ".join(m)
            labs_by_code[codigo] = labs
        return labs_by_code
    finally:
        try:
            drv.quit()
        except Exception:
            pass

def parse_labs_images(dir_path):
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    files = []
    for name in os.listdir(dir_path):
        p = os.path.join(dir_path, name)
        if os.path.isfile(p) and os.path.splitext(name)[1].lower() in exts:
            files.append(p)
    text = []
    for fp in files:
        img = cv2.imread(fp)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_LINEAR)
        _, thr = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cfg = "--psm 4 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "
        s = pytesseract.image_to_string(thr, config=cfg)
        text.append(s)
    full = "\n".join(t.upper() for t in text)
    labs_by_code = {}
    it = list(re.finditer(r"[A-Z]{2}-\d{3,4}", full))
    for i, m in enumerate(it):
        start = m.start()
        end = it[i+1].start() if i+1 < len(it) else len(full)
        block = full[start:end]
        code = m.group(0)
        labs = {}
        day_pat = r"(LUNES|MARTES|MIÉRCOLES|MIERCOLES|JUEVES|VIERNES|SÁBADO|SABADO|DOMINGO)"
        for dm in re.finditer(day_pat, block):
            dname = dm.group(0).lower()
            seg = block[dm.end():dm.end()+120]
            labm = re.findall(r"\bLAB\s+[A-Z]\b", seg)
            if not labm:
                labm = re.findall(r"\bP-\d+\b", seg)
            if labm:
                labs[dname] = " - ".join(labm)
        agg = re.findall(r"\bLAB\s+[A-Z]\b", block)
        if not agg:
            agg = re.findall(r"\bP-\d+\b", block)
        if agg and not labs:
            labs["labs"] = " - ".join(sorted(set(agg)))
        labs_by_code[code] = labs
    return labs_by_code

def parse_labs_from_json_text(text):
    labs_by_code = {}
    it = list(re.finditer(r'"codigo"\s*:\s*"([A-Z]{2}-\d{3,4})"', text))
    for i, m in enumerate(it):
        code = m.group(1)
        start = m.start()
        end = it[i+1].start() if i+1 < len(it) else len(text)
        block = text[start:end]
        labs = {}
        for dm in re.finditer(r'"dia"\s*:\s*"([^"]+)"', block):
            dname = dm.group(1).strip().lower()
            seg = block[dm.end():dm.end()+150]
            labm = re.findall(r'"aula"\s*:\s*"([^"]+)"', seg)
            if not labm:
                labm = re.findall(r'"lugar"\s*:\s*"([^"]+)"', seg)
            if labm:
                labs[dname] = ' - '.join(labm)
        if labs:
            labs_by_code[code] = labs
    return labs_by_code

def parse_labs_from_logged_driver(drv, token):
    drv.get(f"https://net.upt.edu.pe/Academico/website/index.php?sesion={token}")
    try:
        WebDriverWait(drv, 10).until(
            EC.presence_of_element_located((By.XPATH, "//table//td[contains(., 'LAB ') or contains(., 'P-') or contains(., 'Lab ')]"))
        )
    except Exception:
        pass
    rows = drv.find_elements(By.CSS_SELECTOR, "table tr")
    labs_by_code = {}
    header = []
    day_idxs = []
    if rows:
        header = [c.text.strip().lower() for c in rows[0].find_elements(By.CSS_SELECTOR, "th,td")]
        dias = [d for d in header if d in ["lunes","martes","miércoles","miercoles","jueves","viernes","sábado","sabado","domingo"]]
        day_idxs = [header.index(d) for d in dias] if dias else list(range(3, min(10, len(header))))
        if not dias and day_idxs:
            dias = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][:len(day_idxs)]
    for r in rows[1:]:
        cols = r.find_elements(By.CSS_SELECTOR, "td")
        if not cols:
            continue
        codigo = cols[0].text.strip()
        if not codigo:
            continue
        labs = {}
        for idx, dia in zip(day_idxs, dias):
            if idx < len(cols):
                txt = cols[idx].text
                m = re.findall(r"\bLAB\s+[A-Z]\b", txt)
                if not m:
                    m = re.findall(r"\bP-\d+\b", txt)
                if m:
                    labs[dia] = " - ".join(m)
        labs_by_code[codigo] = labs
    return labs_by_code

def parse_labs(html):
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in t.find_all("th")]
        if any("Código" in h for h in ths):
            table = t
            break
    if table is None:
        return {}
    rows = table.find_all("tr")
    if not rows:
        return {}
    header = [th.get_text(strip=True) for th in rows[0].find_all(["th","td"])]
    dias = [d for d in header if d.lower() in ["lunes","martes","miércoles","miercoles","jueves","viernes","sábado","sabado","domingo"]]
    day_index = [header.index(d) for d in dias]
    labs_by_code = {}
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if not tds:
            continue
        codigo = tds[0].get_text(strip=True)
        if not codigo:
            continue
        labs = {}
        for idx, dia in zip(day_index, dias):
            if idx >= len(tds):
                continue
            txt = tds[idx].get_text("\n", strip=True)
            m = re.findall(r"\bLAB\s+[A-Z]\b", txt)
            if not m:
                m = re.findall(r"\bP-\d+\b", txt)
            if m:
                labs[dia] = " - ".join(m)
        labs_by_code[codigo] = labs
    return labs_by_code

def load_scraped_json(codigo, path=None):
    if path is None:
        path = os.path.join("scripts", "horarios_json", f"{codigo}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def merge_labs(horarios, labs_by_code):
    if horarios:
        out = []
        for h in horarios:
            cod = h.get("codigo", "").strip()
            labs = labs_by_code.get(cod, {})
            merged = dict(h)
            # Si hay labs detectados, reemplaza las columnas de días por el nombre del lab
            for dia in ["lunes","martes","miércoles","miercoles","jueves","viernes","sábado","sabado","domingo"]:
                if dia in labs and labs[dia]:
                    merged[dia] = labs[dia]
            if labs:
                merged["labs"] = labs
            out.append(merged)
        return out
    out = []
    for cod, labs in labs_by_code.items():
        out.append({"codigo": cod, "labs": labs})
    return out

def save_output(codigo, data):
    out_dir = os.path.join("scripts", "labs_json")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{codigo}.labs.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path

def main():
    if len(sys.argv) < 2:
        print("Uso: python lab_mapper.py <codigo> [token_sesion|password] [ruta_json]")
        sys.exit(1)
    codigo = sys.argv[1]
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None
    token = None
    ruta_json = sys.argv[3] if len(sys.argv) > 3 else None
    horarios = load_scraped_json(codigo, ruta_json)
    labs_by_code = {}
    if arg2:
        if os.path.exists(arg2) and arg2.lower().endswith('.html'):
            with open(arg2, 'r', encoding='utf-8', errors='ignore') as f:
                labs_by_code = parse_labs(f.read())
        elif os.path.exists(arg2) and arg2.lower().endswith('.json'):
            with open(arg2, 'r', encoding='utf-8', errors='ignore') as f:
                labs_by_code = parse_labs_from_json_text(f.read())
        elif os.path.isdir(arg2):
            json_path = os.path.join(arg2, 'horarios.json')
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8', errors='ignore') as f:
                    labs_by_code = parse_labs_from_json_text(f.read())
            else:
                labs_by_code = parse_labs_images(arg2)
        else:
            if arg2.isdigit() and len(arg2) <= 6:
                drv = iniciar_navegador()
                token = login(drv, codigo, arg2)
                if token:
                    labs_by_code = parse_labs_from_logged_driver(drv, token)
                try:
                    drv.quit()
                except Exception:
                    pass
            else:
                token = arg2
    if token:
        try:
            try:
                html = fetch_html(token)
            except Exception:
                html = None
            if not html or len(html) < 1000:
                labs_by_code = parse_labs_dom(token)
            else:
                labs_by_code = parse_labs(html)
        except Exception:
            labs_by_code = {}
    if not labs_by_code and ruta_json and ruta_json.lower().endswith('.html') and os.path.exists(ruta_json):
        with open(ruta_json, 'r', encoding='utf-8', errors='ignore') as f:
            labs_by_code = parse_labs(f.read())
    if not labs_by_code:
        labs_by_code = {}
        for h in horarios:
            cod = h.get("codigo", "").strip()
            labs = {}
            for dia in ["lunes","martes","miércoles","miercoles","jueves","viernes","sábado","sabado","domingo"]:
                txt = h.get(dia, "")
                if not txt:
                    continue
                m = re.findall(r"\bLAB\s+[A-Z]\b", txt)
                if not m:
                    m = re.findall(r"\bP-\d+\b", txt)
                if m:
                    labs[dia] = " - ".join(m)
            labs_by_code[cod] = labs
    merged = merge_labs(horarios, labs_by_code)
    out_path = save_output(codigo, merged)
    print(json.dumps(merged, ensure_ascii=False))
    print(out_path)

if __name__ == "__main__":
    main()