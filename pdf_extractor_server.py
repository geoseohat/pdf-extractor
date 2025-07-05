#!/usr/bin/env python3
"""
Serveur Flask pour extraction PDF avec pdfplumber
Serveur local permanent pour remplacer ngrok
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import io
import logging
import traceback
from werkzeug.utils import secure_filename
import os
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
CORS(app)  # Permet les requêtes cross-origin depuis le frontend

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Vérifie si le fichier est autorisé"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_file):
    """
    Extrait le texte d'un fichier PDF avec pdfplumber
    
    Args:
        pdf_file: Fichier PDF en bytes
        
    Returns:
        dict: Résultat de l'extraction avec texte et métadonnées
    """
    try:
        logger.info("🔍 Début extraction PDF avec pdfplumber...")
        
        # Ouvre le PDF avec pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_file)) as pdf:
            text_content = []
            total_pages = len(pdf.pages)
            
            logger.info(f"📄 PDF ouvert: {total_pages} page(s) détectée(s)")
            
            # Extrait le texte de chaque page
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    logger.info(f"📖 Extraction page {page_num}/{total_pages}...")
                    page_text = page.extract_text()
                    
                    if page_text:
                        # Nettoie et formate le texte
                        cleaned_text = page_text.strip()
                        if cleaned_text:
                            text_content.append(f"\n=== PAGE {page_num} ===\n\n{cleaned_text}")
                            logger.info(f"✅ Page {page_num}: {len(cleaned_text)} caractères extraits")
                        else:
                            logger.warning(f"⚠️ Page {page_num}: Texte vide après nettoyage")
                    else:
                        logger.warning(f"⚠️ Page {page_num}: Aucun texte extrait")
                        
                except Exception as page_error:
                    logger.error(f"❌ Erreur page {page_num}: {str(page_error)}")
                    continue
            
            # Combine tout le texte
            full_text = "\n".join(text_content)
            
            # Statistiques
            word_count = len(full_text.split()) if full_text else 0
            char_count = len(full_text)
            
            # Détermine la qualité d'extraction
            if char_count > 1000:
                quality = 'excellent'
            elif char_count > 500:
                quality = 'good'
            elif char_count > 100:
                quality = 'poor'
            else:
                quality = 'failed'
            
            logger.info(f"📊 Extraction terminée: {char_count} caractères, {word_count} mots, qualité: {quality}")
            
            return {
                'success': True,
                'text': full_text,
                'metadata': {
                    'pages': total_pages,
                    'characters': char_count,
                    'words': word_count,
                    'extraction_method': 'pdfplumber',
                    'quality': quality,
                    'extraction_time': datetime.now().isoformat()
                }
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur extraction PDF: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'text': '',
            'metadata': {
                'pages': 0,
                'characters': 0,
                'words': 0,
                'extraction_method': 'pdfplumber_failed',
                'quality': 'failed',
                'extraction_time': datetime.now().isoformat()
            }
        }

@app.route('/extract-pdf-text', methods=['POST', 'OPTIONS'])
def extract_pdf_text():
    """Endpoint principal pour l'extraction PDF"""
    
    # Gestion CORS pour les requêtes OPTIONS
    if request.method == 'OPTIONS':
        logger.info("📡 Requête OPTIONS reçue (CORS)")
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        logger.info("📤 Nouvelle requête d'extraction PDF reçue")
        
        # Vérification de la présence du fichier
        if 'file' not in request.files:
            logger.error("❌ Aucun fichier dans la requête")
            return jsonify({
                'success': False,
                'error': 'Aucun fichier fourni',
                'text': ''
            }), 400
        
        file = request.files['file']
        
        # Vérification du nom de fichier
        if file.filename == '':
            logger.error("❌ Nom de fichier vide")
            return jsonify({
                'success': False,
                'error': 'Nom de fichier vide',
                'text': ''
            }), 400
        
        # Vérification de l'extension
        if not allowed_file(file.filename):
            logger.error(f"❌ Extension non autorisée: {file.filename}")
            return jsonify({
                'success': False,
                'error': 'Seuls les fichiers PDF sont autorisés',
                'text': ''
            }), 400
        
        # Lecture du fichier
        file_content = file.read()
        file_size = len(file_content)
        
        logger.info(f"📄 Fichier reçu: {file.filename} ({file_size:,} bytes)")
        
        # Vérification de la taille
        if file_size > MAX_FILE_SIZE:
            logger.error(f"❌ Fichier trop volumineux: {file_size:,} bytes")
            return jsonify({
                'success': False,
                'error': f'Fichier trop volumineux (max {MAX_FILE_SIZE//1024//1024}MB)',
                'text': ''
            }), 400
        
        # Extraction du texte
        logger.info("🔄 Début de l'extraction...")
        result = extract_text_from_pdf(file_content)
        
        # Préparation de la réponse
        response_data = {
            'success': result['success'],
            'text': result['text'],
            'filename': secure_filename(file.filename),
            'metadata': result['metadata']
        }
        
        if not result['success']:
            response_data['error'] = result['error']
            logger.error(f"❌ Échec extraction: {result['error']}")
            return jsonify(response_data), 500
        
        logger.info(f"✅ Extraction réussie: {len(result['text']):,} caractères extraits")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Erreur serveur: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Erreur serveur: {str(e)}',
            'text': ''
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de vérification de santé"""
    logger.info("💓 Vérification de santé demandée")
    return jsonify({
        'status': 'healthy',
        'service': 'PDF Extractor with pdfplumber',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'dependencies': {
            'pdfplumber': 'installed',
            'flask': 'installed',
            'flask-cors': 'installed'
        }
    })

@app.route('/', methods=['GET'])
def index():
    """Page d'accueil du serveur"""
    return jsonify({
        'message': '🚀 Serveur d\'extraction PDF avec pdfplumber',
        'status': 'running',
        'endpoints': {
            '/extract-pdf-text': 'POST - Extraction de texte PDF',
            '/health': 'GET - Vérification de santé',
            '/': 'GET - Informations du serveur'
        },
        'usage': {
            'curl_test': 'curl -X POST -F "file=@document.pdf" http://localhost:5678/extract-pdf-text',
            'cors_test': 'curl -X OPTIONS http://localhost:5678/extract-pdf-text'
        },
        'limits': {
            'max_file_size': f'{MAX_FILE_SIZE//1024//1024}MB',
            'allowed_extensions': list(ALLOWED_EXTENSIONS)
        }
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVEUR D'EXTRACTION PDF AVEC PDFPLUMBER")
    print("=" * 60)
    print("📄 Extraction haute qualité avec pdfplumber")
    print("🌐 Serveur accessible sur: http://localhost:5678")
    print("🔗 Endpoint principal: http://localhost:5678/extract-pdf-text")
    print("💓 Santé du serveur: http://localhost:5678/health")
    print("")
    print("🧪 TESTS RAPIDES:")
    print("   curl -X OPTIONS http://localhost:5678/extract-pdf-text")
    print("   curl -X POST -F 'file=@document.pdf' http://localhost:5678/extract-pdf-text")
    print("")
    print("📦 DÉPENDANCES REQUISES:")
    print("   pip install flask flask-cors pdfplumber")
    print("")
    print("⚠️  IMPORTANT:")
    print("   - Gardez ce serveur en cours d'exécution")
    print("   - L'application web l'utilisera automatiquement")
    print("   - En cas d'arrêt, l'app basculera vers PDF.js")
    print("=" * 60)
    
    try:
        # Vérification des dépendances
        import flask
        import flask_cors
        import pdfplumber
        print("✅ Toutes les dépendances sont installées")
        print("")
        
        # Démarrage du serveur
        print("🔄 Démarrage du serveur...")
        app.run(
            host='0.0.0.0',  # Accessible depuis toutes les interfaces
            port=5678,       # Port fixe
            debug=False,     # Mode production pour plus de stabilité
            threaded=True    # Support multi-thread
        )
        
    except ImportError as e:
        print(f"❌ Dépendance manquante: {e}")
        print("📦 Installez les dépendances avec:")
        print("   pip install flask flask-cors pdfplumber")
        exit(1)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
        exit(1)