import base64
import json
import os
import sys
import time
from pathlib import Path

import jwt
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend" / "fastapi") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from services.database import (
    DEFAULT_JWT_SECRET,
    Base,
    CatalogAttributeScale,
    CatalogCharacter,
    CatalogEpisode,
    CatalogGenre,
    CatalogMediaAsset,
    CatalogPackage,
    CatalogScene,
    CatalogSeason,
    CatalogSegment,
    CatalogSeries,
    CatalogSnapshot,
    CatalogSource,
    CatalogTextTrack,
    FavoriteItem,
    MediaAsset,
    Movie,
    MovieRating,
    User,
    WatchlistItem,
    WatchProgress,
    create_jwt_token,
    create_playback_grant_token,
    decode_jwt_token,
    export_eligible_catalog,
    validate_playback_grant_token,
)


EXPECTED_TABLES = {
    "users",
    "movies",
    "watchlist_items",
    "movie_ratings",
    "favorite_items",
    "media_assets",
    "watch_progress",
    "catalog_packages",
    "catalog_genres",
    "catalog_attribute_scales",
    "catalog_sources",
    "catalog_series",
    "catalog_seasons",
    "catalog_episodes",
    "catalog_segments",
    "catalog_characters",
    "catalog_media_assets",
    "catalog_text_tracks",
    "catalog_scenes",
    "catalog_snapshots",
}

CATALOG_V1_REQUIRED_KEYS = {
    "schema_version",
    "package",
    "genres",
    "attribute_scales",
    "sources",
    "series",
    "seasons",
    "episodes",
    "segments",
    "characters",
    "media_assets",
    "text_tracks",
    "scenes",
}


def test_cross_jwt_token_interoperability():
    """Verify JWT token interoperability between Spring Boot (io.jsonwebtoken) and FastAPI (PyJWT)."""
    # 1. Base64 decoded key check
    raw_secret = os.getenv("APP_JWT_SECRET", DEFAULT_JWT_SECRET)
    decoded_key = base64.b64decode(raw_secret)
    assert len(decoded_key) >= 32, "Secret key must be at least 256 bits for HS256"

    # 2. Token created by Python should have standard claims
    test_user = "dippie_cross_tester"
    py_token = create_jwt_token(test_user)
    assert py_token is not None

    # Decode and verify header & claims
    unverified_header = jwt.get_unverified_header(py_token)
    assert unverified_header.get("alg") == "HS256"

    claims = jwt.decode(py_token, decoded_key, algorithms=["HS256"])
    assert claims.get("sub") == test_user
    assert "iat" in claims
    assert "exp" in claims
    assert claims["exp"] > claims["iat"]

    # 3. Token structured like Java Spring Boot JwtUtils.generateToken(userDetails)
    now = int(time.time())
    java_simulated_payload = {
        "sub": "java_user_principal",
        "iat": now,
        "exp": now + 86400,
    }
    java_simulated_token = jwt.encode(java_simulated_payload, decoded_key, algorithm="HS256")

    # FastAPI decode_jwt_token should recognize Java-generated token
    recovered_user = decode_jwt_token(java_simulated_token)
    assert recovered_user == "java_user_principal"

    # 4. Playback Grant verification (Java JwtUtils.generatePlaybackGrant)
    grant_payload = {
        "sub": "streamer_01",
        "assetId": "ast-drive-videoplayback",
        "role": "ROLE_USER",
        "type": "playback_grant",
        "purpose": "playback",
        "iat": now,
        "exp": now + 300,
    }
    grant_token = jwt.encode(grant_payload, decoded_key, algorithm="HS256")
    grant_claims = jwt.decode(grant_token, decoded_key, algorithms=["HS256"])
    assert grant_claims["assetId"] == "ast-drive-videoplayback"
    assert grant_claims["type"] == "playback_grant"
    assert decode_jwt_token(grant_token) is None, "Playback grant must be rejected as general auth token"
    assert validate_playback_grant_token(grant_token, "ast-drive-videoplayback") == "ROLE_USER"

    py_grant = create_playback_grant_token("ast-drive-videoplayback", "streamer_01", "ROLE_ADMIN", 300)
    assert decode_jwt_token(py_grant) is None
    assert validate_playback_grant_token(py_grant, "ast-drive-videoplayback") == "ROLE_ADMIN"
    assert validate_playback_grant_token(py_grant, "other-asset") is None


def test_cross_database_schema_and_types():
    """Verify that Python SQLAlchemy models cover all 20 MySQL 8.0 tables used by Spring Boot."""
    registered_tables = set(Base.metadata.tables.keys())
    missing_tables = EXPECTED_TABLES - registered_tables
    assert not missing_tables, f"SQLAlchemy models missing tables: {missing_tables}"

    # Verify column consistency on core tables
    users_cols = {c.name for c in Base.metadata.tables["users"].columns}
    assert {"id", "username", "email", "password", "full_name", "role", "created_at"}.issubset(users_cols)

    movies_cols = {c.name for c in Base.metadata.tables["movies"].columns}
    assert {"id", "title", "release_year", "rating", "runtime", "genres", "description", "poster", "backdrop", "video_url"}.issubset(movies_cols)

    watch_progress_cols = {c.name for c in Base.metadata.tables["watch_progress"].columns}
    assert {"id", "user_id", "episode_id", "asset_id", "position_ms", "opt_lock_version", "updated_at"}.issubset(watch_progress_cols)

    media_assets_cols = {c.name for c in Base.metadata.tables["media_assets"].columns}
    assert {"id", "movie_id", "kind", "storage_provider", "relative_path", "version", "byte_length"}.issubset(media_assets_cols)

    catalog_episodes_cols = {c.name for c in Base.metadata.tables["catalog_episodes"].columns}
    assert {"id", "series_id", "season_id", "number", "title", "duration_ms"}.issubset(catalog_episodes_cols)


def test_cross_catalog_v1_format_and_fixtures():
    """Verify catalog v1 schema conforms to rehearsal_catalog fixture and export contract."""
    fixture_path = ROOT / "docs" / "fixtures" / "rehearsal_catalog.json"
    assert fixture_path.exists(), "rehearsal_catalog.json fixture must exist"

    with open(fixture_path, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)

    assert catalog_data.get("schema_version") == "dippie.catalog.v1"
    top_keys = set(catalog_data.keys())
    assert CATALOG_V1_REQUIRED_KEYS.issubset(top_keys), f"Missing keys in fixture: {CATALOG_V1_REQUIRED_KEYS - top_keys}"

    # Package metadata validation
    pkg = catalog_data["package"]
    assert {"id", "revision", "created_at", "default_language", "import_mode", "reference_scope", "description"}.issubset(set(pkg.keys()))

    # Episodes validation
    if catalog_data["episodes"]:
        ep = catalog_data["episodes"][0]
        assert {"id", "series_id", "title"}.issubset(set(ep.keys()))

    # Media assets validation
    if catalog_data["media_assets"]:
        asset = catalog_data["media_assets"][0]
        assert {"id", "content_type", "storage", "access_policy", "duration_ms"}.issubset(set(asset.keys()))

    # Scenes validation
    if catalog_data["scenes"]:
        sc = catalog_data["scenes"][0]
        assert {"id", "episode_id", "start_ms", "end_ms"}.issubset(set(sc.keys()))
