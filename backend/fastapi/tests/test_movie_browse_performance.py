from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import event

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend' / 'fastapi'))

from main import create_app
from services.database import Movie


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
