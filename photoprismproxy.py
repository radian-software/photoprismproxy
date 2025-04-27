import flask

app = flask.Flask(__name__)


@app.get("/")
def get_index():
    return flask.send_from_directory("static", "index.html")
