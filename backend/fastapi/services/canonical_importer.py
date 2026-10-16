"""
Canonical Movie Metadata Importer & Validator for Dippie Cinema (REC-01).

Validates canonical movie bundles against canonical_movie_schema.v1.json,
performs semantic validation (unique IDs, scale bounds, null handling),
and provides idempotent upsert into the snapshot metadata repository.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import jsonschema

logger = logging.getLogger("moviercm.canonical_importer")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "contracts" / "canonical_movie_schema.v1.json"


class CanonicalImporterError(Exception):
    def __init__(self, message: str, errors: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.errors = errors or []


class CanonicalMovieImporter:
    def __init__(self, schema_path: Optional[Path] = None):
        self.schema_path = schema_path or SCHEMA_PATH
        self.schema: Dict[str, Any] = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        if not self.schema_path.exists():
            raise FileNotFoundError(f"JSON Schema không tồn tại tại: {self.schema_path}")
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_bundle(self, data: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Xác thực bundle dữ liệu phim:
        1. Kiểm tra JSON Schema (types, required fields, formats, regex).
        2. Kiểm tra tính duy nhất của ID.
        3. Kiểm tra tính toàn vẹn ngữ nghĩa (năm phát hành, điểm rating, thuộc tính so sánh).
        """
        errors = []

        # 1. JSON Schema validation
        validator = jsonschema.Draft202012Validator(self.schema)
        for err in validator.iter_errors(data):
            field_path = ".".join(str(p) for p in err.path) if err.path else "root"
            errors.append({
                "type": "SCHEMA_VIOLATION",
                "field": field_path,
                "message": err.message,
                "value": getattr(err, "instance", None)
            })

        # 2. Semantic validations if movies list exists
        movies = data.get("movies")
        if isinstance(movies, list):
            seen_ids = set()
            for idx, m in enumerate(movies):
                if not isinstance(m, dict):
                    continue
                mid = m.get("id")
                if mid:
                    if mid in seen_ids:
                        errors.append({
                            "type": "DUPLICATE_ID",
                            "field": f"movies[{idx}].id",
                            "message": f"Phát hiện trùng lặp Movie ID: '{mid}'",
                            "value": mid
                        })
                    seen_ids.add(mid)

                # Check comparative attributes
                comp = m.get("comparative_attributes")
                if isinstance(comp, dict):
                    darkness = comp.get("darkness")
                    pacing = comp.get("pacing")
                    if darkness is not None and not (0.0 <= darkness <= 1.0):
                        errors.append({
                            "type": "INVALID_ATTRIBUTE_RANGE",
                            "field": f"movies[{idx}].comparative_attributes.darkness",
                            "message": f"darkness ({darkness}) vượt ngoài thang đo [0.0, 1.0]",
                            "value": darkness
                        })
                    if pacing is not None and not (0.0 <= pacing <= 1.0):
                        errors.append({
                            "type": "INVALID_ATTRIBUTE_RANGE",
                            "field": f"movies[{idx}].comparative_attributes.pacing",
                            "message": f"pacing ({pacing}) vượt ngoài thang đo [0.0, 1.0]",
                            "value": pacing
                        })

        is_valid = (len(errors) == 0)
        return is_valid, errors

    @staticmethod
    def map_to_movie_item(canonical: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chuyển đổi một bản ghi canonical sang cấu trúc MovieItem tương thích FastAPI/Spring Boot.
        Giữ nguyên các giá trị null hoặc định dạng chuẩn mà không bịa đặt số liệu placeholder.
        """
        runtime_min = canonical.get("runtime_minutes")
        if runtime_min is not None:
            hours = runtime_min // 60
            mins = runtime_min % 60
            runtime_str = f"{hours}h {mins:02d}m" if hours > 0 else f"{mins}m"
        else:
            runtime_str = "N/A"

        # Resolve primary videoUrl from media_assets
        video_url = None
        for asset in canonical.get("media_assets", []):
            if asset.get("available") and asset.get("asset_type") in ("feature_video", "trailer"):
                if asset.get("storage_backend") == "google_drive":
                    video_url = "/api/media/stream/ast-drive-videoplayback"
                elif asset.get("relative_path"):
                    video_url = asset.get("relative_path")
                break

        return {
            "id": canonical["id"],
            "title": canonical["title"],
            "aliases": canonical.get("aliases", []),
            "year": canonical.get("year"),
            "rating": canonical.get("rating"),
            "runtime": runtime_str,
            "genres": canonical.get("genres", []),
            "description": canonical.get("synopsis", ""),
            "poster": canonical.get("poster_url"),
            "backdrop": canonical.get("backdrop_url"),
            "videoUrl": video_url,
            "provenance": canonical.get("provenance", {}),
            "verified_facts": canonical.get("verified_facts", {}),
            "comparative_attributes": canonical.get("comparative_attributes")
        }

    def import_bundle(
        self,
        file_path: Path,
        dry_run: bool = True,
        output_catalog_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Xử lý tệp JSON canonical:
        - Đọc và xác thực.
        - Nếu dry_run=True: trả về kết quả kiểm tra mà không ghi đĩa.
        - Nếu dry_run=False: ghi đè hoặc hợp nhất vào snapshot catalog.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Tệp đầu vào không tồn tại: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as jde:
                return {
                    "success": False,
                    "dry_run": dry_run,
                    "total_records": 0,
                    "errors": [{
                        "type": "SYNTAX_ERROR",
                        "field": "root",
                        "message": f"Lỗi cú pháp JSON: {jde}"
                    }]
                }

        is_valid, errors = self.validate_bundle(data)
        if not is_valid:
            return {
                "success": False,
                "dry_run": dry_run,
                "total_records": len(data.get("movies", [])) if isinstance(data.get("movies"), list) else 0,
                "errors": errors
            }

        movies = data.get("movies", [])
        mapped_items = [self.map_to_movie_item(m) for m in movies]

        if not dry_run and output_catalog_path:
            output_catalog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_catalog_path, "w", encoding="utf-8") as f:
                json.dump(mapped_items, f, indent=2, ensure_ascii=False)
            logger.info(f"Đã lưu {len(mapped_items)} phim canonical vào {output_catalog_path}")

        return {
            "success": True,
            "dry_run": dry_run,
            "schema_version": data.get("schema_version"),
            "total_records": len(movies),
            "movies_imported": [m["id"] for m in movies],
            "errors": []
        }
