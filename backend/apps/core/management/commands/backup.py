import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


LOCAL_APP_LABELS = {
    "core",
    "catalog",
    "locations",
    "acquisitions",
    "inventory",
    "photos",
    "research",
    "valuation",
    "listing",
}


class Command(BaseCommand):
    help = "Create a Sprint 0 backup bundle containing database data and media files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(settings.REPO_ROOT / "backups"),
            help="Directory where the backup zip should be written.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        zip_path = output_dir / f"backup-{timestamp}.zip"

        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            db_artifact = self.write_database_artifact(temp_dir)
            manifest_path = self.write_manifest(temp_dir, db_artifact.name)

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(db_artifact, db_artifact.name)
                archive.write(manifest_path, "manifest.json")
                self.write_media_files(archive)

        self.stdout.write(self.style.SUCCESS(f"Backup written to {zip_path}"))

    def write_database_artifact(self, temp_dir: Path) -> Path:
        if connection.vendor == "postgresql":
            pg_dump = self.try_pg_dump(temp_dir)
            if pg_dump is not None:
                return pg_dump

        json_path = temp_dir / "db.json"
        with json_path.open("w", encoding="utf-8") as handle:
            call_command(
                "dumpdata",
                "core",
                "catalog",
                "locations",
                "acquisitions",
                "inventory",
                "photos",
                "research",
                "valuation",
                "listing",
                indent=2,
                stdout=handle,
            )
        return json_path

    def try_pg_dump(self, temp_dir: Path) -> Path | None:
        if shutil.which("pg_dump") is None:
            self.stderr.write("pg_dump not found; falling back to dumpdata JSON.")
            return None

        db = connection.settings_dict
        dump_path = temp_dir / "db.dump"
        command = [
            "pg_dump",
            "--format=custom",
            "--file",
            str(dump_path),
        ]
        if db.get("HOST"):
            command.extend(["--host", str(db["HOST"])])
        if db.get("PORT"):
            command.extend(["--port", str(db["PORT"])])
        if db.get("USER"):
            command.extend(["--username", str(db["USER"])])
        command.append(str(db["NAME"]))

        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = str(db["PASSWORD"])

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.stderr.write("pg_dump failed; falling back to dumpdata JSON.")
            if result.stderr:
                self.stderr.write(result.stderr.strip())
            return None
        return dump_path

    def write_manifest(self, temp_dir: Path, db_artifact_name: str) -> Path:
        row_counts = {}
        for model in apps.get_models():
            if model._meta.app_label in LOCAL_APP_LABELS:
                row_counts[model._meta.label_lower] = model.objects.count()

        manifest = {
            "created_at": timezone.now().isoformat(),
            "database_artifact": db_artifact_name,
            "django_version": django.get_version(),
            "media_root": str(settings.MEDIA_ROOT),
            "row_counts": row_counts,
        }
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path

    def write_media_files(self, archive: zipfile.ZipFile) -> None:
        archive.writestr("media/", "")
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            return
        for path in media_root.rglob("*"):
            if path.is_file():
                archive.write(path, Path("media") / path.relative_to(media_root))
