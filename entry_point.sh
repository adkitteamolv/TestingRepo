cd /refract/mosaic-notebooks-manager/app/
source /refract/mosaic-notebooks-manager/env/bin/activate
alembic upgrade head
gunicorn --config=gunicorn.py notebooks_api.app