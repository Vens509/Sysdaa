"""
WSGI config for sysdaa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.wsgi import get_wsgi_application

# 1. Définir le chemin de base (le dossier qui contient manage.py et .env)
# Path(__file__) est ce fichier (wsgi.py), .parent est le dossier 'sysdaa', 
# .parent.parent est la racine du projet 'sysdaa_root'
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Charger le fichier .env AVANT d'importer ou de configurer Django
# Cela permet à settings.py de voir DJANGO_DEBUG=0
load_dotenv(BASE_DIR / ".env")

# 3. Définir le module de réglages par défaut
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sysdaa.settings')

# 4. Initialiser l'application WSGI pour Apache
application = get_wsgi_application()