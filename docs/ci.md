# CI and local checks

The `CI` workflow runs for pull requests, pushes to `main`, and manual runs.
It uses GitHub-hosted Ubuntu runners and SHA-pinned actions. Check jobs have a
read-only repository token, and checkout credentials are not retained. Only a
successful push to `main` starts the final publish job and grants it
`packages: write`. Pull requests and manual runs cannot log in to GHCR or push
an image. Fork pull requests use `pull_request`, not `pull_request_target`.

## Jobs

| Job | Coverage |
| --- | --- |
| Workflow syntax | Download actionlint from its pinned release, verify the archive checksum, and check every workflow. |
| Application (Python 3.13 and 3.14) | Locked installation; application regression suite; migration drift; strict production deployment checks; both Compose configurations. |
| Locked dependency audit | Export runtime requirements and hashes from `uv.lock`, then audit them with pip-audit. |
| Container lifecycle and image audit | Build the candidate and baseline images; check fresh startup, HTTP behavior, data persistence, backup/restore, upgrade, and graceful shutdown; scan the candidate image with Trivy. |
| Publish amd64 image | After every other job passes on a `main` push, publish `latest` and an immutable full-commit tag to GHCR with provenance and an SBOM. |

Regression coverage includes generated and custom codes, case normalization,
collisions and database uniqueness, reserved codes, redirects, admin access,
canonical URLs and QR permissions, configuration failures, proxy trust,
bootstrap behavior, and readiness.

The application checks generate a temporary random secret and use an example
HTTPS domain. HSTS is fully enabled for this fixture so `check --deploy
--fail-level WARNING` can reject every deployment warning. These fixture
settings do not change production defaults or the operator's HSTS choices.

The container suite uses isolated named volumes, no published ports, and no
external container network. It checks the non-root/read-only runtime, Docker
health, real Gunicorn HTTP responses, HTTPS and host handling, admin login,
static assets, QR images, retained links and passwords, offline backup/restore,
SQLite integrity, and clean shutdown. A loopback-only trusted proxy fixture
allows HTTPS behavior to be exercised without a TLS server. The resources and
generated credentials are removed at the end, including on check failure.

For a pull request, the upgrade baseline is its base-branch commit. For a push,
it is the branch's previous commit. Manual runs use the checked-out commit's
first parent. The baseline is built from `git archive`, so the candidate's
files cannot enter that build. The suite starts the baseline on a fresh volume,
creates links, stops it, and starts the candidate on the same volume. Only one
app writes to each volume at a time. Container coverage currently uses Linux
amd64; it does not claim to validate other architectures.

## Audit policy

The Python audit fails for any reported vulnerability in the exported runtime
requirements. It uses exact versions and hashes from the lockfile, without
resolving or installing a different dependency set. The audit runs on Linux;
platform markers for other operating systems still apply.

The image audit reports all OS and language-package vulnerabilities in the job
log. A second scan fails for **HIGH or CRITICAL findings with an available fix**.
Unfixed and lower-severity findings remain visible for review; a passing gate
does not mean the image has no advisories. Scanner or database-download failures
fail the job. There are no advisory-ID exceptions or ignored packages.

Update dependencies or the base image to address a failed audit, then rerun the
checks. Review unfixed findings before a release. Keep tool versions and action
commit pins current when updating CI.

The image applies Debian package updates during its build and removes the
unused system pip installation and its bundled libraries. CI builds on a fresh
runner. For a local security rebuild, use `docker build --pull --no-cache` so
an older cached package-update layer cannot be reused.

## Run locally

Use uv and Docker, from the repository root:

```bash
uv sync --locked --python 3.13
uv run --locked python ci/check.py
```

The script supplies its own application environment and does not load `.env`.
It does not run migrations against your local application database. Repeat in
a separate environment with Python 3.14 to cover the second CI version.

To reproduce the container suite against the current `main` baseline:

```bash
docker build --pull -t link-shortener:ci .
git archive main | docker build --pull -t link-shortener:baseline -
python3 ci/container_smoke.py --image link-shortener:ci --upgrade-from link-shortener:baseline
```

Use the PR's actual base commit instead of `main` if your local branch has moved.
Both images must already exist in the Docker daemon. The suite works with a
remote daemon because it streams probes and archives instead of mounting client
paths. It removes only its randomly named containers and volumes; the two image
tags remain available for inspection or removal.

See [container publishing](releasing.md) for the automatic `main` publication
flow, image tags, and first-package visibility step.

To reproduce the dependency audit:

```bash
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file /tmp/link-shortener-requirements.txt
uvx pip-audit==2.10.1 --strict --disable-pip --require-hashes -r /tmp/link-shortener-requirements.txt
```

With Trivy 0.74.0 installed, reproduce the image report and gate:

```bash
trivy image --scanners vuln link-shortener:ci
trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 link-shortener:ci
```
