from schemas import RecommendResponse
from services.database import FavoriteItem, MovieRating, WatchProgress


def profile_signals(db, user_id, snapshot, requested):
    liked = set(requested)
    seen = set(liked)
    if user_id is None:
        return liked, seen
    favorites = db.query(FavoriteItem.movie_id).filter(FavoriteItem.user_id == user_id)
    ratings = db.query(MovieRating.movie_id).filter(MovieRating.user_id == user_id)
    progress = db.query(WatchProgress.episode_id).filter(
        WatchProgress.user_id == user_id, WatchProgress.position_ms > 0)
    liked.update(item_id for item_id, in favorites.order_by(
        FavoriteItem.added_at.desc(), FavoriteItem.id.desc()).limit(100))
    liked.update(item_id for item_id, in ratings.filter(MovieRating.rating >= 8).order_by(
        MovieRating.updated_at.desc(), MovieRating.id.desc()).limit(100))
    liked.update(item_id for item_id, in progress.order_by(
        WatchProgress.updated_at.desc(), WatchProgress.id.desc()).limit(100))
    seen.update(liked)
    ids = {value for item in snapshot.get_flattened_catalog()
           for value in (item.get('id'), item.get('series_id')) if value}
    seen.update(item_id for item_id, in favorites.union_all(ratings, progress).yield_per(256) if item_id in ids)
    return liked, seen


def affinity_score(item, preferred, themes, chars, series):
    genres = {str(value).casefold() for value in item.get('genres') or []}
    item_themes = {str(value).casefold() for value in (item.get('themes') or []) + (item.get('keywords') or [])}
    item_chars = {str(value).casefold() for value in item.get('characters') or []}
    score = float(item.get('rating') or 0.0) * 0.1
    score += 2.0 * len(genres & preferred) / max(1, len(preferred))
    score += 1.5 * len(item_themes & themes) / max(1, len(themes))
    score += 1.2 * len(item_chars & chars) / max(1, len(chars))
    score += 0.8 if item.get('series_id') in series else 0
    return round(score, 4)


def eligible_items(snapshot):
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}

    def rows(key):
        value = payload.get(key)
        return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []

    seasons = {row['id']: row for row in rows('seasons') if isinstance(row.get('id'), str)}
    episodes = {row['id']: row for row in rows('episodes') if isinstance(row.get('id'), str)}
    coverage = {}
    for asset in rows('media_assets'):
        entries = asset.get('coverage')
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get('episode_id'), str):
                coverage.setdefault(entry['episode_id'], []).append((asset, entry))

    def published(record):
        return not isinstance(record, dict) or record.get('status') not in ('draft', 'archived')

    def public_video(asset, entry):
        return (asset.get('enabled', True) is True and str(asset.get('access_policy', 'public')).lower() == 'public'
                and str(asset.get('content_type', 'video')).lower() == 'video'
                and str(asset.get('role', '')).lower() not in ('dub', 'audio_description')
                and str(entry.get('scope', '')).lower() == 'full_episode' and published(asset.get('record')))

    result = []
    for item in snapshot.get_flattened_catalog():
        if item.get('item_type') not in ('episode', 'movie'):
            continue
        season = seasons.get(item.get('season_id'), {})
        if not published(season.get('record')):
            continue
        associated = coverage.get(item['id'], [])
        declared = episodes.get(item['id'], {}).get('primary_media_asset_id')
        if (associated or declared) and not any(public_video(asset, entry) for asset, entry in associated):
            continue
        result.append({**item, 'primary_media_asset_id': None, 'media_asset_id': None})
    return result


def recommend_items(snapshot, search, request, liked, seen):
    all_items = eligible_items(snapshot)
    liked_items = [item for item in all_items if item['id'] in liked or item.get('series_id') in liked]
    explicit = {genre.casefold() for genre in request.genres or []}
    preferred = explicit | {str(genre).casefold() for item in liked_items for genre in item.get('genres') or []}
    themes = {str(value).casefold() for item in liked_items for value in (item.get('themes') or []) + (item.get('keywords') or [])}
    chars = {str(value).casefold() for item in liked_items for value in item.get('characters') or []}
    series = {item['series_id'] for item in liked_items if item.get('series_id')}
    candidates = {item['id']: item for item in all_items if item['id'] not in seen and item.get('series_id') not in seen
                  and (not explicit or explicit.intersection(str(genre).casefold() for genre in item.get('genres') or []))}
    if request.mood:
        matches = search.search(snapshot, request.mood, limit=100, constraints={'include_genres': list(explicit)})
        results = []
        for match in matches:
            item = candidates.pop(match.get('id'), None)
            if item:
                results.append({**match, 'primary_media_asset_id': None, 'media_asset_id': None})
            if len(results) == request.limit:
                break
        return RecommendResponse(recommendedMovies=results, reasoning='Dựa trên tâm trạng bạn chọn.')
    scored = [(affinity_score(item, preferred, themes, chars, series), float(item.get('rating') or 0.0), item)
              for item in candidates.values()]
    scored.sort(key=lambda entry: (-entry[0], -entry[1], entry[2]['id']))
    results = [{**item, 'year': item.get('year') or item.get('release_year') or 0,
                'episodeId': item.get('episode_id') or item['id'], 'startMs': item.get('start_ms'),
                'score': score, 'calibratedScore': None,
                'evidence': [{'documentId': item['id'], 'text': item.get('description', ''),
                              'startMs': item.get('start_ms'), 'endMs': item.get('end_ms'),
                              'itemType': item.get('item_type', 'episode')}]}
               for score, _, item in scored[:request.limit]]
    reasoning = ('Phim tương đồng với nội dung bạn đã thích hoặc đã xem.'
                 if liked_items else 'Dựa trên thể loại bạn chọn.' if explicit else 'Gợi ý từ kho phim.')
    return RecommendResponse(recommendedMovies=results, reasoning=reasoning)
