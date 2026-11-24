import base64
from datetime import date, datetime, timedelta, timezone
import functools
import hashlib
import json
import logging
import mimetypes
import os
import re
import secrets
import threading
from pathlib import Path
import time

import bcrypt
import jwt
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    func,
    insert,
    inspect,
    or_,
    select,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.exc import SQLAlchemyError

Base = declarative_base()
LongText = Text().with_variant(mysql.LONGTEXT(), "mysql")
DoublePrecision = Float().with_variant(mysql.DOUBLE(asdecimal=False), "mysql")
Timestamp = DateTime().with_variant(mysql.TIMESTAMP(), "mysql")
GenreName = String(255).with_variant(mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql")


class CurrentTimestampOnUpdate(FunctionElement):
    inherit_cache = True


@compiles(CurrentTimestampOnUpdate)
def compile_timestamp_default(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP"


@compiles(CurrentTimestampOnUpdate, "mysql")
def compile_mysql_timestamp_default(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"

DEFAULT_JWT_SECRET = "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("HEX(role) IN (HEX('ROLE_USER'), HEX('ROLE_ADMIN'))", name="ck_user_role"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), nullable=False, default="ROLE_USER", server_default=text("'ROLE_USER'"))
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 0 AND 10", name="ck_movie_rating_bounds"),
        Index("idx_movies_title", "title"),
        Index("idx_movies_year", "release_year"),
        Index("idx_movies_rating", "rating"),
    )
    id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    release_year = Column(Integer, nullable=False)
    rating = Column(DoublePrecision, nullable=False)
    runtime = Column(String(20))
    genres = Column(LongText)
    description = Column(LongText)
    poster = Column(String(500))
    backdrop = Column(String(500))
    video_url = Column(String(500))
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE", name="fk_watchlist_user"), nullable=False)
    movie_id = Column(String(100), ForeignKey("movies.id", name="fk_watchlist_movie", ondelete="CASCADE"), nullable=False)
    added_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self, movie):
        return {
            "id": self.id,
            "userId": self.user_id,
            "movieId": self.movie_id,
            "movieTitle": movie.title,
            "posterUrl": movie.poster,
            "addedAt": self.added_at.isoformat() if self.added_at else None,
        }


class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 10", name="ck_movie_rating_range"),
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_rating"),
        Index("idx_ratings_user", "user_id"),
        Index("idx_ratings_movie", "movie_id"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE", name="fk_rating_user"), nullable=False)
    movie_id = Column(String(100), ForeignKey("movies.id", name="fk_rating_movie", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE", name="fk_favorite_user"), nullable=False)
    movie_id = Column(String(100), ForeignKey("movies.id", name="fk_favorite_movie", ondelete="CASCADE"), nullable=False)
    added_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self, movie):
        return {
            "id": self.id,
            "userId": self.user_id,
            "movieId": self.movie_id,
            "movieTitle": movie.title,
            "posterUrl": movie.poster,
            "addedAt": self.added_at.isoformat() if self.added_at else None,
        }


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint("HEX(kind) IN (HEX('feature'), HEX('trailer'), HEX('extra'), HEX('opening'), HEX('ending'), HEX('dub'), HEX('audio_description'))", name="ck_media_kind"),
        UniqueConstraint("movie_id", "kind", "version", name="uq_movie_kind_version"),
        Index("idx_media_movie_id", "movie_id"),
        Index("idx_media_movie_kind", "movie_id", "kind"),
    )
    id = Column(String(64), primary_key=True)
    movie_id = Column(String(100), ForeignKey("movies.id", ondelete="CASCADE", name="fk_media_movie"), nullable=False)
    kind = Column(String(20), nullable=False)
    storage_provider = Column(String(30), nullable=False, default="local", server_default=text("'local'"))
    storage_key = Column(String(100))
    relative_path = Column(String(500), nullable=False)
    version = Column(String(50), nullable=False, default="v1", server_default=text("'v1'"))
    mime_type = Column(String(100), nullable=False, default="video/mp4", server_default=text("'video/mp4'"))
    byte_length = Column(BigInteger, nullable=False, default=0)
    duration_seconds = Column(DoublePrecision)
    is_public = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    is_available = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    __table_args__ = (CheckConstraint("HEX(status) IN (HEX('COMMITTED'))", name="ck_catalog_package_status"),)
    id = Column(String(100), primary_key=True)
    version = Column(String(50), nullable=False)
    revision = Column(Integer, nullable=False)
    default_language = Column(String(20), nullable=False)
    import_mode = Column(String(50), nullable=False)
    reference_scope = Column(String(50), nullable=False)
    name = Column(String(200))
    description = Column(LongText)
    content_hash = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    error_message = Column(LongText)
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    created_at = Column(Timestamp, nullable=False, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    imported_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    labels_json = Column(LongText, nullable=False)
    aliases_json = Column(LongText)
    description = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogAttributeScale(Base):
    __tablename__ = "catalog_attribute_scales"
    __table_args__ = (CheckConstraint("minimum < maximum", name="ck_catalog_scale_bounds"),)
    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    definition = Column(LongText)
    minimum = Column(DoublePrecision, nullable=False)
    maximum = Column(DoublePrecision, nullable=False)
    levels_json = Column(LongText, nullable=False)
    version = Column(String(50))
    source_ids_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    __table_args__ = (CheckConstraint("HEX(kind) IN (HEX('manual'), HEX('official'), HEX('external_catalog'), HEX('subtitle'), HEX('transcript'), HEX('video_observation'), HEX('model_output'), HEX('other'))", name="ck_catalog_source_kind"),)
    id = Column(String(100), primary_key=True)
    kind = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    uri = Column(String(1000))
    note = Column(LongText)
    retrieved_at = Column(DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql"))
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogSeries(Base):
    __tablename__ = "catalog_series"
    __table_args__ = (
        Index("idx_cat_series_title", "title"),
        CheckConstraint("release_year_start <= release_year_end", name="ck_catalog_series_years"),
    )
    id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    original_title = Column(String(255))
    aliases_json = Column(LongText)
    synopsis = Column(LongText)
    translations_json = Column(LongText)
    genre_ids_json = Column(LongText)
    keywords_json = Column(LongText)
    themes_json = Column(LongText)
    origin_countries_json = Column(LongText)
    original_languages_json = Column(LongText)
    release_year_start = Column(Integer)
    release_year_end = Column(Integer)
    release_status = Column(String(50))
    character_ids_json = Column(LongText)
    artworks_json = Column(LongText)
    attributes_json = Column(LongText)
    ratings_json = Column(LongText)
    advisories_json = Column(LongText)
    credits_json = Column(LongText)
    external_ids_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    __table_args__ = (
        UniqueConstraint("series_id", "id", name="uq_cat_season_series_id"),
        CheckConstraint("kind IS NULL OR HEX(kind) IN (HEX('regular'), HEX('specials'), HEX('collection'), HEX('unknown'))", name="ck_catalog_season_kind"),
    )
    id = Column(String(100), primary_key=True)
    series_id = Column(String(100), ForeignKey("catalog_series.id", ondelete="CASCADE", name="fk_season_series"), nullable=False)
    number = Column(Integer)
    title = Column(String(255), nullable=False)
    synopsis = Column(LongText)
    kind = Column(String(50))
    translations_json = Column(LongText)
    release_date = Column(Date)
    artworks_json = Column(LongText)
    attributes_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self):
        return {
            "id": self.id,
            "seriesId": self.series_id,
            "number": self.number,
            "title": self.title,
            "synopsis": self.synopsis,
            "kind": self.kind,
            "translationsJson": self.translations_json,
            "releaseDate": self.release_date.isoformat() if self.release_date else None,
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
        CheckConstraint("duration_ms > 0", name="ck_catalog_episode_duration"),
        CheckConstraint("HEX(kind) IN (HEX('regular'), HEX('special'), HEX('ova'), HEX('ona'), HEX('recap'), HEX('short'), HEX('pilot'), HEX('movie'), HEX('unknown'))", name="ck_catalog_episode_kind"),
        ForeignKeyConstraint(
            ["series_id", "season_id"], ["catalog_seasons.series_id", "catalog_seasons.id"],
            name="fk_episode_season_same_series",
        ),
        Index("idx_cat_ep_series_season", "series_id", "season_id"),
        Index("idx_cat_ep_season", "season_id"),
        Index("idx_cat_ep_publication", "publication_status"),
    )
    id = Column(String(100), primary_key=True)
    series_id = Column(String(100), ForeignKey("catalog_series.id", ondelete="CASCADE", name="fk_episode_series"), nullable=False)
    season_id = Column(String(100))
    number = Column(Integer)
    title = Column(String(255), nullable=False)
    aliases_json = Column(LongText)
    synopsis = Column(LongText)
    translations_json = Column(LongText)
    kind = Column(String(50), nullable=False)
    release_date = Column(Date)
    duration_ms = Column(BigInteger)
    genre_ids_json = Column(LongText)
    primary_language = Column(String(50))
    orders_json = Column(LongText)
    links_json = Column(LongText)
    character_ids_json = Column(LongText)
    plot_facts_json = Column(LongText)
    keywords_json = Column(LongText)
    themes_json = Column(LongText)
    attributes_json = Column(LongText)
    ratings_json = Column(LongText)
    artworks_json = Column(LongText)
    credits_json = Column(LongText)
    record_json = Column(LongText)
    publication_status = Column(
        String(16), CheckConstraint("HEX(publication_status) IN (HEX('draft'), HEX('ready'), HEX('archived'))", name="ck_catalog_episode_publication"),
        nullable=False, default="draft", server_default=text("'draft'"),
    )
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
            "releaseDate": self.release_date.isoformat() if self.release_date else None,
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


SEGMENT_TIME_RANGE = (
    "(({row}episode_start_ms IS NULL AND {row}episode_end_ms IS NULL) OR "
    "({row}episode_start_ms IS NOT NULL AND {row}episode_end_ms IS NOT NULL AND "
    "{row}episode_start_ms >= 0 AND {row}episode_end_ms > {row}episode_start_ms))"
)
SEGMENT_SQLITE_TYPES = (
    "(typeof({row}position) = 'integer' AND "
    "typeof({row}episode_start_ms) IN ('null', 'integer') AND "
    "typeof({row}episode_end_ms) IN ('null', 'integer'))"
)


class CatalogSegment(Base):
    __tablename__ = "catalog_segments"
    __table_args__ = (
        Index("uq_cat_segment_position", "episode_id", "position", unique=True),
        CheckConstraint(SEGMENT_TIME_RANGE.format(row=""), name="ck_cat_segment_time_range"),
        CheckConstraint(SEGMENT_SQLITE_TYPES.format(row=""), name="ck_cat_segment_integer_types").ddl_if(dialect="sqlite"),
    )
    id = Column(String(100), primary_key=True)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE", name="fk_segment_episode"), nullable=False)
    position = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    aliases_json = Column(LongText)
    synopsis = Column(LongText)
    translations_json = Column(LongText)
    primary_language = Column(String(50))
    character_ids_json = Column(LongText)
    plot_facts_json = Column(LongText)
    keywords_json = Column(LongText)
    themes_json = Column(LongText)
    attributes_json = Column(LongText)
    episode_start_ms = Column(BigInteger)
    episode_end_ms = Column(BigInteger)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    series_ids_json = Column(LongText)
    name = Column(String(255), nullable=False)
    aliases_json = Column(LongText)
    description = Column(LongText)
    role = Column(String(50))
    traits_json = Column(LongText)
    relationships_json = Column(LongText)
    voice_credits_json = Column(LongText)
    artworks_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogEpisodeCharacter(Base):
    __tablename__ = "catalog_episode_characters"
    __table_args__ = (Index("idx_cat_ep_character", "character_id"),)

    episode_id = Column(ForeignKey("catalog_episodes.id", ondelete="CASCADE"), primary_key=True)
    character_id = Column(ForeignKey("catalog_characters.id", ondelete="CASCADE"), primary_key=True)


class CatalogEpisodeGenre(Base):
    __tablename__ = "catalog_episode_genres"
    __table_args__ = (Index("idx_cat_ep_genre", "genre_id"),)

    episode_id = Column(ForeignKey("catalog_episodes.id", ondelete="CASCADE"), primary_key=True)
    genre_id = Column(ForeignKey("catalog_genres.id", ondelete="CASCADE"), primary_key=True)


class MovieGenreTerm(Base):
    __tablename__ = "movie_genre_terms"
    name = Column(GenreName, primary_key=True)


class CatalogSeriesGenre(Base):
    __tablename__ = "catalog_series_genres"
    __table_args__ = (Index("idx_cat_series_genre", "genre_id"),)
    series_id = Column(ForeignKey("catalog_series.id", name="fk_catalog_series_genres_series_id", ondelete="CASCADE"), primary_key=True)
    genre_id = Column(ForeignKey("catalog_genres.id", name="fk_catalog_series_genres_genre_id", ondelete="CASCADE"), primary_key=True)


class CatalogSeriesCharacter(Base):
    __tablename__ = "catalog_series_characters"
    __table_args__ = (Index("idx_cat_series_character", "character_id"),)
    series_id = Column(ForeignKey("catalog_series.id", name="fk_catalog_series_characters_series_id", ondelete="CASCADE"), primary_key=True)
    character_id = Column(ForeignKey("catalog_characters.id", name="fk_catalog_series_characters_character_id", ondelete="CASCADE"), primary_key=True)


class CatalogCharacterSeries(Base):
    __tablename__ = "catalog_character_series"
    __table_args__ = (Index("idx_cat_character_series", "series_id"),)
    character_id = Column(ForeignKey("catalog_characters.id", name="fk_catalog_character_series_character_id", ondelete="CASCADE"), primary_key=True)
    series_id = Column(ForeignKey("catalog_series.id", name="fk_catalog_character_series_series_id", ondelete="CASCADE"), primary_key=True)


class MovieGenre(Base):
    __tablename__ = "movie_genres"
    __table_args__ = (Index("idx_movie_genre_name", "genre_name"),)
    movie_id = Column(ForeignKey("movies.id", name="fk_movie_genres_movie_id", ondelete="CASCADE"), primary_key=True)
    genre_name = Column(ForeignKey("movie_genre_terms.name", name="fk_movie_genres_genre_name", ondelete="CASCADE"), primary_key=True)


class CatalogMediaAsset(Base):
    __tablename__ = "catalog_media_assets"
    __table_args__ = (
        CheckConstraint("duration_ms > 0", name="ck_catalog_asset_duration"),
        CheckConstraint("size_bytes >= 0", name="ck_catalog_asset_size"),
        CheckConstraint("HEX(role) IN (HEX('feature'), HEX('trailer'), HEX('extra'), HEX('opening'), HEX('ending'), HEX('dub'), HEX('audio_description'))", name="ck_catalog_asset_role"),
        CheckConstraint("HEX(access_policy) IN (HEX('private'), HEX('authenticated'), HEX('public'))", name="ck_catalog_asset_policy"),
        CheckConstraint("HEX(content_type) IN (HEX('video'), HEX('audio'))", name="ck_catalog_asset_content"),
    )
    id = Column(String(100), primary_key=True)
    content_type = Column(String(50), nullable=False, default="video", server_default=text("'video'"))
    role = Column(String(50), nullable=False, default="feature", server_default=text("'feature'"))
    edition_label = Column(String(100))
    spoken_languages_json = Column(LongText)
    embedded_subtitle_languages_json = Column(LongText)
    storage_provider = Column(String(50), nullable=False)
    storage_key = Column(String(100), nullable=False)
    relative_path = Column(String(500), nullable=False)
    drive_file_id = Column(String(255))
    drive_folder_id = Column(String(255))
    size_bytes = Column(BigInteger)
    sha256 = Column(String(100))
    duration_ms = Column(BigInteger)
    technical_json = Column(LongText)
    coverage_json = Column(LongText)
    related_asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", name="fk_asset_related", ondelete="SET NULL"))
    access_policy = Column(String(50), nullable=False, default="public", server_default=text("'public'"))
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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


class CatalogEpisodeAsset(Base):
    __tablename__ = "catalog_episode_assets"
    __table_args__ = (Index("idx_cat_episode_assets_media", "media_asset_id"),)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE", name="fk_cat_ep_asset_ep"), primary_key=True)
    media_asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", ondelete="CASCADE", name="fk_cat_ep_asset_media"), primary_key=True)


class CatalogTextTrack(Base):
    __tablename__ = "catalog_text_tracks"
    __table_args__ = (
        CheckConstraint("HEX(kind) IN (HEX('subtitle'), HEX('transcript'), HEX('ocr'))", name="ck_catalog_track_kind"),
        Index("idx_cat_track_asset", "media_asset_id"),
        Index("idx_cat_track_episode", "episode_id"),
        CheckConstraint(
            "media_asset_id IS NOT NULL OR (episode_id IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_cat_text_track_origin",
        ),
    )
    id = Column(String(100), primary_key=True)
    media_asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", ondelete="CASCADE", name="fk_text_track_asset"))
    episode_id = Column(ForeignKey("catalog_episodes.id", ondelete="CASCADE", name="fk_cat_track_episode"))
    source_id = Column(ForeignKey("catalog_sources.id", name="fk_cat_track_source"))
    language = Column(String(50), nullable=False)
    kind = Column(String(50), nullable=False)
    label = Column(String(255))
    format = Column(String(50), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    external_file_json = Column(LongText)
    cues_json = Column(LongText)
    provenance_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogScene(Base):
    __tablename__ = "catalog_scenes"
    __table_args__ = (
        CheckConstraint("start_ms >= 0 AND end_ms > start_ms", name="ck_catalog_scene_time_range"),
        Index("idx_cat_scene_ep", "episode_id"),
        Index("idx_cat_scene_asset", "media_asset_id"),
    )
    id = Column(String(100), primary_key=True)
    media_asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", name="fk_scene_asset", ondelete="CASCADE"))
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE", name="fk_scene_episode"), nullable=False)
    segment_id = Column(String(100), ForeignKey("catalog_segments.id", name="fk_scene_segment", ondelete="SET NULL"))
    start_ms = Column(BigInteger, nullable=False)
    end_ms = Column(BigInteger, nullable=False)
    title = Column(String(255))
    summary = Column(LongText)
    visual_description = Column(LongText)
    visual_tags_json = Column(LongText)
    sound_events_json = Column(LongText)
    transcript_cue_ids_json = Column(LongText)
    character_ids_json = Column(LongText)
    keywords_json = Column(LongText)
    themes_json = Column(LongText)
    attributes_json = Column(LongText)
    provenance_json = Column(LongText)
    record_json = Column(LongText)
    raw_json = Column(LongText)
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
    opt_lock_version = Column(BigInteger, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
    __table_args__ = (
        CheckConstraint("HEX(status) IN (HEX('PENDING'), HEX('BUILDING'), HEX('READY'), HEX('BLOCKED'), HEX('SYNC_FAILED'))", name="ck_catalog_snapshot_status"),
        Index("idx_cat_snap_status", "status"),
        Index("uq_cat_snap_version", "snapshot_version", unique=True),
    )
    id = Column(String(100), primary_key=True)
    snapshot_version = Column(BigInteger, nullable=False)
    content_hash = Column(String(100), nullable=False)
    total_items = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    retry_count = Column(Integer, default=0, server_default=text("0"))
    error_message = Column(LongText)
    created_at = Column(Timestamp, server_default=text("CURRENT_TIMESTAMP"), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(Timestamp)
    updated_at = Column(Timestamp, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

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
        CheckConstraint("position_ms >= 0", name="ck_watch_progress_position"),
        UniqueConstraint("user_id", "episode_id", name="uq_watch_progress_user_episode"),
        Index("idx_watch_progress_user_updated", "user_id", "updated_at"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE", name="fk_watch_progress_user"), nullable=False)
    episode_id = Column(String(100), ForeignKey("catalog_episodes.id", ondelete="CASCADE", name="fk_watch_progress_episode"), nullable=False)
    asset_id = Column(String(100), ForeignKey("catalog_media_assets.id", name="fk_watch_progress_asset", ondelete="CASCADE"), nullable=False)
    position_ms = Column(BigInteger, nullable=False)
    opt_lock_version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    updated_at = Column(Timestamp, nullable=False, server_default=CurrentTimestampOnUpdate(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
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
        payload = jwt.decode(token, _jwt_key(), algorithms=["HS256"], options={"require": ["sub", "iat", "exp"]})
        if payload.get("type") == "playback_grant" or payload.get("purpose") == "playback":
            return None
        subject = payload.get("sub")
        return subject if isinstance(subject, str) and 0 < len(subject) <= 50 else None
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
        payload = jwt.decode(token, _jwt_key(), algorithms=["HS256"], options={"require": ["sub", "iat", "exp"]})
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
    return URL.create("mysql+pymysql", username=user, password=password, host=host,
                      port=int(port), database=db_name, query={"charset": "utf8mb4"}).render_as_string(hide_password=False)


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


def _media_mime_type(content_type, relative_path):
    mime_type = mimetypes.guess_type(relative_path)[0]
    if mime_type and mime_type.startswith(f"{content_type}/"):
        return mime_type
    return "audio/mpeg" if content_type == "audio" else "video/mp4"


class DatabaseManager:
    def __init__(self, database_url: str | None = None, seed: bool = True):
        self.database_url = resolve_database_url(database_url)
        self.engine = None
        self.SessionLocal = None
        self._seed = seed
        self._initialized = False
        self._initialization_lock = threading.RLock()

    def ensure_initialized(self):
        with self._initialization_lock:
            if self._initialized:
                return
            try:
                if self.database_url.startswith("sqlite"):
                    database_path = make_url(self.database_url).database
                    if database_path and database_path != ":memory:" and not database_path.startswith("file:"):
                        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
                    self.engine = create_engine(self.database_url, pool_pre_ping=True,
                                                connect_args={"check_same_thread": False, "timeout": 10})
                    @event.listens_for(self.engine, "connect")
                    def _set_sqlite_pragma(dbapi_connection, connection_record):
                        cursor = dbapi_connection.cursor()
                        cursor.execute("PRAGMA foreign_keys=ON")
                        cursor.execute("PRAGMA synchronous=NORMAL")
                        cursor.close()
                else:
                    self.engine = create_engine(
                        self.database_url,
                        pool_pre_ping=True,
                        pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
                        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
                        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
                        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
                        connect_args={"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "3")),
                                      "read_timeout": int(os.getenv("DB_READ_TIMEOUT", "15")),
                                      "write_timeout": int(os.getenv("DB_WRITE_TIMEOUT", "15"))},
                    )
                from .catalog_schema import upgrade_catalog_schema

                upgrade_catalog_schema(self.engine)
                self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
                self.restore_media_metadata()
                self._restore_episode_asset_links()
                self._initialized = True
                if self._seed and os.getenv("APP_DEMO_MODE", "").lower() == "true":
                    self.seed_defaults()
            except Exception:
                if self.engine is not None:
                    self.engine.dispose()
                self.engine = self.SessionLocal = None
                self._initialized = False
                raise RuntimeError("Không thể kết nối hoặc khởi tạo cơ sở dữ liệu đã cấu hình.") from None

    def restore_media_metadata(self):
        with self.SessionLocal() as db:
            rows = db.query(CatalogMediaAsset, MediaAsset).join(MediaAsset, MediaAsset.id == CatalogMediaAsset.id)
            for asset, legacy in rows.filter(CatalogMediaAsset.raw_json.is_not(None)).yield_per(256):
                try:
                    raw = json.loads(asset.raw_json)
                except (TypeError, ValueError):
                    continue
                if isinstance(raw, dict) and raw.get("content_type") in ("audio", "video"):
                    asset.content_type = raw["content_type"]
                    legacy.mime_type = _media_mime_type(asset.content_type, asset.relative_path)
            db.commit()

    def _restore_episode_asset_links(self):
        malformed = missing = 0
        with self.SessionLocal() as db:
            _begin_catalog_write(db)
            assets = db.query(CatalogMediaAsset.id, CatalogMediaAsset.coverage_json).order_by(CatalogMediaAsset.id)
            assets = assets.with_for_update()
            previous_id = None
            while True:
                page = assets if previous_id is None else assets.filter(CatalogMediaAsset.id > previous_id)
                batch = page.limit(256).all()
                if not batch:
                    break
                expected = {}
                for asset_id, coverage_json in batch:
                    try:
                        coverage = json.loads(coverage_json) if coverage_json is not None else []
                    except (TypeError, ValueError):
                        coverage = None
                    malformed += not isinstance(coverage, list)
                    expected[asset_id] = _coverage_episode_ids(coverage)
                referenced = set().union(*expected.values())
                available = set()
                if referenced:
                    available.update(row.id for row in db.query(CatalogEpisode.id).filter(CatalogEpisode.id.in_(referenced)))
                missing += sum(len(ids - available) for ids in expected.values())
                _sync_episode_asset_links(db, {asset_id: ids & available for asset_id, ids in expected.items()})
                previous_id = batch[-1].id
            db.commit()
        if malformed or missing:
            logging.getLogger(__name__).warning(
                "Bỏ qua dữ liệu coverage cũ không thể liên kết (%d JSON lỗi, %d lượt tham chiếu thiếu tập).",
                malformed, missing,
            )

    def healthy(self):
        try:
            with self.session() as db:
                db.execute(text("SELECT 1"))
            return True
        except (SQLAlchemyError, RuntimeError):
            return False

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


def catalog_publication_status(record_json: str | None) -> str:
    try:
        status = str(json.loads(record_json or "{}").get("status", "")).lower()
    except (AttributeError, TypeError, ValueError):
        return "draft"
    if status == "ready" and "ready" in record_json.lower():
        return "ready"
    return "archived" if status == "archived" else "draft"


def is_published(record_json: str | None) -> bool:
    return bool(record_json and "ready" in record_json.lower()) and catalog_publication_status(record_json) == "ready"


@event.listens_for(CatalogEpisode.record_json, "set")
def _set_episode_publication_status(episode, record_json, _old, _initiator):
    episode.publication_status = catalog_publication_status(record_json)


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


CATALOG_DATE_PATTERN = r"[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
CATALOG_DATETIME_PATTERN = re.compile(
    CATALOG_DATE_PATTERN + r"[T ]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"([.][0-9]{1,6})?(Z|[+-]([01][0-9]|2[0-3]):[0-5][0-9])?"
)


def parse_catalog_date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(CATALOG_DATE_PATTERN, value):
        raise ValueError("Ngày phải có dạng YYYY-MM-DD.")
    return date.fromisoformat(value)


def parse_catalog_datetime(value):
    if value is None:
        return None
    if not isinstance(value, str) or not CATALOG_DATETIME_PATTERN.fullmatch(value):
        raise ValueError("Thời điểm phải có dạng ISO 8601.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    if parsed.year < 1000:
        raise ValueError("Thời điểm UTC nằm ngoài phạm vi DATETIME.")
    return parsed


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
        positions = set()
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
            if collection in ("seasons", "episodes"):
                check_id(item.get("series_id"), f"{path}.series_id")
                try:
                    parse_catalog_date(item.get("release_date") or (item.get("air_date") if collection == "episodes" else None))
                except ValueError as exc:
                    raise CatalogInputError(f"{path}.release_date", str(exc)) from exc
            if collection == "sources":
                try:
                    parse_catalog_datetime(item.get("retrieved_at"))
                except (OverflowError, ValueError) as exc:
                    raise CatalogInputError(f"{path}.retrieved_at", str(exc)) from exc
            if collection == "episodes" and item.get("season_id") is not None:
                check_id(item["season_id"], f"{path}.season_id")
            if collection == "segments":
                check_id(item.get("episode_id"), f"{path}.episode_id")
                position = item.get("position", 1)
                if type(position) is not int or not 1 <= position <= 2_147_483_647:
                    raise CatalogInputError(f"{path}.position", "Vị trí phân đoạn phải là số nguyên dương.")
                key = (item["episode_id"], position)
                if key in positions:
                    raise CatalogInputError(f"{path}.position", "Vị trí phân đoạn phải duy nhất trong tập.")
                positions.add(key)
                start, end = item.get("episode_start_ms"), item.get("episode_end_ms")
                if (start is not None or end is not None) and (
                    type(start) is not int or type(end) is not int or not 0 <= start < end
                ):
                    raise CatalogInputError(path, "Phân đoạn cần đủ hai mốc và mốc kết thúc phải sau mốc bắt đầu.")
            if collection == "text_tracks":
                if item.get("media_asset_id") is None:
                    check_id(item.get("episode_id"), f"{path}.episode_id")
                    check_id(item.get("source_id"), f"{path}.source_id")
                descriptor = item.get("external_file")
                if descriptor is not None:
                    file_path = f"{path}.external_file"
                    if not isinstance(descriptor, dict) or set(descriptor) != {"storage_key", "relative_path", "sha256"}:
                        raise CatalogInputError(file_path, "Thiếu thông tin lưu tệp phụ đề.")
                    storage_key = descriptor["storage_key"]
                    if not isinstance(storage_key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", storage_key):
                        raise CatalogInputError(f"{file_path}.storage_key", "Mã nơi lưu tệp phụ đề không hợp lệ.")
                    if not is_relative_media_path(descriptor["relative_path"]):
                        raise CatalogInputError(f"{file_path}.relative_path", "Đường dẫn tệp phụ đề phải là đường dẫn tương đối.")
                    digest = descriptor["sha256"]
                    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
                        raise CatalogInputError(f"{file_path}.sha256", "Mã SHA-256 của tệp phụ đề không hợp lệ.")
            if collection == "media_assets":
                coverage = item.get("coverage")
                if coverage is not None:
                    if not isinstance(coverage, list):
                        raise CatalogInputError(f"{path}.coverage", "Phạm vi tệp phải là một danh sách.")
                    for coverage_index, part in enumerate(coverage):
                        part_path = f"{path}.coverage[{coverage_index}]"
                        if not isinstance(part, dict):
                            raise CatalogInputError(part_path, "Phạm vi tệp không hợp lệ.")
                        check_id(part.get("episode_id"), f"{part_path}.episode_id")
                if item.get("content_type", "video") not in ("audio", "video"):
                    raise CatalogInputError(f"{path}.content_type", "Loại tệp phải là video hoặc audio.")
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


def _validate_catalog_seasons(db, data, stored_seasons, lock):
    seasons = data.get("seasons") or []
    parents = {season["id"]: season["series_id"] for season in seasons}
    moved = {
        season["id"]: index for index, season in enumerate(seasons)
        if season["id"] in stored_seasons and stored_seasons[season["id"]].series_id != season["series_id"]
    }
    if moved:
        query = (
            db.query(CatalogSeason.id)
            .join(CatalogEpisode, CatalogEpisode.season_id == CatalogSeason.id)
            .filter(CatalogSeason.id.in_(moved))
        )
        if lock:
            query = query.with_for_update()
        used = query.first()
        if used:
            raise CatalogInputError(f"seasons[{moved[used.id]}].series_id",
                                    "Không thể chuyển mùa sang bộ khác khi mùa còn tập.")

    episodes = data.get("episodes") or []
    external = {episode["season_id"] for episode in episodes if episode.get("season_id") is not None} - parents.keys()
    if external:
        query = db.query(CatalogSeason.id, CatalogSeason.series_id).filter(CatalogSeason.id.in_(external))
        if lock:
            query = query.with_for_update()
        parents.update(query.all())
    for index, episode in enumerate(episodes):
        season_id = episode.get("season_id")
        if season_id is not None and parents.get(season_id) != episode["series_id"]:
            raise CatalogInputError(f"episodes[{index}].season_id",
                                    "Mùa phải tồn tại và thuộc đúng bộ của tập phim.")


def _validate_catalog_asset_episodes(db, data, lock):
    paths = {}
    for asset_index, asset in enumerate(data.get("media_assets") or []):
        for part_index, part in enumerate(asset.get("coverage") or []):
            paths.setdefault(part["episode_id"], f"media_assets[{asset_index}].coverage[{part_index}].episode_id")
    external = paths.keys() - {episode["id"] for episode in (data.get("episodes") or [])}
    if external:
        query = db.query(CatalogEpisode.id).filter(CatalogEpisode.id.in_(external))
        if lock:
            query = query.with_for_update()
        missing = external - {row.id for row in query}
        if missing:
            raise CatalogInputError(paths[min(missing)], "Tập tham chiếu trong phạm vi tệp chưa tồn tại.")


def _validate_catalog_references(db, data, lock):
    rules = (
        ("series", "genre_ids", "genres", True),
        ("series", "character_ids", "characters", True),
        ("characters", "series_ids", "series", True),
        ("media_assets", "related_asset_id", "media_assets", False),
        ("scenes", "media_asset_id", "media_assets", False),
        ("scenes", "segment_id", "segments", False),
    )
    for collection, field, target, multiple in rules:
        paths = {}
        for index, item in enumerate(data.get(collection) or []):
            value = item.get(field)
            if value is None:
                continue
            path = f"{collection}[{index}].{field}"
            reference_ids = value if multiple else [value]
            if not isinstance(reference_ids, list) or any(not isinstance(ref, str) or not ref for ref in reference_ids):
                raise CatalogInputError(path, "Mã định danh tham chiếu không hợp lệ.")
            for reference_id in reference_ids:
                paths.setdefault(reference_id, path)
        if not paths:
            continue
        external = paths.keys() - {item["id"] for item in data.get(target) or []}
        if external:
            model = CATALOG_COLLECTIONS[target]
            query = db.query(model.id).filter(model.id.in_(external))
            if lock:
                query = query.with_for_update()
            missing = external - {row.id for row in query}
            if missing:
                raise CatalogInputError(paths[min(missing)], "Bản ghi tham chiếu chưa tồn tại.")


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
    _validate_catalog_seasons(db, data, stored.get("seasons", {}), lock)
    _validate_catalog_asset_episodes(db, data, lock)
    _validate_catalog_references(db, data, lock)
    return counts, stored


def _coverage_episode_ids(coverage):
    if not isinstance(coverage, list):
        return set()
    return {
        part["episode_id"] for part in coverage
        if isinstance(part, dict) and isinstance(part.get("episode_id"), str) and part["episode_id"]
    }


def _sync_episode_asset_links(db, expected):
    actual = {asset_id: set() for asset_id in expected}
    query = db.query(CatalogEpisodeAsset.media_asset_id, CatalogEpisodeAsset.episode_id)
    for asset_id, episode_id in query.filter(CatalogEpisodeAsset.media_asset_id.in_(expected)):
        if asset_id in actual:
            actual[asset_id].add(episode_id)
    changed = {asset_id: ids for asset_id, ids in expected.items() if ids != actual[asset_id]}
    if not changed:
        return
    db.execute(delete(CatalogEpisodeAsset).where(CatalogEpisodeAsset.media_asset_id.in_(changed)))
    links = [
        {"media_asset_id": asset_id, "episode_id": episode_id}
        for asset_id, ids in changed.items() for episode_id in sorted(ids)
    ]
    if links:
        db.execute(insert(CatalogEpisodeAsset), links)


def _begin_catalog_write(db):
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def _replace_catalog_links(db, items, model, owner_column, field, reference_column):
    if not items:
        return
    table = model.__table__
    db.execute(delete(table).where(table.c[owner_column].in_([item["id"] for item in items])))
    links = [
        {owner_column: item["id"], reference_column: reference_id}
        for item in items
        for reference_id in dict.fromkeys(item.get(field) or [])
    ]
    if links:
        db.execute(insert(table), links)


def _replace_episode_taxonomy(db, episodes):
    _replace_catalog_links(db, episodes, CatalogEpisodeCharacter, "episode_id", "character_ids", "character_id")
    _replace_catalog_links(db, episodes, CatalogEpisodeGenre, "episode_id", "genre_ids", "genre_id")


def _replace_movie_genres(connection, movies):
    if not movies:
        return
    table = MovieGenre.__table__
    terms = MovieGenreTerm.__table__
    links = [
        {"movie_id": movie_id, "genre_name": name}
        for movie_id, genres in movies
        for name in sorted({value.strip().lower() for value in (genres or "").split(",") if value.strip()})
    ]
    connection.execute(delete(table).where(table.c.movie_id.in_([movie_id for movie_id, _ in movies])))
    if links:
        names = [{"name": name} for name in sorted({link["genre_name"] for link in links})]
        if connection.dialect.name == "mysql":
            insert_terms = mysql.insert(terms)
            connection.execute(insert_terms.on_duplicate_key_update(name=terms.c.name), names)
        else:
            connection.execute(sqlite.insert(terms).on_conflict_do_nothing(), names)
        connection.execute(insert(table), links)


@event.listens_for(Session, "after_flush")
def _sync_changed_movie_genres(session, _flush_context):
    movies = [
        (movie.id, movie.genres)
        for movie in session.new.union(session.dirty)
        if isinstance(movie, Movie) and inspect(movie).attrs.genres.history.has_changes()
    ]
    for offset in range(0, len(movies), 500):
        _replace_movie_genres(session.connection(), movies[offset:offset + 500])


def import_catalog_package(db, data: dict) -> dict:
    pkg_id, revision = validate_catalog_input(data)
    pkg = data["package"]
    version = str(pkg.get("version") or "1.0.0")
    default_lang = str(pkg.get("default_language") or "vi")
    import_mode = str(pkg.get("import_mode") or "upsert")
    ref_scope = str(pkg.get("reference_scope") or "self_contained")
    content_hash = compute_sha256(data)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    _begin_catalog_write(db)
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
            entity.retrieved_at = parse_catalog_datetime(src.get("retrieved_at"))
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
            else:
                m = existing_movies[sid]
                m.title = entity.title
                m.release_year = entity.release_year_start or m.release_year
                m.description = entity.synopsis or ""
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
            kind = sea.get("kind", "regular")
            entity.kind = "regular" if kind == "standard" else kind
            entity.release_date = parse_catalog_date(sea.get("release_date") or None)
            entity.artworks_json = json.dumps(sea.get("artwork") or sea.get("artworks"), ensure_ascii=False) if (sea.get("artwork") or sea.get("artworks")) is not None else None
            entity.record_json = json.dumps(sea.get("record") or {"status": "ready", "revision": revision}, ensure_ascii=False)
            entity.raw_json = json.dumps(sea, ensure_ascii=False)
            entity.revision = int((sea.get("record") or {}).get("revision") or revision)
            entity.updated_at = now
        db.flush()

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
            kind = ep.get("kind") or ep.get("episode_type") or "regular"
            entity.kind = "regular" if kind in ("standard", "episode") else kind
            entity.release_date = parse_catalog_date(ep.get("release_date") or ep.get("air_date"))
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
            else:
                m = existing_movies[ep_id]
                m.title = entity.title
                m.runtime = f"{int((entity.duration_ms or 1200000) / 60000)}m"
                m.description = entity.synopsis or ""
    db.flush()

    segments = data.get("segments") or []
    if segments:
        existing = stored["segments"]
        moving = [
            existing[seg["id"]] for seg in segments if seg["id"] in existing
            and (existing[seg["id"]].episode_id, existing[seg["id"]].position)
            != (seg["episode_id"], seg.get("position", 1))
        ]
        if moving:
            occupied = {entity.episode_id: set() for entity in moving}
            rows = db.query(CatalogSegment.episode_id, CatalogSegment.position).filter(
                CatalogSegment.episode_id.in_(occupied), CatalogSegment.position < 0,
            )
            for episode_id, position in rows:
                occupied[episode_id].add(position)
            temporary_positions = dict.fromkeys(occupied, -1)
            for entity in moving:
                episode_id = entity.episode_id
                position = temporary_positions[episode_id]
                while position in occupied[episode_id]:
                    position -= 1
                entity.position = position
                temporary_positions[episode_id] = position - 1
            db.flush()
        for seg in segments:
            seg_id = seg["id"]
            entity = existing.get(seg_id)
            if not entity:
                entity = CatalogSegment(id=seg_id)
                db.add(entity)
            entity.episode_id = seg["episode_id"]
            entity.position = seg.get("position", 1)
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

    db.flush()
    _replace_episode_taxonomy(db, episodes)
    _replace_catalog_links(db, series_list, CatalogSeriesGenre, "series_id", "genre_ids", "genre_id")
    _replace_catalog_links(db, series_list, CatalogSeriesCharacter, "series_id", "character_ids", "character_id")
    _replace_catalog_links(db, characters, CatalogCharacterSeries, "character_id", "series_ids", "series_id")

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
                existing_cat_assets[mid] = entity
            entity.content_type = ma.get("content_type") or "video"
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
            legacy.mime_type = _media_mime_type(entity.content_type, rel_path)
            legacy.byte_length = size_bytes
            legacy.duration_seconds = (entity.duration_ms / 1000.0) if entity.duration_ms else None
            legacy.is_public = entity.access_policy.lower() == "public"
            legacy.is_available = entity.enabled
    db.flush()
    if media_assets:
        for asset in media_assets:
            existing_cat_assets[asset["id"]].related_asset_id = asset.get("related_asset_id")
        _sync_episode_asset_links(db, {
            asset["id"]: _coverage_episode_ids(asset.get("coverage")) for asset in media_assets
        })

    tracks = data.get("text_tracks") or []
    if tracks:
        existing = stored["text_tracks"]
        for tt in tracks:
            tid = tt["id"]
            entity = existing.get(tid)
            if not entity:
                entity = CatalogTextTrack(id=tid)
                db.add(entity)
            entity.media_asset_id = tt.get("media_asset_id")
            entity.episode_id = tt.get("episode_id")
            entity.source_id = tt.get("source_id")
            entity.kind = tt.get("kind", "subtitles")
            entity.language = tt.get("language", "vi")
            entity.label = tt.get("label")
            entity.format = tt.get("format", "vtt")
            entity.external_file_json = json.dumps(tt.get("external_file"), ensure_ascii=False) if tt.get("external_file") is not None else None
            entity.cues_json = json.dumps(tt.get("cues"), ensure_ascii=False) if tt.get("cues") is not None else None
            entity.provenance_json = json.dumps(tt.get("provenance"), ensure_ascii=False) if tt.get("provenance") is not None else None
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
        total_items=sum(counts.values()), status="PENDING", retry_count=0,
        created_at=now, updated_at=now,
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
        "indexStatus": "PENDING",
        "message": "Đã nhập gói danh mục.",
    }


def export_eligible_catalog(db, include_draft: bool = False, include_private: bool = False) -> dict:
    def _filter_rows(model):
        check_access = model is CatalogMediaAsset and not include_private
        check_record = model is not CatalogEpisode and not include_draft
        columns = [model.raw_json]
        if check_record:
            columns.append(model.record_json)
        if check_access:
            columns.append(model.access_policy)
        rows = db.query(*columns).filter(model.raw_json.is_not(None))
        if check_record:
            rows = rows.filter(func.lower(model.record_json).contains("ready"))
        if model is CatalogEpisode and not include_draft:
            rows = rows.filter(model.publication_status == "ready")
        if model is CatalogTextTrack:
            if not include_draft:
                ready_episodes = select(CatalogEpisode.id).where(CatalogEpisode.publication_status == "ready")
                rows = rows.filter(or_(model.episode_id.is_(None), model.episode_id.in_(ready_episodes)))
            if not include_private:
                public_assets = select(CatalogMediaAsset.id).where(CatalogMediaAsset.access_policy == "public")
                rows = rows.filter(or_(model.media_asset_id.is_(None), model.media_asset_id.in_(public_assets)))
        out = []
        for row in rows:
            if not row.raw_json:
                continue
            if check_record and not is_published(row.record_json):
                continue
            if check_access and str(row.access_policy).lower() != "public":
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
    catalog = {
        "schema_version": "dippie.catalog.v1",
        "package": pkg_meta,
        **{collection: _filter_rows(model) for collection, model in CATALOG_COLLECTIONS.items()},
    }
    if not include_draft:
        source_ids = {source.get("id") for source in catalog["sources"]}
        catalog["text_tracks"] = [
            track for track in catalog["text_tracks"]
            if track.get("source_id") is None or track["source_id"] in source_ids
        ]
    return catalog

