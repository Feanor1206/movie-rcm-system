from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def serve_web(app, directory):
    dist = Path(directory)
    index = dist / "index.html"
    if not index.is_file():
        return

    def page():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    for route in ("/", "/search", "/profile", "/admin/import", "/movies/{movie_id}", "/series/{series_id}"):
        app.add_api_route(route, page, methods=["GET", "HEAD"], include_in_schema=False)

    for name in ("assets", "illustrations"):
        if (dist / name).is_dir():
            app.mount(f"/{name}", StaticFiles(directory=dist / name), name=name)
