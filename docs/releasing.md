# Container publishing

Every successful CI run for a new commit on `main` publishes a Linux amd64
image to `ghcr.io/sjtrny/link-shortener`. Merging a pull request into `main` is
the normal publication action. No version tag or GitHub Release is required.

Pull requests and manual CI runs cannot log in to GHCR or publish images. The
publish job starts only after the application checks, dependency audit,
container lifecycle suite, image audit, and workflow syntax check all pass.

## Image tags

Each publication updates two tags:

| Container tag | Purpose |
| --- | --- |
| `latest` | The most recent successfully published `main` image. |
| `sha-<full-commit>` | An immutable reference to the source commit. |

Use `latest` for simple deployments that should follow `main`. Use the commit
tag or the reported image digest when a deployment must stay on one build.

The final job receives `packages: write` and logs in with the repository
`GITHUB_TOKEN`. All other jobs have read-only repository access. The published
image includes max-level provenance and an SPDX SBOM. The workflow checks that
both tags resolve to the reported digest, contain only Linux amd64 as a runnable
platform, and include an attestation manifest.

All third-party actions are pinned to commit hashes. The BuildKit and SBOM
scanner images are pinned to digests. The build receives only the source commit
as public image metadata; deployment secrets are not used during the build.

## Package linkage and visibility

The workflow publishes with the repository `GITHUB_TOKEN`, and the image carries
`org.opencontainers.image.source=https://github.com/sjtrny/link-shortener`.
These connect the GHCR package to this repository without a personal token.

GitHub creates a new personal-account package as private. After the first
publication, the owner must change the package visibility to public in GitHub's
package settings. Source and package visibility are separate. Verify the public
setting with an unauthenticated pull from a clean Docker configuration before
announcing the image.

## Verify a published image

Check the published image from another machine or a clean Docker client:

```bash
docker buildx imagetools inspect ghcr.io/sjtrny/link-shortener:latest
docker pull ghcr.io/sjtrny/link-shortener:sha-REPLACE_WITH_FULL_COMMIT
```

Confirm the revision and source labels after pulling the image. Then perform the
clean installation and persistent-volume checks in the operations guide.
