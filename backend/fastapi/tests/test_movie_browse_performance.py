from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import event

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend' / 'fastapi'))

from main import create_app
from services.database import CatalogEpisode, CatalogSeason, CatalogSeries, Movie


def test_browse_numeric_sort_loads_only_page_and_keeps_binary_ties(tmp_path):
    app = create_app(sync_path=tmp_path / 'sync.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False,
                     database_url=f"sqlite:///{(tmp_path / 'browse.db').as_posix()}")
    with TestClient(app) as client:
        with app.state.runtime.db.session() as db:
            db.query(Movie).delete()
            db.add_all([Movie(id=movie_id, title=movie_id, release_year=2020, rating=8.0)
                        for movie_id in ['a', 'B', 'é', 'Z']])
            db.commit()
        loaded = []
        def record_load(movie, context):
            loaded.append(movie.id)
        event.listen(Movie, 'load', record_load)
        try:
            result = client.get('/api/movies/browse?sort=rating&direction=desc&page=1&size=2').json()['data']
            empty = client.get('/api/movies/browse?sort=year&page=999999999999999999999&size=2').json()['data']
        finally:
            event.remove(Movie, 'load', record_load)
            app.state.runtime.db.engine.dispose()
    assert [movie['id'] for movie in result['items']] == ['a', 'é']
    assert (result['totalElements'], result['totalPages'], result['hasNext'], result['hasPrevious']) == (4, 2, False, True)
    assert len(loaded) == 2
    assert empty['items'] == []
    assert empty['totalElements'] == 4


def test_filtered_browse_loads_only_returned_movie_rows(tmp_path):
    app = create_app(sync_path=tmp_path / 'sync.json', cache_dir=tmp_path / 'cache',
                     model_mode='light', load_default=False,
                     database_url=f"sqlite:///{(tmp_path / 'browse.db').as_posix()}")
    with TestClient(app) as client:
        with app.state.runtime.db.session() as db:
            db.query(Movie).delete()
            db.add_all([
                Movie(id='a', title='é', description='Một câu chuyện về bờ biển', genres=' animation , Family ', release_year=2020, rating=8),
                Movie(id='B', title='Z', genres='Animation, Comedy', release_year=2020, rating=8),
                Movie(id='é', title='a', description='Một tuần ở BỜ BIỂN', genres='Animation, Family', release_year=2020, rating=8),
                Movie(id='Z', title='Film', genres='Animàtion, Family', release_year=2020, rating=10),
                Movie(id='other', title='Film 2', genres='AnimationExtra, Family', release_year=2020, rating=10),
                Movie(id='private-series', title='Nháp bộ', genres='Animation, Family', release_year=2020, rating=10),
                Movie(id='private-season-ep', title='Nháp mùa', genres='Animation, Family', release_year=2020, rating=10),
                Movie(id='private-ep', title='Nháp tập', genres='Animation, Family', release_year=2020, rating=10),
            ])
            db.add_all([
                CatalogSeries(id='public-series', title='Bộ đã xuất bản', record_json='{"status":"ready"}'),
                CatalogSeries(id='private-series', title='Bộ chưa xuất bản', record_json='{}'),
            ])
            db.flush()
            db.add(CatalogSeason(id='private-season', series_id='public-series', title='Mùa nháp', record_json='{}'))
            db.flush()
            db.add_all([
                CatalogEpisode(id='private-season-ep', title='Tập thuộc mùa nháp', series_id='public-series',
                               season_id='private-season', record_json='{"status":"ready"}', kind='regular'),
                CatalogEpisode(id='private-ep', title='Tập nháp', series_id='public-series',
                               record_json='{}', kind='regular'),
            ])
            db.commit()
        loaded = []

        def record_load(movie, context):
            loaded.append(movie.id)

        event.listen(Movie, 'load', record_load)
        try:
            cases = [
                ({'animationOnly': True, 'page': 1, 'size': 1}, 'a', 3),
                ({'animationOnly': True, 'genres': 'family, animation', 'sort': 'title', 'direction': 'asc', 'size': 1}, 'é', 2),
                ({'animationOnly': True, 'q': 'bờ biển', 'size': 1}, 'a', 2),
                ({'animationOnly': True, 'q': 'bo bien', 'size': 1}, None, 0),
            ]
            for params, expected_id, total in cases:
                loaded.clear()
                response = client.get('/api/movies/browse', params=params)
                assert response.status_code == 200
                result = response.json()['data']
                assert result['totalElements'] == total
                assert [movie['id'] for movie in result['items']] == ([expected_id] if expected_id else [])
                assert loaded == ([expected_id] if expected_id else [])
        finally:
            event.remove(Movie, 'load', record_load)
            app.state.runtime.db.engine.dispose()
