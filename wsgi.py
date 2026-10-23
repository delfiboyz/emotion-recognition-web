"""Entry point produksi: gunicorn -w 1 --threads 8 -b 0.0.0.0:5000 wsgi:app"""

from emotion_api import create_app

app = create_app()
