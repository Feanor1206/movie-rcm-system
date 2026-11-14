import base64
from datetime import datetime, timedelta, timezone
import functools
import hashlib
import json
import os
import secrets
from pathlib import Path
import time

import bcrypt
import jwt
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
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
    __table_args__ = (
        Index("idx_movies_title", "title"),
        Index("idx_movies_year", "release_year"),
        Index("idx_movies_rating", "rating"),
    )
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
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_watchlist"),
        Index("idx_watchlist_user", "user_id"),
        Index("idx_watchlist_movie", "movie_id"),
    )
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
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_rating"),
        Index("idx_ratings_user", "user_id"),
        Index("idx_ratings_movie", "movie_id"),
    )
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
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_favorite"),
        Index("idx_favorite_user", "user_id"),
        Index("idx_favorite_movie", "movie_id"),
    )
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
    __table_args__ = (
        UniqueConstraint("movie_id", "kind", "version", name="uq_movie_kind_version"),
        Index("idx_media_movie_id", "movie_id"),
        Index("idx_media_movie_kind", "movie_id", "kind"),
    )
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
    __table_args__ = (Index("idx_cat_series_title", "title"),)
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
    __table_args__ = (Index("idx_cat_season_series", "series_id"),)
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
    __table_args__ = (
        Index("idx_cat_ep_series", "series_id"),
        Index("idx_cat_ep_season", "season_id"),
    )
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
    __table_args__ = (Index("idx_cat_seg_ep", "episode_id"),)
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
    __table_args__ = (Index("idx_cat_track_asset", "media_asset_id"),)
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
    __table_args__ = (
        Index("idx_cat_scene_ep", "episode_id"),
        Index("idx_cat_scene_asset", "media_asset_id"),
    )
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
    __table_args__ = (Index("idx_cat_snap_status", "status"),)
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
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id", name="uq_watch_progress_user_episode"),
        Index("idx_watch_progress_user_updated", "user_id", "updated_at"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String(100), nullable=False)
    position_ms = Column(BigInteger, nullable=False)
    opt_lock_version = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    __mapper_args__ = {
        "version_id_col": opt_lock_version,
        "version_id_generator": lambda version: 0 if version is None else version + 1,
    }


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _jwt_key() -> bytes:
    return _jwt_key_cached(os.getenv("APP_JWT_SECRET", ""))


@functools.lru_cache(maxsize=4)
def _jwt_key_cached(secret: str) -> bytes:
    try:
        key = base64.b64decode(secret, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("APP_JWT_SECRET phải là khóa Base64 hợp lệ, tối thiểu 32 byte.") from exc
    if len(key) < 32 or key in (
        base64.b64decode(DEFAULT_JWT_SECRET),
        base64.b64decode("dippieSecretKeyForJwtAuthentication2026MustBeLongEnoughForHmacSha256"),
    ):
        raise RuntimeError("APP_JWT_SECRET phải là khóa riêng, tối thiểu 32 byte; không dùng khóa mặc định cũ.")
    return key


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
        if payload.get("type") == "playback_grant" or payload.get("purpose") == "playback":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_playback_grant_token(asset_id: str, username: str, role: str, validity_seconds: int = 300) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username or "anonymous",
        "assetId": asset_id,
        "role": role or "ROLE_ANONYMOUS",
        "type": "playback_grant",
        "purpose": "playback",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=validity_seconds)).timestamp()),
    }
    return jwt.encode(payload, _jwt_key(), algorithm="HS256")


