# WhiteNoise Static Files Design

## Goal

Serve Django static assets from the Heroku application using WhiteNoise so the
admin interface does not depend on the unavailable S3 bucket. Keep S3 as the
storage backend for user-uploaded media.

## Current problem

The deployed application uses `S3Boto3Storage` for static files and generates
asset URLs under the `anyon3` S3 bucket. That bucket currently returns
`NoSuchBucket`, so the admin CSS and JavaScript cannot load. The existing
`StaticStorage` class also defines a `static` object prefix, but it is not
selected by the current `STORAGES["staticfiles"]` configuration.

## Design

1. Add WhiteNoise as a runtime dependency.
2. Add `WhiteNoiseMiddleware` immediately after Django's
   `SecurityMiddleware`.
3. Use `/static/` as the application-relative static URL and
   `BASE_DIR / "staticfiles"` as `STATIC_ROOT`.
4. Include the existing project-level `static/` directory in
   `STATICFILES_DIRS`.
5. Configure
   `whitenoise.storage.CompressedManifestStaticFilesStorage` for the
   `staticfiles` storage backend.
6. Keep `custom_storages.MediaStorage` as the `default` storage backend and
   keep `MEDIA_URL` pointing to S3.
7. Ensure Heroku's build phase runs `collectstatic`, then verify that the
   collected admin assets are present in the slug and served under
   `/static/admin/...`.

## Data flow

Static source files from Django apps and the project-level `static/` directory
are collected into `staticfiles/` during the Heroku build. WhiteNoise serves
that directory from the web dyno. Uploaded media continues to be written to
the S3 `media/` prefix through `MediaStorage`.

## Validation

- Run Django checks.
- Run `collectstatic --noinput`.
- Confirm the collected admin CSS and JavaScript exist under `staticfiles/`.
- Start the application locally and request an admin asset from `/static/`.
- Confirm the deployed admin page no longer requests `anyon3.s3.amazonaws.com`
  for static assets.
