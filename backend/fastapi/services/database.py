import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import bcrypt
import jwt
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

DEFAULT_JWT_SECRET = "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970"


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), nullable=False, default="ROLE_USER")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Movie(Base):
    __tablename__ = "movies"
    id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    release_year = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)
    runtime = Column(String(20))
    genres = Column(Text)
    description = Column(Text)
    poster = Column(String(500))
    backdrop = Column(String(500))
    video_url = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_response(self):
        genre_list = [g.strip() for g in (self.genres or "").split(",") if g.strip()]
        return {
            "id": self.id,
            "title": self.title,
            "year": self.release_year,
            "rating": self.rating,
            "runtime": self.runtime,
            "genres": genre_list,
            "description": self.description,
            "poster": self.poster,
            "backdrop": self.backdrop,
            "videoUrl": self.video_url,
        }


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_movie_watchlist"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(String(100), nullable=False)
    movie_title = Column(String(255), nullable=False)
    poster_url = Column(String(500))
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "movieId": self.movie_id,
            "movieTitle": self.movie_title,
            "posterUrl": self.poster_url,
            "addedAt": self.added_at.isoformat() if self.added_at else None,
        }


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_movie_rating"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "movieId": self.movie_id,
            "rating": self.rating,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class FavoriteItem(Base):
    __tablename__ = "favorite_items"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_movie_favorite"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(String(100), nullable=False)
    movie_title = Column(String(255), nullable=False)
    poster_url = Column(String(500))
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "movieId": self.movie_id,
            "movieTitle": self.movie_title,
            "posterUrl": self.poster_url,
            "addedAt": self.added_at.isoformat() if self.added_at else None,
        }


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (UniqueConstraint("movie_id", "kind", "version", name="uq_movie_kind_version"),)
    id = Column(String(64), primary_key=True)
    movie_id = Column(String(100), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), nullable=False)
    storage_provider = Column(String(30), nullable=False, default="local")
    storage_key = Column(String(100))
    relative_path = Column(String(500), nullable=False)
    version = Column(String(50), nullable=False, default="v1")
    mime_type = Column(String(100), nullable=False, default="video/mp4")
    byte_length = Column(BigInteger, nullable=False, default=0)
    duration_seconds = Column(Float)
    is_public = Column(Boolean, nullable=False, default=True)
    is_available = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dto(self):
        return {
            "assetId": self.id,
            "kind": self.kind,
            "streamUrl": f"/api/media/stream/{self.id}",
            "mimeType": self.mime_type,
            "byteLength": self.byte_length,
            "durationSeconds": self.duration_seconds,
            "isPublic": bool(self.is_public),
            "version": self.version,
        }


class CatalogPackage(Base):
    __tablename__ = "catalog_packages"
    id = Column(String(100), primary_key=True)
    version = Column(String(50), nullable=False)
    revision = Column(Integer, nullable=False)
    default_language = Column(String(20), nullable=False)
    import_mode = Column(String(50), nullable=False)
    reference_scope = Column(String(50), nullable=False)
    name = Column(String(200))
    description = Column(Text)
    content_hash = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    error_message = Column(Text)
    opt_lock_version = Column(BigInteger, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "revision": self.revision,
            "defaultLanguage": self.default_language,
            "importMode": self.import_mode,
            "referenceScope": self.reference_scope,
            "description": self.description,
            "contentHash": self.content_hash,
            "status": self.status,
            "errorMessage": self.error_message,
            "optLockVersion": self.opt_lock_version,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "importedAt": self.imported_at.isoformat() if self.imported_at else None,
        }


