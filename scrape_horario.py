import os
import re
import time
import json
import shutil
import tempfile
import pandas as pd
import pytesseract
import cv2
import sys

from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import os
_prefix = r"C:\Users\Angel\scoop\persist\tesseract"
_td = os.path.join(_prefix, "tessdata")
_eng1 = os.path.join(_prefix, 'eng.traineddata')
_eng2 = os.path.join(_td, 'eng.traineddata')
if os.path.exists(_eng1):
    os.environ['TESSDATA_PREFIX'] = _prefix
elif os.path.exists(_eng2):
    os.environ['TESSDATA_PREFIX'] = _td
else:
    os.environ['TESSDATA_PREFIX'] = r"C:\Users\Angel\scoop\apps\tesseract-languages\current"
pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"


class CaptchaSolver:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def procesar_imagen(self, driver, img_element):
        temp_path = os.path.join(self.temp_dir, "captcha.png")
        img_element.screenshot(temp_path)
        return temp_path

    def resolver(self, img_path):
        try:
            img = cv2.imread(img_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inverted = cv2.bitwise_not(gray)
            _, thr1 = cv2.threshold(inverted, 127, 255, cv2.THRESH_BINARY)
            up1 = cv2.resize(thr1, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
            config_base = '--oem 1 -c tessedit_char_whitelist=0123456789 -c classify_bln_numeric_mode=1 --dpi 300'
            for img_try, psm in [(thr1, 8), (up1, 7)]:
                texto = pytesseract.image_to_string(img_try, config=f'--psm {psm} ' + config_base, lang='eng')
                r = re.sub(r'\D', '', texto)
                if len(r) == 4:
                    return r
            blur = cv2.medianBlur(up1, 3)
            _, thr2 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            texto3 = pytesseract.image_to_string(thr2, config='--psm 7 ' + config_base, lang='eng')
            r3 = re.sub(r'\D', '', texto3)
            if len(r3) == 4:
                return r3
            _, thr4 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            up2 = cv2.resize(thr4, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
            texto4 = pytesseract.image_to_string(up2, config='--psm 8 ' + config_base, lang='eng')
            r4 = re.sub(r'\D', '', texto4)
            return r4 if len(r4) == 4 else None
        except Exception as e:
            print(" Error OCR:", e)
            return None

    def limpiar(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def iniciar_navegador():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless")
    options.add_argument("--force-device-scale-factor=2")
    options.add_argument("--window-size=1280,720")
    return webdriver.Chrome(options=options)


def login(driver, codigo, password):
    driver.get("https://net.upt.edu.pe/index2.php?n=a38c138bbf10e4d5d2fbf6cb08bb280b")
    time.sleep(2)

    driver.find_element(By.ID, "t1").send_keys(codigo)

    img = driver.find_element(By.CSS_SELECTOR, "#td_cuerpo_imagen_aleatoria img")
    solver = CaptchaSolver()
    img_path = solver.procesar_imagen(driver, img)
    captcha_auto = solver.resolver(img_path)
    captcha_final = captcha_auto
    intentos = 0
    while not captcha_final and intentos < 3:
        time.sleep(0.3)
        img = driver.find_element(By.CSS_SELECTOR, "#td_cuerpo_imagen_aleatoria img")
        img_path = solver.procesar_imagen(driver, img)
        captcha_final = solver.resolver(img_path)
        intentos += 1
    if not captcha_final:
        print(" No se pudo leer el captcha automáticamente.")
        return None

    driver.find_element(By.ID, "kamousagi").send_keys(captcha_final)

    # Usa la contraseña recibida como argumento
    botones = driver.find_elements(By.CLASS_NAME, "btn_cuerpo_login_number")
    mapa = {b.text.strip(): b for b in botones if b.text.strip().isdigit()}
    for d in password:
        if d in mapa:
            mapa[d].click()
            time.sleep(0.2)

    driver.find_element(By.ID, "Submit").click()
    time.sleep(3)

    match = re.search(r'sesion=([A-Za-z0-9]+)', driver.current_url)
    if not match:
        print(" Login fallido. Revisa captcha o contraseña.")
        solver.limpiar()
        return None

    solver.limpiar()
    return match.group(1)


def ordenar_horarios(texto):
    # Divide por " - ", elimina vacíos, ordena y vuelve a unir
    partes = [h.strip() for h in texto.split(" - ") if h.strip()]
    def hora_inicio(h):
        # Extrae la hora de inicio para ordenar, asume formato HH:MM o HH:MM-HH:MM
        if '-' in h:
            return h.split('-')[0].strip()
        return h
    partes.sort(key=hora_inicio)
    return " - ".join(partes)


def extraer_horario(driver, token):
    driver.get(f"https://net.upt.edu.pe/alumno.php?mihorario=1&sesion={token}")
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    tabla = soup.find("table", {"align": "center", "style": "font-size:12px;"})
    if not tabla:
        return []

    filas = tabla.find_all("tr")[1:]
    horarios = []
    for fila in filas:
        cols = fila.find_all("td")
        if len(cols) < 10:
            continue
        horarios.append({
            "codigo": cols[0].text.strip(),
            "curso": cols[1].text.strip(),
            "seccion": cols[2].text.strip(),
            "lunes": ordenar_horarios(cols[3].text.strip().replace("\n", " - ")),
            "martes": ordenar_horarios(cols[4].text.strip().replace("\n", " - ")),
            "miércoles": ordenar_horarios(cols[5].text.strip().replace("\n", " - ")),
            "jueves": ordenar_horarios(cols[6].text.strip().replace("\n", " - ")),
            "viernes": ordenar_horarios(cols[7].text.strip().replace("\n", " - ")),
            "sábado": ordenar_horarios(cols[8].text.strip().replace("\n", " - ")),
            "domingo": ordenar_horarios(cols[9].text.strip().replace("\n", " - ")),
        })
    return horarios


def guardar_archivos(horarios, codigo):
    os.makedirs("scripts/horarios_json", exist_ok=True)
    os.makedirs("scripts/horarios_excel", exist_ok=True)

    with open(f"scripts/horarios_json/{codigo}.json", "w", encoding="utf-8") as f:
        json.dump(horarios, f, ensure_ascii=False, indent=4)

    df = pd.DataFrame(horarios)
    df.to_excel(f"scripts/horarios_excel/{codigo}.xlsx", index=False)

    print(f" Horario guardado como JSON y Excel en scripts/horarios_json/ y horarios_excel/")


def main():
    #  Leer argumentos desde línea de comandos
    if len(sys.argv) < 3:
        print(" Debes proporcionar el código y la contraseña como argumentos.")
        print("Ejemplo: python scrape_horario.py 2020068762 262001")
        exit(1)

    codigo = sys.argv[1]
    password = sys.argv[2]

    driver = iniciar_navegador()
    try:
        token = login(driver, codigo, password)
        if not token:
            print(json.dumps([], ensure_ascii=False))
            return
        horarios = extraer_horario(driver, token)
        guardar_archivos(horarios, codigo)
        print(json.dumps(horarios, ensure_ascii=False))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
