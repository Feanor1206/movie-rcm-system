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


def tags(item, *fields):
    return {str(value).casefold() for field in fields for value in item.get(field) or []}


def affinity_score(item, preferred, themes, chars, series):
    score = float(item.get('rating') or 0.0) * 0.1
    score += 2.0 * len(tags(item, 'genres') & preferred) / max(1, len(preferred))
    score += 1.5 * len(tags(item, 'themes', 'keywords') & themes) / max(1, len(themes))
    score += 1.2 * len(tags(item, 'characters') & chars) / max(1, len(chars))
    score += 0.8 if item.get('series_id') in series else 0
    return round(score, 4)


def eligible_items(snapshot):
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}

    def rows(key):
        value = payload.get(key)
        return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []

    def published(record):
        return not isinstance(record, dict) or record.get('status') not in ('draft', 'archived')

    hidden_seasons = {row['id'] for row in rows('seasons')
                      if isinstance(row.get('id'), str) and not published(row.get('record'))}
    declared = {row['id'] for row in rows('episodes')
                if isinstance(row.get('id'), str) and row.get('primary_media_asset_id')}
    playable = set()
    for asset in rows('media_assets'):
        public_video = (
            asset.get('enabled', True) is True
            and str(asset.get('access_policy', 'public')).lower() == 'public'
            and str(asset.get('content_type', 'video')).lower() == 'video'
            and str(asset.get('role', '')).lower() not in ('dub', 'audio_description')
            and published(asset.get('record'))
        )
        coverage = asset.get('coverage')
        for entry in coverage if isinstance(coverage, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get('episode_id'), str):
                declared.add(entry['episode_id'])
                if public_video and str(entry.get('scope', '')).lower() == 'full_episode':
                    playable.add(entry['episode_id'])

    return [
        {**item, 'primary_media_asset_id': None, 'media_asset_id': None}
        for item in snapshot.get_flattened_catalog()
        if item.get('item_type') in ('episode', 'movie') and item.get('season_id') not in hidden_seasons
        and (item['id'] not in declared or item['id'] in playable)
    ]


def recommend_items(snapshot, search, request, liked, seen):
    all_items = eligible_items(snapshot)
    liked_items = [item for item in all_items if item['id'] in liked or item.get('series_id') in liked]
    explicit = {genre.casefold() for genre in request.genres or []}
    preferred = explicit | {genre for item in liked_items for genre in tags(item, 'genres')}
    themes = {theme for item in liked_items for theme in tags(item, 'themes', 'keywords')}
    chars = {character for item in liked_items for character in tags(item, 'characters')}
    series = {item['series_id'] for item in liked_items if item.get('series_id')}
    candidates = {item['id']: item for item in all_items if item['id'] not in seen and item.get('series_id') not in seen
                  and (not explicit or explicit & tags(item, 'genres'))}
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