class CatalogGenre(Base):
    __tablename__ = "catalog_genres"
    id = Column(String(100), primary_key=True)
    labels_json = Column(Text, nullable=False)
    aliases_json = Column(Text)
    description = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogAttributeScale(Base):
    __tablename__ = "catalog_attribute_scales"
    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    definition = Column(Text)
    minimum = Column(Float, nullable=False)
    maximum = Column(Float, nullable=False)
    levels_json = Column(Text, nullable=False)
    version = Column(String(50))
    source_ids_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    id = Column(String(100), primary_key=True)
    kind = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    uri = Column(String(1000))
    note = Column(Text)
    retrieved_at = Column(String(100))
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogSeries(Base):
    __tablename__ = "catalog_series"
    id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    original_title = Column(String(255))
    aliases_json = Column(Text)
    synopsis = Column(Text)
    translations_json = Column(Text)
    genre_ids_json = Column(Text)
    keywords_json = Column(Text)
    themes_json = Column(Text)
    origin_countries_json = Column(Text)
    original_languages_json = Column(Text)
    release_year_start = Column(Integer)
    release_year_end = Column(Integer)
    release_status = Column(String(50))
    character_ids_json = Column(Text)
    artworks_json = Column(Text)
    attributes_json = Column(Text)
    ratings_json = Column(Text)
    advisories_json = Column(Text)
    credits_json = Column(Text)
    external_ids_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "originalTitle": self.original_title,
            "aliasesJson": self.aliases_json,
            "synopsis": self.synopsis,
            "translationsJson": self.translations_json,
            "genreIdsJson": self.genre_ids_json,
            "keywordsJson": self.keywords_json,
            "themesJson": self.themes_json,
            "originCountriesJson": self.origin_countries_json,
            "originalLanguagesJson": self.original_languages_json,
            "releaseYearStart": self.release_year_start,
            "releaseYearEnd": self.release_year_end,
            "releaseStatus": self.release_status,
            "characterIdsJson": self.character_ids_json,
            "artworksJson": self.artworks_json,
            "attributesJson": self.attributes_json,
            "ratingsJson": self.ratings_json,
            "advisoriesJson": self.advisories_json,
            "creditsJson": self.credits_json,
            "externalIdsJson": self.external_ids_json,
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogSeason(Base):
    __tablename__ = "catalog_seasons"
    id = Column(String(100), primary_key=True)
    series_id = Column(String(100), ForeignKey("catalog_series.id", ondelete="CASCADE"), nullable=False)
    number = Column(Integer)
    title = Column(String(255), nullable=False)
    synopsis = Column(Text)
    kind = Column(String(50))
    translations_json = Column(Text)
    release_date = Column(String(50))
    artworks_json = Column(Text)
    attributes_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "seriesId": self.series_id,
            "number": self.number,
            "title": self.title,
            "synopsis": self.synopsis,
            "kind": self.kind,
            "translationsJson": self.translations_json,
            "releaseDate": self.release_date,
            "artworksJson": self.artworks_json,
            "attributesJson": self.attributes_json,
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogEpisode(Base):
    __tablename__ = "catalog_episodes"
    id = Column(String(100), primary_key=True)
    series_id = Column(String(100), ForeignKey("catalog_series.id", ondelete="CASCADE"), nullable=False)
    season_id = Column(String(100))
    number = Column(Integer)
    title = Column(String(255), nullable=False)
    aliases_json = Column(Text)
    synopsis = Column(Text)
    translations_json = Column(Text)
    kind = Column(String(50), nullable=False)
    release_date = Column(String(50))
    duration_ms = Column(BigInteger)
    genre_ids_json = Column(Text)
    primary_language = Column(String(50))
    orders_json = Column(Text)
    links_json = Column(Text)
    character_ids_json = Column(Text)
    plot_facts_json = Column(Text)
    keywords_json = Column(Text)
    themes_json = Column(Text)
    attributes_json = Column(Text)
    ratings_json = Column(Text)
    artworks_json = Column(Text)
    credits_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "seriesId": self.series_id,
            "seasonId": self.season_id,
            "number": self.number,
            "title": self.title,
            "aliasesJson": self.aliases_json,
            "synopsis": self.synopsis,
            "translationsJson": self.translations_json,
            "kind": self.kind,
            "releaseDate": self.release_date,
            "durationMs": self.duration_ms,
            "genreIdsJson": self.genre_ids_json,
            "primaryLanguage": self.primary_language,
            "ordersJson": self.orders_json,
            "linksJson": self.links_json,
            "characterIdsJson": self.character_ids_json,
            "plotFactsJson": self.plot_facts_json,
            "keywordsJson": self.keywords_json,
            "themesJson": self.themes_json,
            "attributesJson": self.attributes_json,
            "ratingsJson": self.ratings_json,
            "artworksJson": self.artworks_json,
            "creditsJson": self.credits_json,
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogSegment(Base):
    __tablename__ = "catalog_segments"
    id = Column(String(100), primary_key=True)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    aliases_json = Column(Text)
    synopsis = Column(Text)
    translations_json = Column(Text)
    primary_language = Column(String(50))
    character_ids_json = Column(Text)
    plot_facts_json = Column(Text)
    keywords_json = Column(Text)
    themes_json = Column(Text)
    attributes_json = Column(Text)
    episode_start_ms = Column(BigInteger)
    episode_end_ms = Column(BigInteger)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "episodeId": self.episode_id,
            "position": self.position,
            "title": self.title,
            "aliasesJson": self.aliases_json,
            "synopsis": self.synopsis,
            "translationsJson": self.translations_json,
            "primaryLanguage": self.primary_language,
            "characterIdsJson": self.character_ids_json,
            "plotFactsJson": self.plot_facts_json,
            "keywordsJson": self.keywords_json,
            "themesJson": self.themes_json,
            "attributesJson": self.attributes_json,
            "episodeStartMs": self.episode_start_ms,
            "episodeEndMs": self.episode_end_ms,
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogCharacter(Base):
    __tablename__ = "catalog_characters"
    id = Column(String(100), primary_key=True)
    series_ids_json = Column(Text)
    name = Column(String(255), nullable=False)
    aliases_json = Column(Text)
    description = Column(Text)
    role = Column(String(50))
    traits_json = Column(Text)
    relationships_json = Column(Text)
    voice_credits_json = Column(Text)
    artworks_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogMediaAsset(Base):
    __tablename__ = "catalog_media_assets"
    id = Column(String(100), primary_key=True)
    content_type = Column(String(50), nullable=False, default="video")
    role = Column(String(50), nullable=False, default="feature")
    edition_label = Column(String(100))
    spoken_languages_json = Column(Text)
    embedded_subtitle_languages_json = Column(Text)
    storage_provider = Column(String(50), nullable=False)
    storage_key = Column(String(100), nullable=False)
    relative_path = Column(String(500), nullable=False)
    drive_file_id = Column(String(255))
    drive_folder_id = Column(String(255))
    size_bytes = Column(BigInteger)
    sha256 = Column(String(100))
    duration_ms = Column(BigInteger)
    technical_json = Column(Text)
    coverage_json = Column(Text)
    related_asset_id = Column(String(100))
    access_policy = Column(String(50), nullable=False, default="public")
    enabled = Column(Boolean, nullable=False, default=True)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "contentType": self.content_type,
            "role": self.role,
            "editionLabel": self.edition_label,
            "spokenLanguagesJson": self.spoken_languages_json,
            "embeddedSubtitleLanguagesJson": self.embedded_subtitle_languages_json,
            "storageProvider": self.storage_provider,
            "storageKey": self.storage_key,
            "relativePath": self.relative_path,
            "driveFileId": self.drive_file_id,
            "driveFolderId": self.drive_folder_id,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "durationMs": self.duration_ms,
            "technicalJson": self.technical_json,
            "coverageJson": self.coverage_json,
            "relatedAssetId": self.related_asset_id,
            "accessPolicy": self.access_policy,
            "enabled": bool(self.enabled),
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogTextTrack(Base):
    __tablename__ = "catalog_text_tracks"
    id = Column(String(100), primary_key=True)
    media_asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(50), nullable=False)
    kind = Column(String(50), nullable=False)
    label = Column(String(255))
    format = Column(String(50), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    external_file_json = Column(Text)
    cues_json = Column(Text)
    provenance_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogScene(Base):
    __tablename__ = "catalog_scenes"
    id = Column(String(100), primary_key=True)
    media_asset_id = Column(String(100))
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String(100))
    start_ms = Column(BigInteger, nullable=False)
    end_ms = Column(BigInteger, nullable=False)
    title = Column(String(255))
    summary = Column(Text)
    visual_description = Column(Text)
    visual_tags_json = Column(Text)
    sound_events_json = Column(Text)
    transcript_cue_ids_json = Column(Text)
    character_ids_json = Column(Text)
    keywords_json = Column(Text)
    themes_json = Column(Text)
    attributes_json = Column(Text)
    provenance_json = Column(Text)
    record_json = Column(Text)
    raw_json = Column(Text)
    revision = Column(Integer, nullable=False, default=1)
    opt_lock_version = Column(BigInteger, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "mediaAssetId": self.media_asset_id,
            "episodeId": self.episode_id,
            "segmentId": self.segment_id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "title": self.title,
            "summary": self.summary,
            "visualDescription": self.visual_description,
            "visualTagsJson": self.visual_tags_json,
            "soundEventsJson": self.sound_events_json,
            "transcriptCueIdsJson": self.transcript_cue_ids_json,
            "characterIdsJson": self.character_ids_json,
            "keywordsJson": self.keywords_json,
            "themesJson": self.themes_json,
            "attributesJson": self.attributes_json,
            "provenanceJson": self.provenance_json,
            "recordJson": self.record_json,
            "rawJson": self.raw_json,
            "revision": self.revision,
            "optLockVersion": self.opt_lock_version,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"
    id = Column(String(100), primary_key=True)
    snapshot_version = Column(BigInteger, nullable=False, unique=True)
    content_hash = Column(String(100), nullable=False)
    total_items = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "snapshotVersion": self.snapshot_version,
            "contentHash": self.content_hash,
            "totalItems": self.total_items,
            "status": self.status,
            "retryCount": self.retry_count,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class WatchProgress(Base):
    __tablename__ = "watch_progress"
    __table_args__ = (UniqueConstraint("user_id", "episode_id", name="uq_watch_progress_user_episode"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String(100), nullable=False)
    position_ms = Column(BigInteger, nullable=False)
    opt_lock_version = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _jwt_key() -> bytes:
    secret = os.getenv("APP_JWT_SECRET", DEFAULT_JWT_SECRET)
    try:
        return base64.b64decode(secret)
    except Exception:
        return secret.encode("utf-8")


def create_jwt_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    exp_ms = int(os.getenv("APP_JWT_EXPIRATION_MS", "86400000"))
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(milliseconds=exp_ms)).timestamp()),
    }
    return jwt.encode(payload, _jwt_key(), algorithm="HS256")