def validate_playback_grant_token(token: str, asset_id: str) -> str | None:
    try:
        payload = jwt.decode(token, _jwt_key(), algorithms=["HS256"])
        if payload.get("type") != "playback_grant":
            return None
        if not asset_id or payload.get("assetId") != asset_id:
            return None
        return str(payload.get("role") or "ROLE_ANONYMOUS")
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
    ("drive-videoplayback", "Shin Cậu Bé Bút Chì: Chuyến phiêu lưu kỳ thú", 2026, 8.8, "7m 25s", "Animation,Comedy,Adventure,Family", "Tập phim Shin Cậu Bé Bút Chì phát từ Google Drive.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85", "/api/media/stream/ast-drive-videoplayback"),
    ("the-last-orbit", "The Last Orbit", 2026, 8.7, "2h 14m", "Animation,Sci-Fi,Drama", "Một nữ phi hành gia lần theo tín hiệu dẫn cô về nhà. Đó có thể là ký ức cuối cùng của một thế giới đã mất.", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85", "/videos/the-last-orbit.mp4"),
    ("spirited-away", "Spirited Away", 2001, 8.6, "2h 05m", "Animation,Adventure,Family,Fantasy", "Một cô bé lạc vào nhà tắm của các linh hồn và phù thủy. Cô phải tìm cách cứu cha mẹ.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1800&q=85", "/videos/the-last-orbit.mp4"),
    ("your-name", "Your Name", 2016, 8.4, "1h 46m", "Animation,Romance,Drama,Fantasy", "Hai thiếu niên phát hiện họ có thể hoán đổi thân xác dù sống ở những nơi và thời điểm khác nhau.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85", "/videos/afterlight.mp4"),
    ("spider-verse", "Spider-Man: Into the Spider-Verse", 2018, 8.4, "1h 57m", "Animation,Action,Adventure,Sci-Fi", "Miles Morales trở thành Người Nhện và gặp năm Người Nhện đến từ các chiều không gian khác.", "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=1800&q=85", "/videos/glass-horizon.mp4"),
    ("isle-of-dogs", "Isle of Dogs", 2018, 7.8, "1h 41m", "Animation,Adventure,Comedy,Drama", "Một cậu bé ở Nhật Bản đến đảo rác để tìm Spots, chú chó bị đày khỏi thành phố.", "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1800&q=85", "/videos/deep-blue.mp4"),
    ("coraline", "Coraline", 2009, 7.7, "1h 40m", "Animation,Drama,Family,Fantasy,Horror", "Coraline, 11 tuổi, tìm thấy một thế giới giống nhà mình đến kỳ lạ. Nơi tưởng chừng hoàn hảo ấy che giấu những bí mật đáng sợ.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=1800&q=85", "/videos/nocturne.mp4"),
    ("fantasia-1940", "Fantasia", 1940, 7.7, "2h 05m", "Animation,Family,Fantasy,Musical", "Tuyển tập hoạt hình lấy cảm hứng từ các tác phẩm nhạc cổ điển phương Tây.", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1800&q=85", "/videos/quiet-places.mp4"),
    ("afterlight", "Afterlight", 2025, 8.3, "1h 58m", "Animation,Drama,Mystery", "Trong thành phố chìm trong đêm, một nhiếp ảnh gia lần theo tia nắng duy nhất.", "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85", "/videos/afterlight.mp4"),
    ("glass-horizon", "Glass Horizon", 2026, 8.1, "2h 06m", "Animation,Thriller,Sci-Fi", "Một kiến trúc sư được giao thiết kế một thành phố mà cư dân không thể rời đi.", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85", "/videos/glass-horizon.mp4"),
    ("deep-blue", "Deep Blue", 2024, 7.9, "1h 46m", "Animation,Adventure,Drama", "Hai chị em xa cách cùng vượt qua vùng biển chưa có trên bản đồ để tìm cha.", "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85", "/videos/deep-blue.mp4"),
    ("quiet-places", "Quiet Places", 2025, 8.5, "2h 01m", "Animation,Romance,Drama", "Một nữ nhạc sĩ trở về thị trấn từng bỏ đi và tìm lại một ca khúc cũ.", "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85", "/videos/quiet-places.mp4"),
    ("nocturne", "Nocturne", 2024, 7.8, "1h 52m", "Animation,Crime,Thriller", "Một thám tử điều tra chuỗi vụ án xảy ra đúng nửa đêm.", "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85", "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85", "/videos/nocturne.mp4"),
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
            if url.startswith("sqlite"):
                connect_args = {"check_same_thread": False}
                self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
                @event.listens_for(self.engine, "connect")
                def _set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.close()
            else:
                connect_args = {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "3"))}
                self.engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
                    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
                    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
                    connect_args=connect_args,
                )
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

    def secure_accounts(self):
        if os.getenv("APP_DEMO_MODE", "").lower() == "true":
            return
        username = os.getenv("APP_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        email = os.getenv("APP_BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.getenv("APP_BOOTSTRAP_ADMIN_PASSWORD", "")
        if (username or email or password) and (not username or not password):
            raise RuntimeError("Cần cả APP_BOOTSTRAP_ADMIN_USERNAME và APP_BOOTSTRAP_ADMIN_PASSWORD.")
        if password and (len(password.strip()) < 16 or len(password.encode("utf-8")) > 72):
            raise RuntimeError("Mật khẩu quản trị phải dài từ 16 ký tự đến 72 byte.")
        with self.session() as db:
            admins = db.query(User).filter(User.role == "ROLE_ADMIN").all()
            admin = next((user for user in admins if user.username == username), None)
            weak_admins = [user for user in admins if verify_password("password123", user.password)]
            if weak_admins:
                if len(weak_admins) != 1 or admin is not weak_admins[0] or not password:
                    raise RuntimeError("Tài khoản quản trị dùng mật khẩu demo; đặt APP_BOOTSTRAP_ADMIN_USERNAME và APP_BOOTSTRAP_ADMIN_PASSWORD để đổi mật khẩu.")
                admin.password = hash_password(password)
            elif password and not admin:
                if admins:
                    raise RuntimeError("Đã có quản trị viên; không thể tự động tạo thêm tài khoản quản trị.")
                if not email:
                    raise RuntimeError("Cần APP_BOOTSTRAP_ADMIN_EMAIL để tạo quản trị viên.")
                if db.query(User).filter((User.username == username) | (User.email == email)).first():
                    raise RuntimeError("Tên đăng nhập hoặc email quản trị đã được dùng.")
                db.add(User(username=username, email=email, password=hash_password(password), role="ROLE_ADMIN"))
            legacy_user = db.query(User).filter(User.username == "user", User.email == "user@dippie.com", User.role == "ROLE_USER").first()
            if legacy_user and verify_password("password123", legacy_user.password):
                legacy_user.password = hash_password(secrets.token_urlsafe(32))
            db.commit()

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
            if os.getenv("APP_DEMO_MODE", "").lower() == "true":
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
    if not record_json or "ready" not in record_json.lower():
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


CATALOG_COLLECTIONS = {
    "genres": CatalogGenre,
    "attribute_scales": CatalogAttributeScale,
    "sources": CatalogSource,
    "series": CatalogSeries,
    "seasons": CatalogSeason,
    "episodes": CatalogEpisode,
    "segments": CatalogSegment,
    "characters": CatalogCharacter,
    "media_assets": CatalogMediaAsset,
    "text_tracks": CatalogTextTrack,
    "scenes": CatalogScene,
}


class CatalogInputError(ValueError):
    def __init__(self, path, message):
        super().__init__(message)
        self.path = path


class CatalogConflictError(ValueError):
    pass


def is_relative_media_path(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not value.startswith("/")
        and not any(char in "\\:" or ord(char) < 32 or ord(char) == 127 for char in value)
        and all(part.rstrip(" ") != ".." for part in value.split("/"))
    )


def validate_catalog_input(data):
    def check_revision(value, path):
        if type(value) is not int or not 1 <= value <= 2_147_483_647:
            raise CatalogInputError(path, "Phiên bản phải là số nguyên dương hợp lệ.")

    def check_id(value, path, max_length=100):
        if not isinstance(value, str) or not value.strip() or len(value) > max_length or value != value.strip():
            raise CatalogInputError(path, "Mã định danh không hợp lệ.")

    pkg = data.get("package") if isinstance(data, dict) else None
    if not isinstance(pkg, dict) or not pkg.get("id"):
        raise CatalogInputError("package.id", "Thiếu mã gói danh mục.")
    check_id(pkg["id"], "package.id")
    revision = pkg.get("revision", 1)
    check_revision(revision, "package.revision")
    for collection in CATALOG_COLLECTIONS:
        items = data.get(collection)
        if items is None:
            continue
        if not isinstance(items, list):
            raise CatalogInputError(collection, "Cần một danh sách bản ghi.")
        ids = set()
        for index, item in enumerate(items):
            path = f"{collection}[{index}]"
            if not isinstance(item, dict):
                raise CatalogInputError(path, "Bản ghi không hợp lệ.")
            item_id = item.get("id")
            check_id(item_id, f"{path}.id", 64 if collection == "media_assets" else 100)
            if item_id.casefold() in ids:
                raise CatalogInputError(f"{path}.id", "Mã định danh bị trùng.")
            ids.add(item_id.casefold())
            record = item.get("record")
            if record is not None:
                if not isinstance(record, dict):
                    raise CatalogInputError(f"{path}.record", "Bản ghi không hợp lệ.")
                check_revision(record.get("revision", revision), f"{path}.record.revision")
            if collection == "media_assets":
                storage = item.get("storage")
                if storage is not None and not isinstance(storage, dict):
                    raise CatalogInputError(f"{path}.storage", "Thông tin lưu trữ không hợp lệ.")
                media_path = (storage or {}).get("relative_path", f"media/{item_id}.mp4")
                if not is_relative_media_path(media_path) or len(media_path) > 500:
                    raise CatalogInputError(f"{path}.storage.relative_path", "Đường dẫn video phải nằm trong thư mục lưu trữ.")
                if item.get("access_policy", "public") not in ("public", "authenticated", "private"):
                    raise CatalogInputError(f"{path}.access_policy", "Quyền truy cập video không hợp lệ.")
    return pkg["id"], revision


def _stored_catalog_hash(raw_json):
    if raw_json:
        try:
            return compute_sha256(json.loads(raw_json))
        except (TypeError, ValueError):
            return compute_sha256(raw_json)
    return ""


def catalog_diff(db, data, revision, content_hash, existing_pkg, lock=False):
    counts = dict(toCreate=0, toUpdate=0, unchanged=0, conflicts=0)
    stored = {}

    def count(stored_revision, incoming_revision, same_content):
        if stored_revision is None:
            counts["toCreate"] += 1
        elif incoming_revision > stored_revision:
            counts["toUpdate"] += 1
        elif incoming_revision == stored_revision and same_content:
            counts["unchanged"] += 1
        else:
            counts["conflicts"] += 1

    count(
        existing_pkg.revision if existing_pkg else None,
        revision,
        existing_pkg is not None and content_hash == existing_pkg.content_hash,
    )
    for collection, model in CATALOG_COLLECTIONS.items():
        items = data.get(collection) or []
        if not items:
            continue
        query = db.query(model).filter(model.id.in_([item["id"] for item in items]))
        if lock:
            query = query.with_for_update().populate_existing()
        existing_rows = {row.id: row for row in query}
        stored[collection] = existing_rows
        for item in items:
            existing = existing_rows.get(item["id"])
            item_revision = (item.get("record") or {}).get("revision", revision)
            old_revision = existing.revision if existing else None
            if existing and existing.record_json:
                try:
                    recorded = json.loads(existing.record_json)
                    if isinstance(recorded, dict) and type(recorded.get("revision")) is int:
                        old_revision = recorded["revision"]
                except (TypeError, ValueError):
                    pass
            same_content = (
                existing is not None and item_revision == old_revision
                and compute_sha256(item) == _stored_catalog_hash(existing.raw_json)
            )
            count(old_revision, item_revision, same_content)
    return counts, stored


def import_catalog_package(db, data: dict) -> dict:
    pkg_id, revision = validate_catalog_input(data)
    pkg = data["package"]
    version = str(pkg.get("version") or "1.0.0")
    default_lang = str(pkg.get("default_language") or "vi")
    import_mode = str(pkg.get("import_mode") or "upsert")
    ref_scope = str(pkg.get("reference_scope") or "self_contained")
    content_hash = compute_sha256(data)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.execute(text("BEGIN IMMEDIATE"))
    existing_pkg = db.get(CatalogPackage, pkg_id, with_for_update=True, populate_existing=True)
    changes, stored = catalog_diff(db, data, revision, content_hash, existing_pkg, lock=True)
    if changes["conflicts"]:
        raise CatalogConflictError("Gói danh mục xung đột với phiên bản đã lưu.")

    counts = {
        {"attribute_scales": "attributeScales", "media_assets": "mediaAssets", "text_tracks": "textTracks"}.get(key, key):
            len(data.get(key) or [])
        for key in CATALOG_COLLECTIONS
    }
    if not changes["toCreate"] and not changes["toUpdate"]:
        snap = (
            db.query(CatalogSnapshot).filter_by(content_hash=content_hash)
            .order_by(CatalogSnapshot.snapshot_version.desc()).with_for_update().first()
        )
        if snap:
            return {
                "success": True,
                "unchanged": True,
                "importId": snap.id,
                "packageId": pkg_id,
                "revision": revision,
                "snapshotVersion": snap.snapshot_version,
                "contentHash": content_hash,
                "importedAt": existing_pkg.imported_at.isoformat() if existing_pkg.imported_at else None,
                "counts": counts,
                "indexStatus": snap.status,
                "message": "Gói danh mục đã được nhập.",
            }
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

    genres = data.get("genres") or []
    if genres:
        existing = stored["genres"]
        for g in genres:
            gid = g["id"]
            entity = existing.get(gid)
            if not entity:
                entity = CatalogGenre(id=gid)
                db.add(entity)
            entity.labels_json = json.dumps(g.get("labels") or {"vi": g.get("name", gid)}, ensure_ascii=False)
            entity.aliases_json = json.dumps(g.get("aliases"), ensure_ascii=False) if g.get("aliases") is not None else None
            entity.description = g.get("description")
            entity.record_json = json.dumps(g.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
            entity.raw_json = json.dumps(g, ensure_ascii=False)
            entity.revision = int((g.get("record") or {}).get("revision") or revision)
            entity.updated_at = now

    scales = data.get("attribute_scales") or []
    if scales:
        existing = stored["attribute_scales"]
        for sc in scales:
            sid = sc["id"]
            entity = existing.get(sid)
            if not entity:
                entity = CatalogAttributeScale(id=sid)
                db.add(entity)
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

    sources = data.get("sources") or []
    if sources:
        existing = stored["sources"]
        for src in sources:
            sid = src["id"]
            entity = existing.get(sid)
            if not entity:
                entity = CatalogSource(id=sid)
                db.add(entity)
            entity.kind = src.get("kind") or src.get("source_type") or "web"
            entity.title = src.get("title") or src.get("name") or sid
            entity.uri = src.get("url") or src.get("uri")
            entity.note = src.get("note") or src.get("notes")
            entity.retrieved_at = src.get("retrieved_at")
            entity.record_json = json.dumps(src.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
            entity.raw_json = json.dumps(src, ensure_ascii=False)
            entity.revision = int((src.get("record") or {}).get("revision") or revision)
            entity.updated_at = now

    series_list = data.get("series") or []
    seasons = data.get("seasons") or []
    episodes = data.get("episodes") or []
    media_assets = data.get("media_assets") or []

    needed_movie_ids = {s["id"] for s in series_list if "id" in s} | {ep["id"] for ep in episodes if "id" in ep}
    for ma in media_assets:
        cov = ma.get("coverage") or []
        m_id = cov[0].get("episode_id", ma["id"]) if isinstance(cov, list) and cov else ma["id"]
        needed_movie_ids.add(m_id)
    existing_movies = {row.id: row for row in db.query(Movie).filter(Movie.id.in_(needed_movie_ids)).all()} if needed_movie_ids else {}

    if series_list:
        existing = stored["series"]
        for s in series_list:
            sid = s["id"]
            entity = existing.get(sid)
            if not entity:
                entity = CatalogSeries(id=sid)
                db.add(entity)
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
            if sid not in existing_movies:
                m = Movie(
                    id=sid, title=entity.title, release_year=entity.release_year_start or 2026,
                    rating=0.0, runtime="Series", genres="Animation", description=entity.synopsis or "",
                )
                db.add(m)
                existing_movies[sid] = m
    db.flush()

    if seasons:
        existing = stored["seasons"]
        for sea in seasons:
            sea_id = sea["id"]
            entity = existing.get(sea_id)
            if not entity:
                entity = CatalogSeason(id=sea_id)
                db.add(entity)
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

    if episodes:
        existing = stored["episodes"]
        for ep in episodes:
            ep_id = ep["id"]
            entity = existing.get(ep_id)
            if not entity:
                entity = CatalogEpisode(id=ep_id)
                db.add(entity)
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
            if ep_id not in existing_movies:
                mins = int((entity.duration_ms or 1200000) / 60000)
                m = Movie(
                    id=ep_id, title=entity.title, release_year=2026,
                    rating=0.0, runtime=f"{mins}m", genres="Animation", description=entity.synopsis or "",
                )
                db.add(m)
                existing_movies[ep_id] = m
    db.flush()

    segments = data.get("segments") or []
    if segments:
        existing = stored["segments"]
        for seg in segments:
            seg_id = seg["id"]
            entity = existing.get(seg_id)
            if not entity:
                entity = CatalogSegment(id=seg_id)
                db.add(entity)
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

    characters = data.get("characters") or []
    if characters:
        existing = stored["characters"]
        for c in characters:
            cid = c["id"]
            entity = existing.get(cid)
            if not entity:
                entity = CatalogCharacter(id=cid)
                db.add(entity)
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

    if media_assets:
        existing_cat_assets = stored["media_assets"]
        ids = [ma["id"] for ma in media_assets]
        existing_leg_assets = {row.id: row for row in db.query(MediaAsset).filter(MediaAsset.id.in_(ids)).with_for_update()}
        for ma in media_assets:
            cov = ma.get("coverage") or []
            movie_id = cov[0].get("episode_id", ma["id"]) if isinstance(cov, list) and cov else ma["id"]
            if movie_id not in existing_movies:
                movie = Movie(id=movie_id, title=f"Phim liên kết {ma['id']}", release_year=2026, rating=0.0, genres="Animation")
                db.add(movie)
                existing_movies[movie_id] = movie
        db.flush()
        for ma in media_assets:
            mid = ma["id"]
            storage = ma.get("storage") or {}
            p_str = str(storage.get("provider") or "local").lower()
            provider = "drive" if p_str in ("drive", "google_drive") else "local"
            storage_key = storage.get("storage_key") or storage.get("root_storage_key") or "local_main"
            rel_path = storage.get("relative_path") or f"media/{mid}.mp4"
            size_bytes = ma.get("size_bytes") if ma.get("size_bytes") is not None else (ma.get("byte_length") or 0)
            entity = existing_cat_assets.get(mid)
            if not entity:
                entity = CatalogMediaAsset(id=mid)
                db.add(entity)
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

            cov = ma.get("coverage") or []
            movie_id = cov[0].get("episode_id", mid) if isinstance(cov, list) and cov else mid
            legacy = existing_leg_assets.get(mid)
            if not legacy:
                legacy = MediaAsset(id=mid)
                db.add(legacy)
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
    db.flush()

    tracks = data.get("text_tracks") or []
    if tracks:
        existing = stored["text_tracks"]
        for tt in tracks:
            tid = tt["id"]
            entity = existing.get(tid)
            if not entity:
                entity = CatalogTextTrack(id=tid)
                db.add(entity)
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

    scenes = data.get("scenes") or []
    if scenes:
        existing = stored["scenes"]
        for sc in scenes:
            sc_id = sc["id"]
            entity = existing.get(sc_id)
            if not entity:
                entity = CatalogScene(id=sc_id)
                db.add(entity)
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

    max_ver = db.query(CatalogSnapshot).order_by(CatalogSnapshot.snapshot_version.desc()).with_for_update().first()
    next_gen = (max_ver.snapshot_version + 1) if max_ver else 1
    snap_id = f"snap_{int(time.time() * 1000)}_{pkg_id[:48]}_g{next_gen}"
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
        "message": "Đã nhập gói danh mục.",
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
    created_at_iso = (
        latest_pkg.created_at.isoformat() + "Z"
        if (latest_pkg and latest_pkg.created_at)
        else datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
    )
    pkg_meta = {
        "id": latest_pkg.id if latest_pkg else "dippie-exported-catalog",
        "version": latest_pkg.version if latest_pkg else "1.0.0",
        "revision": latest_pkg.revision if latest_pkg else 1,
        "description": (latest_pkg.description if (latest_pkg and latest_pkg.description) else "Canonical catalog export"),
        "created_at": created_at_iso,
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

