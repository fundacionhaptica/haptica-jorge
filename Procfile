release: python generate_guide.py static/guia_dashboard.pdf
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300
