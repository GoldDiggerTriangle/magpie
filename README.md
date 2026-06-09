# Gold, Stamps & Phonetech

Sprint 0 implements the Django backend skeleton and data model only. Sprint 1 UI/API workflows are intentionally not built yet.

## Backend quick start

Prerequisites: Python 3.12 and Docker.

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
cd ..
docker compose up -d db
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py seed
python manage.py runserver
```

Admin will be available at http://localhost:8000/admin/.

## Sprint 0 scope

Included:

- Django project/settings split into `base`, `dev`, and `prod`
- Core domain models, migrations, and Django admin registration
- Transaction-safe SKU sequence service
- Permissive attribute schema registry seam
- Idempotent seed command
- Backup/export management command skeletons
- Local file storage adapter
- Stub integration ports for eBay, vision/OCR, and metals pricing
- Minimal Vite proxy configuration for later frontend work

Not included in Sprint 0:

- React screens and Sprint 1 API viewsets
- AI, OCR, valuation, eBay, listing generation
- Celery, Redis, offline sync, or real per-category schemas

## Backup and export

```powershell
cd backend
python manage.py backup
python manage.py export_items --csv ..\backups\items.csv
```

`backup` writes a zip under `backups/` containing database data, media files, and a manifest. It uses `pg_dump` for PostgreSQL when available and falls back to Django `dumpdata` JSON.

For restore in Sprint 0, extract the zip, restore `db.dump` with `pg_restore` when it is a PostgreSQL dump or load `db.json` with `python manage.py loaddata`, then copy the extracted `media/` directory contents back into `backend/media_files/`.
