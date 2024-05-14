cd /refract/mosaic-notebooks-manager/app/
source /refract/mosaic-notebooks-manager/env/bin/activate
celery --app=notebooks_api.worker worker --concurrency=5 --loglevel=debug --events