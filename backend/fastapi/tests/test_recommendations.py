from fastapi.testclient import TestClient

from main import create_app
from services.database import CatalogEpisode, CatalogSeries, FavoriteItem, MovieRating, User, WatchProgress, create_jwt_token


def test_recommend_personalizes_only_from_authenticated_account(tmp_path):
    app = create_app(sync_secret='test-token', sync_path=tmp_path / 'state.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False, database_url=f'sqlite:///{tmp_path / "test.db"}')
    payload = {'schema_version': 'dippie.catalog.v1', 'series': [{'id': 's', 'title': 'Series'}],
               'episodes': [{'id': name, 'series_id': 's', 'number': n, 'title': name, 'themes': [theme]}
                            for n, (name, theme) in enumerate([('liked', 'space'), ('match', 'space'),
                                                               ('watched', 'space'), ('other', 'forest')], 1)],
               'seasons': [], 'segments': [], 'scenes': [], 'media_assets': [], 'text_tracks': []}
    with TestClient(app) as client:
        assert client.post('/api/index/sync', headers={'X-Service-Token': 'test-token'},
                           json={'generation': 1, 'catalog': payload}).status_code == 200
        with app.state.runtime.db.session() as db:
            user = User(username='alice', email='alice@example.com', password='x')
            other = User(username='bob', email='bob@example.com', password='x')
            db.add_all([user, other, CatalogSeries(id='s', title='Series')])
            db.flush()
            db.add(CatalogEpisode(id='watched', series_id='s', title='watched', kind='episode'))
            db.add_all([FavoriteItem(user_id=user.id, movie_id='liked', movie_title='liked'),
                        MovieRating(user_id=other.id, movie_id='other', rating=10),
                        WatchProgress(user_id=user.id, episode_id='watched', asset_id='asset', position_ms=1000)])
            db.commit()
        headers = {'Authorization': f'Bearer {create_jwt_token("alice")}'}
        response = client.post('/api/recommend', headers=headers, json={'limit': 10})
        assert response.status_code == 200
        ids = [item['id'] for item in response.json()['recommendedMovies']]
        assert ids == ['match', 'other']
        assert 'tương đồng' in response.json()['reasoning']
        guest = client.post('/v1/recommend', json={'limit': 10, 'userId': user.id}).json()
        assert {'liked', 'watched', 'other'} <= {item['id'] for item in guest['recommendedMovies']}


def test_recommend_rejects_unbounded_signals(tmp_path):
    app = create_app(sync_path=tmp_path / 'state.json', cache_dir=tmp_path / 'cache', model_mode='light', load_default=False)
    with TestClient(app) as client:
        assert client.post('/api/recommend', json={'likedMovieIds': ['x'] * 101}).status_code == 422
        assert client.post('/api/recommend', json={'mood': 'x' * 501}).status_code == 422


def test_recommend_filters_draft_seasons_and_private_assets(tmp_path):
    app = create_app(sync_secret='test-token', sync_path=tmp_path / 'state.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False, database_url=f'sqlite:///{tmp_path / "eligibility.db"}')
    payload = {'schema_version': 'dippie.catalog.v1', 'series': [{'id': 's', 'title': 'Series'}],
               'seasons': [{'id': 'draft', 'series_id': 's', 'record': {'status': 'draft'}}],
               'episodes': [{'id': 'ok', 'series_id': 's', 'title': 'Visible'},
                            {'id': 'draft_ep', 'series_id': 's', 'season_id': 'draft', 'title': 'Draft'},
                            {'id': 'private', 'series_id': 's', 'title': 'Private', 'primary_media_asset_id': 'private_asset'},
                            {'id': 'covered', 'series_id': 's', 'title': 'Private coverage'}],
               'media_assets': [{'id': 'private_asset', 'access_policy': 'private', 'coverage': [{'episode_id': 'covered'}]}],
               'segments': [], 'scenes': [], 'text_tracks': []}
    with TestClient(app) as client:
        assert client.post('/api/index/sync', headers={'X-Service-Token': 'test-token'},
                           json={'generation': 1, 'catalog': payload}).status_code == 200
        response = client.post('/api/recommend', json={'limit': 10})
        assert [item['id'] for item in response.json()['recommendedMovies']] == ['ok']


def test_old_viewed_items_are_excluded_even_when_affinity_history_is_bounded(tmp_path):
    app = create_app(sync_secret='test-token', sync_path=tmp_path / 'state.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False, database_url=f'sqlite:///{tmp_path / "history.db"}')
    payload = {'schema_version': 'dippie.catalog.v1', 'series': [{'id': 's', 'title': 'Series'}],
               'episodes': [{'id': 'old', 'series_id': 's', 'title': 'Seen'}, {'id': 'new', 'series_id': 's', 'title': 'New'}]}
    with TestClient(app) as client:
        assert client.post('/api/index/sync', headers={'X-Service-Token': 'test-token'},
                           json={'generation': 1, 'catalog': payload}).status_code == 200
        with app.state.runtime.db.session() as db:
            user = User(username='long_history', email='history@example.com', password='x')
            db.add(user)
            db.flush()
            db.add(MovieRating(user_id=user.id, movie_id='old', rating=5))
            db.flush()
            db.add_all([MovieRating(user_id=user.id, movie_id=f'other-{n}', rating=5) for n in range(101)])
            db.commit()
        response = client.post('/api/recommend', headers={'Authorization': f'Bearer {create_jwt_token("long_history")}'}, json={})
        assert [item['id'] for item in response.json()['recommendedMovies']] == ['new']


def test_recommend_requires_public_video_and_never_returns_stale_asset(tmp_path):
    app = create_app(sync_secret='test-token', sync_path=tmp_path / 'state.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False, database_url=f'sqlite:///{tmp_path / "assets.db"}')
    payload = {'schema_version': 'dippie.catalog.v1', 'series': [{'id': 's', 'title': 'Series'}],
               'episodes': [{'id': 'blocked', 'series_id': 's', 'title': 'Blocked', 'primary_media_asset_id': 'private'},
                            {'id': 'allowed', 'series_id': 's', 'title': 'Allowed', 'primary_media_asset_id': 'private'},
                            {'id': 'missing', 'series_id': 's', 'title': 'Missing', 'primary_media_asset_id': 'missing_asset'},
                            {'id': 'metadata', 'series_id': 's', 'title': 'Metadata'}],
               'media_assets': [
                   {'id': 'private', 'content_type': 'video', 'access_policy': 'private',
                    'coverage': [{'episode_id': 'blocked', 'scope': 'full_episode'}, {'episode_id': 'allowed', 'scope': 'full_episode'}]},
                   {'id': 'audio', 'content_type': 'audio', 'coverage': [{'episode_id': 'blocked', 'scope': 'full_episode'}]},
                   {'id': 'public_video', 'content_type': 'video', 'coverage': [{'episode_id': 'allowed', 'scope': 'full_episode'}]},
               ]}
    with TestClient(app) as client:
        assert client.post('/api/index/sync', headers={'X-Service-Token': 'test-token'},
                           json={'generation': 1, 'catalog': payload}).status_code == 200
        response = client.post('/api/recommend', json={'limit': 10})
        movies = {item['id']: item for item in response.json()['recommendedMovies']}
        assert set(movies) == {'allowed', 'metadata'}
        assert movies['allowed']['primary_media_asset_id'] in (None, 'public_video')
        response = client.post('/api/recommend', json={'mood': 'Allowed', 'limit': 10})
        assert response.status_code == 200
        assert any(item['id'] == 'allowed' for item in response.json()['recommendedMovies'])
        assert all(item['primary_media_asset_id'] in (None, 'public_video') for item in response.json()['recommendedMovies'])


def test_eligibility_handles_malformed_optional_coverage():
    from types import SimpleNamespace
    from services.recommendations import eligible_items

    snapshot = SimpleNamespace(payload={'seasons': None, 'episodes': [None],
                                        'media_assets': [None, {'id': 'asset', 'coverage': [None, 'bad']} ]},
                               get_flattened_catalog=lambda: [{'id': 'episode', 'item_type': 'episode'}])
    assert [item['id'] for item in eligible_items(snapshot)] == ['episode']
