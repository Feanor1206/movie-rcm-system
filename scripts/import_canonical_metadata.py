"""
CLI Tool for Importing Canonical Movie Metadata (REC-01).

Usage:
  python scripts/import_canonical_metadata.py --input docs/contracts/canonical_catalog_sample.valid.json --dry-run
  python scripts/import_canonical_metadata.py --input docs/contracts/canonical_catalog_sample.valid.json --output data/snapshot/canonical_catalog.json
"""

import sys
import argparse
from pathlib import Path

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
sys.path.insert(0, str(backend_fastapi_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from services.canonical_importer import CanonicalMovieImporter

def main():
    parser = argparse.ArgumentParser(description="Canonical Movie Metadata Importer (REC-01)")
    parser.add_argument("--input", required=True, type=Path, help="Path to canonical movie bundle JSON")
    parser.add_argument("--schema", default=None, type=Path, help="Optional custom JSON schema path")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing database or catalog file")
    parser.add_argument("--output", default=None, type=Path, help="Output snapshot catalog path (JSON)")
    args = parser.parse_args()

    importer = CanonicalMovieImporter(schema_path=args.schema)
    print(f"[IMPORTER] Reading input file: {args.input}")
    print(f"[IMPORTER] Dry-run mode: {args.dry_run}")

    result = importer.import_bundle(
        file_path=args.input,
        dry_run=args.dry_run,
        output_catalog_path=args.output
    )

    if result["success"]:
        print("\n[IMPORTER] ✔ XÁC THỰC THÀNH CÔNG (VALIDATION PASS)")
        print(f"  - Schema Version: {result['schema_version']}")
        print(f"  - Tổng số bản ghi: {result['total_records']}")
        print(f"  - Danh sách Movie ID: {', '.join(result['movies_imported'])}")
        if not args.dry_run and args.output:
            print(f"  - Đã xuất dữ liệu ra: {args.output}")
        sys.exit(0)
    else:
        print("\n[IMPORTER] ❌ XÁC THỰC THẤT BẠI (VALIDATION FAILED)")
        print(f"  - Tổng số lỗi: {len(result['errors'])}")
        for i, err in enumerate(result["errors"], 1):
            print(f"  [{i}] ({err['type']}) tại '{err['field']}': {err['message']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
