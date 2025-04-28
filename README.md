# photoprismproxy

Small web utility for more easily uploading photo(s) to PhotoPrism. It
works around some rough edges in the UX but does not offer
fundamentally new features. You deploy this Flask/Gunicorn server to
whatever cloud host or personal server you wish, put it behind TLS,
and provide it with an application password in environment variables
(`.env` is supported). Like this:

```
MAX_UPLOAD_BYTES=20000000
PHOTOPRISM_URL=https://photos.example.com/
PHOTOPRISM_USERNAME=admin
PHOTOPRISM_PASSWORD=xxxxxx-xxxxxx-xxxxxx-xxxxxx
```

Then, it provides a minimal webpage that allows you to select one or
more photos to upload, optionally to sort them into a different order
based on filename (A-Z or Z-A), and optionally to add them to a new or
existing album by name. The sorting feature is because adding photos
to the library in the correct order is the only way to robustly ensure
the display order of a custom album, due to the lack of the ability to
change album entry ordering.
