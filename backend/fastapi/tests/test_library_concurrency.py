from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from main import create_app
from services.database import FavoriteItem, Movie, MovieRating, WatchlistItem


@pytest.mark.parametrize("endpoint,model", [
    ("watchlist", WatchlistItem), ("favorites", FavoriteItem), ("ratings", MovieRating),
])
def test_simultaneous_library_additions_keep_one_item(endpoint, model):
    application = create_app(load_default=False)
    with TestClient(application, raise_server_exceptions=False) as client:
        login = client.post("/api/auth/login", json={"usernameOrEmail": "user", "password": "password123"})
        headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
        barrier = Barrier(2)

        def before_flush(session, context, objects):
            if any(isinstance(item, model) for item in session.new):
                barrier.wait(timeout=5)

        event.listen(Session, "before_flush", before_flush)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(lambda _: client.post(
                    "/api/users/" + endpoint, headers=headers,
                    json={"movieId": "the-last-orbit", "rating": 8},
                ).status_code, range(2)))
        finally:
            event.remove(Session, "before_flush", before_flush)
        assert statuses == [200, 200]
        assert len(client.get("/api/users/" + endpoint, headers=headers).json()["data"]) == 1


@pytest.mark.parametrize("endpoint", ["watchlist", "favorites"])
def test_movie_metadata_is_read_from_the_movie_after_an_update(endpoint):
    application = create_app(load_default=False)
    url = "/api/users/" + endpoint
    with TestClient(application) as client:
        login = client.post("/api/auth/login", json={"usernameOrEmail": "user", "password": "password123"})
        headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
        created = client.post(url, headers=headers, json={"movieId": "the-last-orbit"}).json()["data"]
        with application.state.runtime.db.session() as db:
            movie = db.get(Movie, "the-last-orbit")
            movie.title = "New title"
            movie.poster = None
            db.commit()
        expected = {**created, "movieTitle": "New title", "posterUrl": None}
        assert client.get(url, headers=headers).json()["data"] == [expected]
        assert client.post(url, headers=headers, json={"movieId": "the-last-orbit"}).json()["data"] == expected
