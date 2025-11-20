from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route("/", methods=["POST"])
def ejecutar_script():
    data = request.json

    codigo = data.get("codigo")
    password = data.get("password")

    if not codigo or not password:
        return jsonify({"error": "Faltan datos."}), 400

    script_path = os.path.join(os.path.dirname(__file__), "scrape_horario.py")

    try:
        resultado = subprocess.run(
           ["/root/horario_api/venv/bin/python", script_path, codigo, password],
	   capture_output=True,
            text=True,
            timeout=60
        )

        if resultado.returncode != 0:
            return jsonify({"error": "Falló la ejecución del script.", "detalle": resultado.stderr}), 500

        import json as _json
        horario = None
        for line in resultado.stdout.splitlines():
            try:
                posible_json = _json.loads(line)
                if isinstance(posible_json, list):
                    horario = posible_json
                    break
            except Exception:
                continue
        if horario is not None:
            return jsonify(horario)
        else:
            # Si no se pudo extraer el horario, devolver un array vacío
            return jsonify([])

    except subprocess.TimeoutExpired:
        return jsonify({"error": "El script tardó demasiado en ejecutarse."}), 504

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