def decode_jwt_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, _jwt_key(), algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


def resolve_database_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    db_name = os.getenv("MYSQL_DB", "movie_rcm_db")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"


SEED_MOVIES = [
    ("drive-videoplayback", "Shin Cậu Bé Bút Chì: Chuyến phiêu lưu kỳ thú", 2026, 8.8, "7m 25s", "Animation,Comedy,Adventure,Family", "Tập phim hoạt hình Shin Cậu Bé Bút Chì được phát và giải mã trực tiếp từ Google Drive storage.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85", "/api/media/stream/ast-drive-videoplayback"),
    ("the-last-orbit", "The Last Orbit", 2026, 8.7, "2h 14m", "Animation,Sci-Fi,Drama", "A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85", "/videos/the-last-orbit.mp4"),
    ("spirited-away", "Spirited Away", 2001, 8.6, "2h 05m", "Animation,Adventure,Family,Fantasy", "A young girl wanders into a magical bathhouse ruled by spirits and witches, where she must find the courage to free her parents.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1800&q=85", "/videos/the-last-orbit.mp4"),
    ("your-name", "Your Name", 2016, 8.4, "1h 46m", "Animation,Romance,Drama,Fantasy", "Two teenagers share a profound, magical connection upon discovering they are swapping bodies across time and space.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85", "/videos/afterlight.mp4"),
    ("spider-verse", "Spider-Man: Into the Spider-Verse", 2018, 8.4, "1h 57m", "Animation,Action,Adventure,Sci-Fi", "Teen Miles Morales becomes the Spider-Man of his universe and crosses paths with five counterparts from other dimensions.", "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=1800&q=85", "/videos/glass-horizon.mp4"),
    ("isle-of-dogs", "Isle of Dogs", 2018, 7.8, "1h 41m", "Animation,Adventure,Comedy,Drama", "Set in dystopian Japan, a young boy journeys to Trash Island in a stop-motion quest to rescue his exiled dog Spots.", "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1800&q=85", "/videos/deep-blue.mp4"),
    ("coraline", "Coraline", 2009, 7.7, "1h 40m", "Animation,Drama,Family,Fantasy,Horror", "An adventurous 11-year-old girl finds another world that is a strangely idealized version of her frustrating home, but it has sinister secrets.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=1800&q=85", "/videos/nocturne.mp4"),
    ("fantasia-1940", "Fantasia", 1940, 7.7, "2h 05m", "Animation,Family,Fantasy,Musical", "A timeless collection of animated interpretations of great works of Western classical music.", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1800&q=85", "/videos/quiet-places.mp4"),
    ("afterlight", "Afterlight", 2025, 8.3, "1h 58m", "Animation,Drama,Mystery", "In a city where night never ends, a photographer follows one impossible beam of sunlight.", "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85", "/videos/afterlight.mp4"),
    ("glass-horizon", "Glass Horizon", 2026, 8.1, "2h 06m", "Animation,Thriller,Sci-Fi", "A brilliant architect is asked to design a city that no one is meant to leave.", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85", "/videos/glass-horizon.mp4"),
    ("deep-blue", "Deep Blue", 2024, 7.9, "1h 46m", "Animation,Adventure,Drama", "Two estranged sisters cross an unmapped ocean in search of their father.", "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85", "/videos/deep-blue.mp4"),
    ("quiet-places", "Quiet Places", 2025, 8.5, "2h 01m", "Animation,Romance,Drama", "A composer returns to the town she fled and finds an old song waiting for her.", "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85", "/videos/quiet-places.mp4"),
    ("nocturne", "Nocturne", 2024, 7.8, "1h 52m", "Animation,Crime,Thriller", "A detective investigates a string of elegant crimes committed at midnight.", "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85", "/videos/nocturne.mp4"),
]


class DatabaseManager:
    def __init__(self, database_url: str | None = None, seed: bool = True):
        self.database_url = resolve_database_url(database_url)
        self.engine = None
        self.SessionLocal = None
        self._seed = seed
        self._initialized = False

    def ensure_initialized(self):
        if self._initialized:
            return
        url = self.database_url
        try:
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
            self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
            Base.metadata.create_all(self.engine)
        except Exception:
            fallback_path = Path(os.getenv("PYTHON_MAIN_SQLITE_FALLBACK", "data/python_main.db"))
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{fallback_path}"
            self.database_url = url
            self.engine = create_engine(url, connect_args={"check_same_thread": False})
            Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self._initialized = True
        if self._seed:
            self.seed_defaults()

    def session(self):
        self.ensure_initialized()
        return self.SessionLocal()

    def seed_defaults(self):
        with self.session() as db:
            for mid, title, year, rating, runtime, genres, desc, poster, backdrop, video_url in SEED_MOVIES:
                if not db.get(Movie, mid):
                    db.add(Movie(
                        id=mid, title=title, release_year=year, rating=rating,
                        runtime=runtime, genres=genres, description=desc,
                        poster=poster, backdrop=backdrop, video_url=video_url,
                    ))
            if not db.query(User).filter(User.username == "admin").first():
                db.add(User(
                    username="admin", email="admin@dippie.com",
                    full_name="System Administrator",
                    password=hash_password("password123"), role="ROLE_ADMIN",
                ))
            if not db.query(User).filter(User.username == "user").first():
                db.add(User(
                    username="user", email="user@dippie.com",
                    full_name="Standard User",
                    password=hash_password("password123"), role="ROLE_USER",
                ))
            db.flush()
            default_assets = [
                ("ast-drive-videoplayback", "drive-videoplayback", "feature", "drive", "videoplayback.mp4", "v1", "video/mp4", 29209556, 445.8),
                ("ast-orbit-feat", "the-last-orbit", "feature", "local", "synthetic/feature_test.mp4", "v1", "video/mp4", 137961, 10.0),
                ("ast-orbit-trl", "the-last-orbit", "trailer", "local", "synthetic/trailer_test.mp4", "v1", "video/mp4", 45095, 3.0),
                ("ast-afterlight-trl", "afterlight", "trailer", "local", "synthetic/trailer_test.mp4", "v1", "video/mp4", 45095, 3.0),
            ]
            for aid, movie_id, kind, provider, rel_path, ver, mime, size_b, dur_s in default_assets:
                if not db.get(MediaAsset, aid):
                    db.add(MediaAsset(
                        id=aid, movie_id=movie_id, kind=kind, storage_provider=provider,
                        relative_path=rel_path, version=ver, mime_type=mime,
                        byte_length=size_b, duration_seconds=dur_s, is_public=True, is_available=True,
                    ))
            db.commit()


def is_published(record_json: str | None) -> bool:
    if not record_json:
        return False
    try:
        return str(json.loads(record_json).get("status", "")).lower() == "ready"
    except Exception:
        return False


def compute_sha256(data) -> str:
    if isinstance(data, (dict, list)):
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    else:
        raw = str(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def import_catalog_package(db, data: dict) -> dict:
    pkg = data.get("package") or {}
    pkg_id = pkg.get("id") or "pkg_default"
    revision = int(pkg.get("revision") or 1)
    version = str(pkg.get("version") or "1.0.0")
    default_lang = str(pkg.get("default_language") or "vi")
    import_mode = str(pkg.get("import_mode") or "upsert")
    ref_scope = str(pkg.get("reference_scope") or "self_contained")
    content_hash = compute_sha256(data)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    existing_pkg = db.get(CatalogPackage, pkg_id)
    if existing_pkg:
        existing_pkg.version = version
        existing_pkg.revision = revision
        existing_pkg.default_language = default_lang
        existing_pkg.import_mode = import_mode
        existing_pkg.reference_scope = ref_scope
        existing_pkg.content_hash = content_hash
        existing_pkg.status = "COMMITTED"
        existing_pkg.imported_at = now
    else:
        db.add(CatalogPackage(
            id=pkg_id, version=version, revision=revision, default_language=default_lang,
            import_mode=import_mode, reference_scope=ref_scope, description=pkg.get("description"),
            content_hash=content_hash, status="COMMITTED", created_at=now, imported_at=now,
        ))

    counts = {}

    genres = data.get("genres") or []
    for g in genres:
        gid = g["id"]
        entity = db.get(CatalogGenre, gid) or CatalogGenre(id=gid)
        entity.labels_json = json.dumps(g.get("labels") or {"vi": g.get("name", gid)}, ensure_ascii=False)
        entity.aliases_json = json.dumps(g.get("aliases"), ensure_ascii=False) if g.get("aliases") is not None else None
        entity.description = g.get("description")
        entity.record_json = json.dumps(g.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(g, ensure_ascii=False)
        entity.revision = int((g.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["genres"] = len(genres)

    scales = data.get("attribute_scales") or []
    for sc in scales:
        sid = sc["id"]
        entity = db.get(CatalogAttributeScale, sid) or CatalogAttributeScale(id=sid)
        entity.name = sc.get("name", sid)
        entity.definition = sc.get("definition")
        entity.minimum = float(sc.get("minimum", 0.0))
        entity.maximum = float(sc.get("maximum", 1.0))
        entity.levels_json = json.dumps(sc.get("levels") or [], ensure_ascii=False)
        entity.version = sc.get("version", "1.0.0")
        entity.source_ids_json = json.dumps(sc.get("source_ids"), ensure_ascii=False) if sc.get("source_ids") is not None else None
        entity.record_json = json.dumps(sc.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(sc, ensure_ascii=False)
        entity.revision = int((sc.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["attributeScales"] = len(scales)

    sources = data.get("sources") or []
    for src in sources:
        sid = src["id"]
        entity = db.get(CatalogSource, sid) or CatalogSource(id=sid)
        entity.kind = src.get("kind") or src.get("source_type") or "web"
        entity.title = src.get("title") or src.get("name") or sid
        entity.uri = src.get("url") or src.get("uri")
        entity.note = src.get("note") or src.get("notes")
        entity.retrieved_at = src.get("retrieved_at")
        entity.record_json = json.dumps(src.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(src, ensure_ascii=False)
        entity.revision = int((src.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["sources"] = len(sources)

    series_list = data.get("series") or []
    for s in series_list:
        sid = s["id"]
        entity = db.get(CatalogSeries, sid) or CatalogSeries(id=sid)
        entity.title = s.get("title", sid)
        entity.original_title = s.get("original_title")
        entity.aliases_json = json.dumps(s.get("aliases"), ensure_ascii=False) if s.get("aliases") is not None else None
        entity.synopsis = s.get("synopsis")
        entity.translations_json = json.dumps(s.get("translations"), ensure_ascii=False) if s.get("translations") is not None else None
        entity.genre_ids_json = json.dumps(s.get("genre_ids"), ensure_ascii=False) if s.get("genre_ids") is not None else None
        entity.keywords_json = json.dumps(s.get("keywords") or s.get("tags"), ensure_ascii=False) if (s.get("keywords") or s.get("tags")) is not None else None
        entity.themes_json = json.dumps(s.get("themes"), ensure_ascii=False) if s.get("themes") is not None else None
        entity.origin_countries_json = json.dumps(s.get("origin_countries"), ensure_ascii=False) if s.get("origin_countries") is not None else None
        entity.original_languages_json = json.dumps(s.get("original_languages"), ensure_ascii=False) if s.get("original_languages") is not None else None
        entity.release_year_start = s.get("release_year_start") or s.get("release_year")
        entity.release_year_end = s.get("release_year_end")
        entity.release_status = s.get("release_status") or s.get("status")
        entity.character_ids_json = json.dumps(s.get("character_ids"), ensure_ascii=False) if s.get("character_ids") is not None else None
        entity.artworks_json = json.dumps(s.get("artwork") or s.get("artworks"), ensure_ascii=False) if (s.get("artwork") or s.get("artworks")) is not None else None
        entity.attributes_json = json.dumps(s.get("attributes"), ensure_ascii=False) if s.get("attributes") is not None else None
        entity.ratings_json = json.dumps(s.get("ratings"), ensure_ascii=False) if s.get("ratings") is not None else None
        entity.advisories_json = json.dumps(s.get("content_advisory"), ensure_ascii=False) if s.get("content_advisory") is not None else None
        entity.external_ids_json = json.dumps(s.get("external_ids"), ensure_ascii=False) if s.get("external_ids") is not None else None
        entity.record_json = json.dumps(s.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(s, ensure_ascii=False)
        entity.revision = int((s.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
        if not db.get(Movie, sid):
            db.add(Movie(
                id=sid, title=entity.title, release_year=entity.release_year_start or 2026,
                rating=0.0, runtime="Series", genres="Animation", description=entity.synopsis or "",
            ))
            db.flush()
    counts["series"] = len(series_list)

    seasons = data.get("seasons") or []
    for sea in seasons:
        sea_id = sea["id"]
        entity = db.get(CatalogSeason, sea_id) or CatalogSeason(id=sea_id)
        entity.series_id = sea["series_id"]
        entity.number = sea.get("number") if sea.get("number") is not None else sea.get("season_number")
        entity.title = sea.get("title", sea_id)
        entity.synopsis = sea.get("synopsis") or sea.get("description")
        entity.kind = sea.get("kind", "standard")
        entity.release_date = str(sea.get("release_date") or sea.get("release_year") or "") or None
        entity.artworks_json = json.dumps(sea.get("artwork") or sea.get("artworks"), ensure_ascii=False) if (sea.get("artwork") or sea.get("artworks")) is not None else None
        entity.record_json = json.dumps(sea.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(sea, ensure_ascii=False)
        entity.revision = int((sea.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["seasons"] = len(seasons)

    episodes = data.get("episodes") or []
    for ep in episodes:
        ep_id = ep["id"]
        entity = db.get(CatalogEpisode, ep_id) or CatalogEpisode(id=ep_id)
        entity.series_id = ep["series_id"]
        entity.season_id = ep.get("season_id")
        entity.number = ep.get("number") if ep.get("number") is not None else ep.get("episode_number")
        entity.title = ep.get("title", ep_id)
        entity.aliases_json = json.dumps(ep.get("aliases"), ensure_ascii=False) if ep.get("aliases") is not None else None
        entity.synopsis = ep.get("synopsis")
        entity.translations_json = json.dumps(ep.get("translations"), ensure_ascii=False) if ep.get("translations") is not None else None
        entity.kind = ep.get("kind") or ep.get("episode_type") or "standard"
        entity.release_date = ep.get("release_date") or ep.get("air_date")
        entity.duration_ms = ep.get("duration_ms")
        entity.genre_ids_json = json.dumps(ep.get("genre_ids"), ensure_ascii=False) if ep.get("genre_ids") is not None else None
        entity.primary_language = ep.get("primary_language")
        entity.character_ids_json = json.dumps(ep.get("character_ids"), ensure_ascii=False) if ep.get("character_ids") is not None else None
        entity.plot_facts_json = json.dumps(ep.get("plot_facts"), ensure_ascii=False) if ep.get("plot_facts") is not None else None
        entity.keywords_json = json.dumps(ep.get("keywords") or ep.get("tags"), ensure_ascii=False) if (ep.get("keywords") or ep.get("tags")) is not None else None
        entity.themes_json = json.dumps(ep.get("themes"), ensure_ascii=False) if ep.get("themes") is not None else None
        entity.attributes_json = json.dumps(ep.get("attributes"), ensure_ascii=False) if ep.get("attributes") is not None else None
        entity.artworks_json = json.dumps(ep.get("artwork") or ep.get("artworks"), ensure_ascii=False) if (ep.get("artwork") or ep.get("artworks")) is not None else None
        entity.record_json = json.dumps(ep.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(ep, ensure_ascii=False)
        entity.revision = int((ep.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
        if not db.get(Movie, ep_id):
            mins = int((entity.duration_ms or 1200000) / 60000)
            db.add(Movie(
                id=ep_id, title=entity.title, release_year=2026,
                rating=0.0, runtime=f"{mins}m", genres="Animation", description=entity.synopsis or "",
            ))
            db.flush()
    counts["episodes"] = len(episodes)

    segments = data.get("segments") or []
    for seg in segments:
        seg_id = seg["id"]
        entity = db.get(CatalogSegment, seg_id) or CatalogSegment(id=seg_id)
        entity.episode_id = seg["episode_id"]
        entity.position = int(seg.get("position") or 1)
        entity.title = seg.get("title", seg_id)
        entity.synopsis = seg.get("synopsis")
        entity.episode_start_ms = seg.get("episode_start_ms")
        entity.episode_end_ms = seg.get("episode_end_ms")
        entity.character_ids_json = json.dumps(seg.get("character_ids"), ensure_ascii=False) if seg.get("character_ids") is not None else None
        entity.keywords_json = json.dumps(seg.get("keywords") or seg.get("tags"), ensure_ascii=False) if (seg.get("keywords") or seg.get("tags")) is not None else None
        entity.attributes_json = json.dumps(seg.get("attributes"), ensure_ascii=False) if seg.get("attributes") is not None else None
        entity.plot_facts_json = json.dumps(seg.get("plot_facts"), ensure_ascii=False) if seg.get("plot_facts") is not None else None
        entity.record_json = json.dumps(seg.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(seg, ensure_ascii=False)
        entity.revision = int((seg.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["segments"] = len(segments)

    characters = data.get("characters") or []
    for c in characters:
        cid = c["id"]
        entity = db.get(CatalogCharacter, cid) or CatalogCharacter(id=cid)
        entity.name = c.get("name", cid)
        entity.description = c.get("description")
        entity.series_ids_json = json.dumps(c.get("series_ids"), ensure_ascii=False) if c.get("series_ids") is not None else None
        entity.role = c.get("role")
        entity.aliases_json = json.dumps(c.get("aliases"), ensure_ascii=False) if c.get("aliases") is not None else None
        entity.traits_json = json.dumps(c.get("traits"), ensure_ascii=False) if c.get("traits") is not None else None
        entity.relationships_json = json.dumps(c.get("relationships"), ensure_ascii=False) if c.get("relationships") is not None else None
        entity.record_json = json.dumps(c.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(c, ensure_ascii=False)
        entity.revision = int((c.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["characters"] = len(characters)

    media_assets = data.get("media_assets") or []
    for ma in media_assets:
        mid = ma["id"]
        storage = ma.get("storage") or {}
        p_str = str(storage.get("provider") or "local").lower()
        provider = "drive" if p_str in ("drive", "google_drive") else "local"
        storage_key = storage.get("storage_key") or storage.get("root_storage_key") or "local_main"
        rel_path = storage.get("relative_path") or f"media/{mid}.mp4"
        size_bytes = ma.get("size_bytes") if ma.get("size_bytes") is not None else (ma.get("byte_length") or 0)
        entity = db.get(CatalogMediaAsset, mid) or CatalogMediaAsset(id=mid)
        entity.content_type = "video"
        entity.role = ma.get("role", "feature")
        entity.edition_label = ma.get("edition_label") or ma.get("edition")
        entity.storage_provider = provider
        entity.storage_key = storage_key
        entity.relative_path = rel_path
        entity.drive_file_id = storage.get("drive_file_id")
        entity.drive_folder_id = storage.get("drive_folder_id")
        entity.size_bytes = size_bytes
        entity.sha256 = ma.get("sha256")
        entity.duration_ms = ma.get("duration_ms")
        entity.technical_json = json.dumps(ma.get("technical"), ensure_ascii=False) if ma.get("technical") is not None else None
        entity.coverage_json = json.dumps(ma.get("coverage"), ensure_ascii=False) if ma.get("coverage") is not None else None
        entity.access_policy = ma.get("access_policy", "public")
        entity.enabled = bool(ma.get("enabled", True))
        entity.record_json = json.dumps(ma.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(ma, ensure_ascii=False)
        entity.revision = int((ma.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)

        cov = ma.get("coverage") or []
        movie_id = cov[0].get("episode_id", mid) if isinstance(cov, list) and cov else mid
        if not db.get(Movie, movie_id):
            db.add(Movie(id=movie_id, title=f"Phim liên kết {mid}", release_year=2026, rating=0.0, genres="Animation"))
            db.flush()
        legacy = db.get(MediaAsset, mid) or MediaAsset(id=mid)
        legacy.movie_id = movie_id
        legacy.kind = entity.role
        legacy.storage_provider = provider
        legacy.storage_key = storage_key
        legacy.relative_path = rel_path
        legacy.version = f"v1_{mid}"
        legacy.mime_type = "video/mp4"
        legacy.byte_length = size_bytes
        legacy.duration_seconds = (entity.duration_ms / 1000.0) if entity.duration_ms else None
        legacy.is_public = entity.access_policy.lower() == "public"
        legacy.is_available = entity.enabled
        db.merge(legacy)
    counts["mediaAssets"] = len(media_assets)

    tracks = data.get("text_tracks") or []
    for tt in tracks:
        tid = tt["id"]
        entity = db.get(CatalogTextTrack, tid) or CatalogTextTrack(id=tid)
        entity.media_asset_id = tt["media_asset_id"]
        entity.kind = tt.get("kind", "subtitles")
        entity.language = tt.get("language", "vi")
        entity.label = tt.get("label")
        entity.format = tt.get("format", "vtt")
        entity.external_file_json = json.dumps(tt.get("external_file"), ensure_ascii=False) if tt.get("external_file") is not None else None
        entity.cues_json = json.dumps(tt.get("cues"), ensure_ascii=False) if tt.get("cues") is not None else None
        entity.record_json = json.dumps(tt.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(tt, ensure_ascii=False)
        entity.revision = int((tt.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["textTracks"] = len(tracks)

    scenes = data.get("scenes") or []
    for sc in scenes:
        sc_id = sc["id"]
        entity = db.get(CatalogScene, sc_id) or CatalogScene(id=sc_id)
        entity.media_asset_id = sc.get("media_asset_id")
        entity.episode_id = sc["episode_id"]
        entity.segment_id = sc.get("segment_id")
        entity.start_ms = int(sc.get("start_ms") or 0)
        entity.end_ms = int(sc.get("end_ms") or 0)
        entity.title = sc.get("title")
        entity.summary = sc.get("summary")
        entity.visual_description = sc.get("visual_description") or sc.get("visual_summary")
        entity.character_ids_json = json.dumps(sc.get("character_ids"), ensure_ascii=False) if sc.get("character_ids") is not None else None
        entity.visual_tags_json = json.dumps(sc.get("visual_tags") or sc.get("keywords"), ensure_ascii=False) if (sc.get("visual_tags") or sc.get("keywords")) is not None else None
        entity.sound_events_json = json.dumps(sc.get("sound_events"), ensure_ascii=False) if sc.get("sound_events") is not None else None
        entity.transcript_cue_ids_json = json.dumps(sc.get("transcript_cue_ids"), ensure_ascii=False) if sc.get("transcript_cue_ids") is not None else None
        entity.record_json = json.dumps(sc.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
        entity.raw_json = json.dumps(sc, ensure_ascii=False)
        entity.revision = int((sc.get("record") or {}).get("revision") or revision)
        entity.updated_at = now
        db.merge(entity)
    counts["scenes"] = len(scenes)

    max_ver = db.query(CatalogSnapshot).order_by(CatalogSnapshot.snapshot_version.desc()).first()
    next_gen = (max_ver.snapshot_version + 1) if max_ver else 1
    snap_id = f"snap_{int(time.time() * 1000)}_{pkg_id}_g{next_gen}"
    snap = CatalogSnapshot(
        id=snap_id, snapshot_version=next_gen, content_hash=content_hash,
        total_items=sum(counts.values()), status="READY", retry_count=0,
        created_at=now, completed_at=now, updated_at=now,
    )
    db.add(snap)
    db.commit()
    return {
        "success": True,
        "importId": snap_id,
        "packageId": pkg_id,
        "revision": revision,
        "snapshotVersion": next_gen,
        "contentHash": content_hash,
        "importedAt": now.isoformat(),
        "counts": counts,
        "indexStatus": "READY",
        "message": "Nhập dữ liệu package thành công và đồng bộ trực tiếp trong Python Main.",
    }


def export_eligible_catalog(db, include_draft: bool = False, include_private: bool = False) -> dict:
    def _filter_rows(rows, check_access: bool = False):
        out = []
        for row in rows:
            if not row.raw_json:
                continue
            if not include_draft and not is_published(row.record_json):
                continue
            if check_access and not include_private and str(getattr(row, "access_policy", "public")).lower() != "public":
                continue
            try:
                out.append(json.loads(row.raw_json))
            except Exception:
                pass
        return out

    latest_pkg = db.query(CatalogPackage).order_by(CatalogPackage.imported_at.desc()).first()
    pkg_meta = {
        "id": latest_pkg.id if latest_pkg else "dippie-exported-catalog",
        "version": latest_pkg.version if latest_pkg else "1.0.0",
        "revision": latest_pkg.revision if latest_pkg else 1,
        "default_language": latest_pkg.default_language if latest_pkg else "vi",
        "import_mode": latest_pkg.import_mode if latest_pkg else "upsert",
        "reference_scope": latest_pkg.reference_scope if latest_pkg else "self_contained",
    }
    return {
        "schema_version": "dippie.catalog.v1",
        "package": pkg_meta,
        "genres": _filter_rows(db.query(CatalogGenre).all()),
        "attribute_scales": _filter_rows(db.query(CatalogAttributeScale).all()),
        "sources": _filter_rows(db.query(CatalogSource).all()),
        "series": _filter_rows(db.query(CatalogSeries).all()),
        "seasons": _filter_rows(db.query(CatalogSeason).all()),
        "episodes": _filter_rows(db.query(CatalogEpisode).all()),
        "segments": _filter_rows(db.query(CatalogSegment).all()),
        "characters": _filter_rows(db.query(CatalogCharacter).all()),
        "media_assets": _filter_rows(db.query(CatalogMediaAsset).all(), check_access=True),
        "text_tracks": _filter_rows(db.query(CatalogTextTrack).all()),
        "scenes": _filter_rows(db.query(CatalogScene).all()),
    }

