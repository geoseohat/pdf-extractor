#!/usr/bin/env python3
"""
Serveur Flask pour extraction PDF avec pdfplumber
Fonctionne en local (localhost:5678) ET sur Render/Railway (PORT imposé).
"""

import io
import logging
import traceback
import os                    # ← nouveau : pour lire la variable d’environnement PORT
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pdfplumber

# ────────────────────────────────────────────────────────────
# LOGGING
# ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 10 * 1024 * 1024          # 10 MB
ALLOWED_EXTENSIONS = {"pdf"}

# ────────────────────────────────────────────────────────────
# APP FLASK
# ────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # autorise toutes les origines (front local ou déployé)

# ────────────────────────────────────────────────────────────
# OUTILS
# ────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Extraction texte + métadonnées depuis un PDF (pdfplumber).
    Renvoie un dict {'success': True/False, 'text': str, 'metadata': {...}}
    """
    try:
        logger.info("🔍 Extraction PDF…")
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = len(pdf.pages)
            logger.info(f"📄 {pages} page(s) détectée(s)")
            parts = []
            for i, page in enumerate(pdf.pages, 1):
                try:
                    txt = page.extract_text() or ""
                    txt = txt.strip()
                    if txt:
                        parts.append(f"\n=== PAGE {i} ===\n\n{txt}")
                        logger.info(f"✅ Page {i}: {len(txt)} caractères")
                    else:
                        logger.warning(f"⚠️ Page {i}: texte vide")
                except Exception as perr:
                    logger.error(f"❌ Erreur page {i}: {perr}")
                    continue

        full_text = "\n".join(parts)
        char_cnt = len(full_text)
        word_cnt = len(full_text.split())
        quality = (
            "excellent" if char_cnt > 1000
            else "good" if char_cnt > 500
            else "poor" if char_cnt > 100
            else "failed"
        )
        return {
            "success": True,
            "text": full_text,
            "metadata": {
                "pages": pages,
                "characters": char_cnt,
                "words": word_cnt,
                "quality": quality,
                "method": "pdfplumber",
                "extraction_time": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"❌ Extraction échouée: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "metadata": {
                "pages": 0,
                "characters": 0,
                "words": 0,
                "quality": "failed",
                "method": "pdfplumber_failed",
                "extraction_time": datetime.utcnow().isoformat()
            }
        }

# ────────────────────────────────────────────────────────────
# ENDPOINTS
# ────────────────────────────────────────────────────────────
@app.route("/extract-pdf-text", methods=["POST", "OPTIONS"])
def extract_pdf_text():
    # OPTIONS → CORS pre-flight
    if request.method == "OPTIONS":
        resp = jsonify({"status": "ok"})
        resp.headers.add("Access-Control-Allow-Origin", "*")
        resp.headers.add("Access-Control-Allow-Headers", "Content-Type")
        resp.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return resp

    # POST
    if "file" not in request.files:
        return jsonify({"success": False, "error": "Aucun fichier fourni"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Nom de fichier vide"}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Format non autorisé"}), 400

    data = file.read()
    if len(data) > MAX_FILE_SIZE:
        return jsonify({"success": False, "error": "Fichier trop volumineux"}), 400

    result = extract_text_from_pdf(data)
    if not result["success"]:
        return jsonify(result), 500

    return jsonify({
        "success": True,
        "filename": secure_filename(file.filename),
        "text": result["text"],
        "metadata": result["metadata"]
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "PDF Extractor (pdfplumber)",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route("/")
def index():
    return jsonify({
        "message": "🚀 Serveur d'extraction PDF (pdfplumber) opérationnel",
        "endpoints": {
            "/extract-pdf-text": "POST",
            "/health": "GET"
        }
    })

# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SERVEUR D'EXTRACTION PDF AVEC PDFPLUMBER")
    print("=" * 60)
    print("📄 Extraction haute qualité avec pdfplumber")
    print("🔗 Endpoint: /extract-pdf-text")
    print("💓 Santé:    /health")
    print("=" * 60)

    try:
        port = int(os.environ.get("PORT", 5678))   # ← PORT imposé par Render, sinon 5678
        print(f"🌐 Écoute sur le port {port} (host 0.0.0.0)")
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
        traceback.print_exc()
        exit(1)
