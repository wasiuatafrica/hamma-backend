# WhiteNoise Static Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Serve Django static assets from Heroku with WhiteNoise while retaining S3 for uploaded media.

**Architecture:** Django will collect app and project static assets into a local `staticfiles/` directory during the Heroku build. WhiteNoise will serve that directory after `SecurityMiddleware`; the existing S3 media storage remains the `default` storage backend and continues using the `media/` prefix.

**Tech Stack:** Django 6.0, WhiteNoise, django-storages, uv, Heroku Python buildpack, Daphne.

## Global Constraints

- WhiteNoise handles static files only; S3 remains responsible for uploaded media.
- Static URLs must be application-relative (`/static/`), not S3 URLs.
- `STATIC_ROOT` must not be the same directory as the project-level static source directory.
- WhiteNoise middleware must immediately follow Django's `SecurityMiddleware`.
- Static storage must use `whitenoise.storage.CompressedManifestStaticFilesStorage`.
- Do not expose or copy credentials from `.env`.
- This workspace is not a Git repository, so commit steps are replaced with verification notes.

---

### Task 1: Add the WhiteNoise dependency

**Files:**
- Modify: `pyproject.toml` dependency list
- Modify: `uv.lock`

**Interfaces:**
- Produces the installed `whitenoise` package required by Django settings.

- [ ] **Step 1: Add the dependency**

Add `"whitenoise"` beside the existing Django storage dependencies in `pyproject.toml`:

```toml
    "django-storages",
    "whitenoise",
    "djangorestframework",
```

- [ ] **Step 2: Resolve and install the lockfile**

Run:

```bash
uv lock
uv sync
```

Expected: `uv.lock` contains a `whitenoise` package entry and the environment installs successfully.

- [ ] **Step 3: Verify the package import**

Run:

```bash
.venv/bin/python -c 'import whitenoise; from importlib.metadata import version; print(version("whitenoise"))'
```

Expected: the command prints a WhiteNoise version and exits with status 0.

### Task 2: Configure WhiteNoise and preserve S3 media

**Files:**
- Modify: `backend/settings.py`
- Modify: `custom_storages.py`
- Modify: `.gitignore`

**Interfaces:**
- `django.contrib.staticfiles` resolves URLs under `/static/`.
- `whitenoise.middleware.WhiteNoiseMiddleware` serves collected static files.
- `STORAGES["default"]` remains `custom_storages.MediaStorage`.
- `STORAGES["staticfiles"]` becomes `whitenoise.storage.CompressedManifestStaticFilesStorage`.

- [ ] **Step 1: Add WhiteNoise middleware**

Insert WhiteNoise immediately after `SecurityMiddleware`:

```python
MIDDLEWARE = [
    # 'silk.middleware.SilkyMiddleware',
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ...
]
```

- [ ] **Step 2: Replace the S3 static configuration**

Replace the commented static settings and S3 static URL configuration with:

```python
# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
```

Keep the media settings S3-backed:

```python
MEDIAFILES_LOCATION = "media"
MEDIA_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, MEDIAFILES_LOCATION)
```

- [ ] **Step 3: Select WhiteNoise for static storage**

Keep the media storage backend and replace only the static backend:

```python
STORAGES = {
    "default": {
        "BACKEND": "custom_storages.MediaStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

Remove the unused `STATICFILES_LOCATION` setting after the replacement.

- [ ] **Step 4: Remove the unused S3 static storage class**

Leave `MediaStorage` in `custom_storages.py` and remove only `StaticStorage`, resulting in:

```python
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    location = settings.MEDIAFILES_LOCATION
```

- [ ] **Step 5: Check the configuration**

Run with a local non-SRV MongoDB URI so Django startup does not depend on external DNS:

```bash
MONGO_STRING=mongodb://localhost:27017 .venv/bin/python manage.py check
```

Expected: Django reports no configuration errors. A local MongoDB connection is not required for this command.

- [ ] **Step 6: Ignore WhiteNoise's generated output**

Add this entry to `.gitignore`:

```gitignore
/staticfiles/
```

Expected: the collected `staticfiles/` directory remains deployment output and
is not treated as a source directory.

### Task 3: Collect and test static assets

**Files:**
- Generated: `staticfiles/` (ignored build output; do not add source files there)

**Interfaces:**
- Collected admin assets are available at `staticfiles/admin/css/base.css` and `staticfiles/admin/js/theme.js`.
- A request to `/static/admin/css/base.css` returns HTTP 200 through WhiteNoise.

- [ ] **Step 1: Remove the broken project CSS reference**

In `static/css/main.css`, keep the existing green background without
referencing the absent image:

```css
.video-meger-section {
    background: #359602;
}
```

Expected: the project stylesheet no longer references the missing
`images/patternpad.png` asset.

- [ ] **Step 2: Collect static files**

Run:

```bash
MONGO_STRING=mongodb://localhost:27017 .venv/bin/python manage.py collectstatic --noinput
```

Expected: Django reports the number of copied files and exits successfully. Duplicate-file warnings are acceptable only when the same path exists in both the project-level `static/` directory and an installed app; collection must still finish successfully.

- [ ] **Step 3: Verify the key collected files**

Run:

```bash
test -f staticfiles/admin/css/base.css
test -f staticfiles/admin/js/theme.js
```

Expected: both commands exit with status 0.

- [ ] **Step 4: Verify WhiteNoise serves an admin asset**

Run:

```bash
MONGO_STRING=mongodb://localhost:27017 .venv/bin/python manage.py shell -c '
from django.test import Client

response = Client().get("/static/admin/css/base.css")
assert response.status_code == 200, response.status_code
assert "text/css" in response["Content-Type"], response["Content-Type"]
print(response.status_code, response["Content-Type"])
'
```

Expected: the command prints `200` with a CSS content type.

### Task 4: Validate deployment behavior

**Files:**
- No additional source file changes expected.

- [ ] **Step 1: Verify Heroku build collection**

On the next deployment, inspect the build output and confirm the Python buildpack runs `collectstatic`. The build must complete without `NoSuchBucket` because static collection no longer uses S3.

- [ ] **Step 2: Verify the deployed admin asset URL**

Open the deployed admin login page and inspect the CSS request. Expected:

```text
https://api-hamma-f0bcaabf77ea.herokuapp.com/static/admin/css/base.css
```

It must return HTTP 200 and must not reference `anyon3.s3.amazonaws.com` for static assets.

- [ ] **Step 3: Verify media remains on S3**

Upload or inspect one existing media-backed object and confirm its URL still uses the configured S3 `media/` prefix.

