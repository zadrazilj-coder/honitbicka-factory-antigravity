"""Dashboard HTTP server pro HONBIČKA FACTORY.
Spouští se lokálně bez externích závislostí a poskytuje REST API i webové rozhraní.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import urllib.parse
from typing import Any
import yaml

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")


def nacti_seznam_her() -> list[dict]:
    skiny_dir = os.path.join(BASE_DIR, "skiny")
    if not os.path.exists(skiny_dir):
        return []

    vysledek = []
    for slug in sorted(os.listdir(skiny_dir)):
        skin_path = os.path.join(skiny_dir, slug)
        if not os.path.isdir(skin_path):
            continue

        report_path = os.path.join(skin_path, "report.json")
        koncept_path = os.path.join(skin_path, "koncept.md")

        data = {
            "slug": slug,
            "stav": "OK",
            "seed": None,
            "archetyp": None,
            "tema": slug,
            "vek": "12-15",
            "format_hracu": "jednotlivci",
            "obtiznost": "stredni",
            "has_pdf": False,
            "has_mermaid": os.path.exists(os.path.join(skin_path, "mapa.mmd")),
            "has_twee": os.path.exists(os.path.join(skin_path, f"{slug}.twee")),
        }

        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    rep = json.load(f)
                    data["stav"] = rep.get("stav", "OK")
                    data["seed"] = rep.get("seed")
                    data["archetyp"] = rep.get("archetyp")
            except Exception:
                pass

        if os.path.exists(koncept_path):
            try:
                with open(koncept_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    m_tema = re.search(r"# Koncept – (.*)", content)
                    if m_tema:
                        data["tema"] = m_tema.group(1).strip()
                    m_arch = re.search(r"- Archetyp:\s*(.*)", content)
                    if m_arch and not data["archetyp"]:
                        data["archetyp"] = m_arch.group(1).strip()
            except Exception:
                pass

        # Najdeme příslušné složky v hotove_hry
        hotove_hry_path = os.path.join(BASE_DIR, "hotove_hry")
        pdf_list = []
        if os.path.exists(hotove_hry_path):
            for root, _, files in os.walk(hotove_hry_path):
                if slug in root:
                    for file in files:
                        if file.endswith(".pdf"):
                            rel_path = os.path.relpath(os.path.join(root, file), BASE_DIR)
                            pdf_list.append({
                                "nazev": file,
                                "cesta": rel_path.replace("\\", "/")
                            })
        data["pdf_soubory"] = pdf_list
        data["has_pdf"] = len(pdf_list) > 0

        vysledek.append(data)

    return vysledek


def nacti_detail_hry(slug: str) -> dict | None:
    skin_path = os.path.join(BASE_DIR, "skiny", slug)
    if not os.path.exists(skin_path):
        return None

    detail = {"slug": slug}
    from honbicka.modely import Mapa, Karta
    from honbicka.export import export_mermaid, export_twee

    for f_name, key in [
        ("koncept.md", "koncept"),
        ("report.json", "report"),
        ("karty.json", "karty"),
        ("mapa.mmd", "mermaid"),
        ("mapa.json", "mapa_json"),
        (f"{slug}.twee", "twee"),
    ]:
        cesta = os.path.join(skin_path, f_name)
        if os.path.exists(cesta):
            try:
                with open(cesta, "r", encoding="utf-8") as f:
                    if f_name.endswith(".json"):
                        detail[key] = json.load(f)
                    else:
                        detail[key] = f.read()
            except Exception as e:
                detail[key] = f"Chyba při načítání: {e}"

    # Najdeme všechny PDF soubory v hotove_hry pro tuto hru
    hotove_hry_path = os.path.join(BASE_DIR, "hotove_hry")
    pdf_list = []
    if os.path.exists(hotove_hry_path):
        for root, _, files in os.walk(hotove_hry_path):
            if slug in root:
                for file in files:
                    if file.endswith(".pdf") or file.endswith(".twee") or file == "INDEX.md":
                        rel_path = os.path.relpath(os.path.join(root, file), BASE_DIR)
                        pdf_list.append({
                            "nazev": file,
                            "cesta": rel_path.replace("\\", "/")
                        })
    detail["soubory"] = pdf_list

    # Dynamic Mermaid & Twee rendering with real story card titles
    if "mapa_json" in detail:
        try:
            mapa_obj = Mapa.model_validate(detail["mapa_json"]) if isinstance(detail["mapa_json"], dict) else Mapa.model_validate_json(detail["mapa_json"])
            karty_objs = None
            if "karty" in detail and isinstance(detail["karty"], list):
                karty_objs = [Karta.model_validate(k) for k in detail["karty"]]
            detail["mermaid"] = export_mermaid(mapa_obj, karty_objs)
            detail["twee"] = export_twee(mapa_obj, karty_objs, nazev=slug)
        except Exception as e:
            pass

    return detail


current_gen_proc: subprocess.Popen | None = None

def spust_generovani(params: dict) -> dict:
    global current_gen_proc
    tema = params.get("tema", "Nova Hra").strip()
    model_name = params.get("model", "").strip()
    slug_tema = re.sub(r"[^a-zA-Z0-9]+", "_", tema).strip("_").lower() or "nova_hra"
    yaml_filename = f"{slug_tema}.yaml"
    yaml_path = os.path.join(BASE_DIR, "zadani", yaml_filename)

    yaml_params = {k: v for k, v in params.items() if k != "model" and v not in (None, "", [])}

    os.makedirs(os.path.join(BASE_DIR, "zadani"), exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_params, f, allow_unicode=True, sort_keys=False)

    def run_job():
        global current_gen_proc
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        cmd = [sys.executable, "-m", "honbicka.cli", "gen", f"zadani/{yaml_filename}"]
        if model_name:
            cmd.extend(["--model", model_name])
        proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=env)
        current_gen_proc = proc
        proc.wait()
        current_gen_proc = None

    t = threading.Thread(target=run_job)
    t.start()

    model_label = model_name if model_name else "Hybrid Routing (gpt-oss:20b / ornith:35b / qwen3.6:27b)"
    return {"status": "OK", "message": f"Generování spuštěno pro zadani/{yaml_filename} s modelem: {model_label}"}

def zastav_generovani() -> dict:
    global current_gen_proc
    if current_gen_proc and current_gen_proc.poll() is None:
        try:
            current_gen_proc.kill()
        except Exception:
            pass
        current_gen_proc = None
        return {"status": "OK", "message": "Generování bylo úspěšně zastaveno."}
    return {"status": "OK", "message": "Žádné generování nebylo aktivní."}


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self) -> None:
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/" or path == "/index.html":
            self.send_static_file(os.path.join(WEB_DIR, "index.html"), "text/html")
        elif path == "/styles.css":
            self.send_static_file(os.path.join(WEB_DIR, "styles.css"), "text/css")
        elif path == "/app.js":
            self.send_static_file(os.path.join(WEB_DIR, "app.js"), "application/javascript")
        elif path == "/api/games":
            self.send_json(nacti_seznam_her())
        elif path.startswith("/api/games/"):
            slug = path[len("/api/games/") :]
            detail = nacti_detail_hry(slug)
            if detail is not None:
                self.send_json(detail)
            else:
                self.send_json({"error": "Hra nenalezena"}, status=404)
        elif path == "/api/mapy":
            mapy_dir = os.path.join(BASE_DIR, "mapy")
            seznam = []
            if os.path.exists(mapy_dir):
                for f_name in sorted(os.listdir(mapy_dir)):
                    if f_name.endswith(".twee"):
                        seznam.append({"nazev": f_name, "cesta": f"mapy/{f_name}"})
            self.send_json(seznam)
        else:
            super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/generate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                params = json.loads(body.decode("utf-8"))
                res = spust_generovani(params)
                self.send_json(res)
            except Exception as e:
                self.send_json({"error": str(e)}, status=400)
        elif self.path == "/api/cancel":
            res = zastav_generovani()
            self.send_json(res)
        else:
            self.send_json({"error": "Neznamy endpoint"}, status=404)

    def send_static_file(self, file_path: str, mime_type: str) -> None:
        if not os.path.exists(file_path):
            self.send_error(404, "File not found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    os.chdir(BASE_DIR)
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"==================================================")
        print(f"HONBIČKA FACTORY Dashboard běží na adresách:")
        print(f"http://localhost:{PORT}")
        print(f"http://127.0.0.1:{PORT}")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer ukončen.")


if __name__ == "__main__":
    main()
