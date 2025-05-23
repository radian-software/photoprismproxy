import hashlib
import io
import os
import random
import string
from typing import Tuple
from urllib.parse import urlencode

import dotenv
import flask
import requests

dotenv.load_dotenv()


global_uploads_memory = {}


class Config:
    URL = os.environ["PHOTOPRISM_URL"]
    USERNAME = os.environ["PHOTOPRISM_USERNAME"]
    PASSWORD = os.environ["PHOTOPRISM_PASSWORD"]
    MAX_SIZE = int(os.environ["MAX_UPLOAD_BYTES"])
    AUTH_SECRET = os.environ["AUTH_SECRET"]


class PhotoPrism:
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.headers = {
            "Authorization": f"Bearer {self.password}",
        }
        self.user_id, self.preview_token = self.get_user_info()

    def get_user_info(self) -> Tuple[str, str]:
        resp = requests.get(
            self.url + "/api/v1/session",
            headers=self.headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["user"]["UID"], data["config"]["previewToken"]

    def generate_token(self) -> str:
        # https://github.com/photoprism/photoprism/blob/f652159522f992a56ea918db90275dd2257a5664/frontend/src/common/util.js#L294-L296
        # but less scuffed, cf https://github.com/photoprism/photoprism/issues/4970
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=7))

    def upload_photos(self, photos, album=None) -> Tuple[str, list[str], str | None]:
        route = f"/api/v1/users/{self.user_id}/upload/{self.generate_token()}"
        hashes = []
        for photo in photos:
            data = photo.read()
            h = hashlib.sha1()
            h.update(data)
            hashes.append(h.hexdigest())
            resp = requests.post(
                self.url + route,
                headers=self.headers,
                files={
                    "files": (photo.filename, io.BytesIO(data)),
                },
            )
            resp.raise_for_status()
            if not resp.json()["message"].startswith("1 file"):
                raise RuntimeError(f"Got unexpected server response: {resp.json()}")
        resp = requests.put(
            self.url + route,
            headers=self.headers,
            json={"albums": [album] if album else []},
        )
        resp.raise_for_status()
        resp = requests.get(
            self.url
            + "/api/v1/photos?"
            + urlencode(
                {
                    "count": "1000",
                    "q": "hash:" + "|".join(hashes),
                }
            ),
            headers=self.headers,
        )
        resp.raise_for_status()
        photo_urls = [
            f"{self.url}/api/v1/t/{photo['Hash']}/{self.preview_token}/fit_4096"
            for photo in resp.json()
        ]
        assert len(photo_urls) == len(
            photos
        ), f"{len(photo_urls)} urls for {len(photos)} photos"
        album_url = None
        if album:
            resp = requests.get(
                self.url
                + "/api/v1/albums?"
                + urlencode(
                    {
                        "count": "2",
                        "q": album,
                    }
                ),
                headers=self.headers,
            )
            resp.raise_for_status()
            matching_albums = resp.json()
            assert len(matching_albums) == 1
            album_id = matching_albums[0]["UID"]
            resp = requests.get(
                self.url + f"/api/v1/albums/{album_id}/links",
                headers=self.headers,
            )
            resp.raise_for_status()
            album_token = album_slug = None
            for link in resp.json():
                if link["Expires"] == 0:
                    album_token = link["Token"]
                    album_slug = link["Slug"]
                    break
            # if not album_token:
            #     slug = self.generate_token()
            #     resp = requests.post(
            #         self.url + f"/api/v1/albums/{album_id}/links",
            #         headers=self.headers,
            #         json={"Slug": slug},
            #     )
            #     resp.raise_for_status()
            #     album_token = resp.json()["Token"]
            #     album_slug = slug
            # album_url = f"{self.url}/s/{album_token}/{album_slug}"
            #
            # TODO: https://github.com/photoprism/photoprism/commit/a64e2ea4459bc56b2ba945d1a3fef962740d9953
            # lets us use the commented out code once that is released
            # and used publicly
            if not album_token:
                album_url = f"{self.url}/library/albums/{album_id}/view"
            else:
                album_url = f"{self.url}/s/{album_token}/{album_slug}"
        upload_id = self.generate_token()
        return upload_id, photo_urls, album_url


pp = PhotoPrism(Config.URL, Config.USERNAME, Config.PASSWORD)

app = flask.Flask(__name__, template_folder="pages")
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_SIZE


@app.before_request
def require_login():
    token = flask.request.cookies.get("auth-token")
    if token != Config.AUTH_SECRET:
        return flask.send_from_directory("pages", "auth.html")


@app.get("/")
def get_index():
    return flask.send_from_directory("pages", "index.html")


@app.post("/upload")
def post_upload():
    form = flask.request.form
    photos = flask.request.files.getlist("photos")
    if not photos:
        return flask.abort(400)
    if not all(photo.filename for photo in photos):
        return flask.abort(400)
    match form["sort"]:
        case "none":
            pass
        case "asc":
            photos.sort(key=lambda f: f.filename or "")
        case "desc":
            photos.sort(key=lambda f: f.filename or "", reverse=True)
        case _:
            return flask.abort(400)
    upload_id, photo_urls, album_url = pp.upload_photos(photos, album=form["album"])
    global_uploads_memory[upload_id] = photo_urls, album_url
    return flask.redirect(f"/success/{upload_id}")


@app.route("/success/<upload_id>", methods=["HEAD", "GET", "POST"])
def get_success(upload_id: str):
    if upload_id not in global_uploads_memory:
        return flask.abort(404)
    photo_urls, album_url = global_uploads_memory[upload_id]
    return flask.render_template(
        "success.html", photo_urls=photo_urls, album_url=album_url
    )
