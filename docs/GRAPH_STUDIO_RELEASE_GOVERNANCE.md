# Graph Studio Linux release governance — Issue #123

Graph Studio has **two separate workflows**. A normal merge is never a
release authorization.

## Build-only CI

`.github/workflows/graph-studio.yml` runs on qualifying PRs and pushes to
`main` and can also be invoked manually for nonpublishing verification. Its
`GITHUB_TOKEN` has **read-only contents permission**. It compiles the Tauri
backend, runs regression/Rust tests, builds AppImage/Deb packages and checks
they exist. It contains no release/tag-writing command.

A successfully merged F8/Graph Studio tools, source or docs change does
**not** move `roadpilot-graph-studio-linux` or replace its assets.

## Owner-approved release

`.github/workflows/graph-studio-release.yml` runs only via
`workflow_dispatch`. To request a release:

1. Verify the intended source is merged and obtain the exact **40-character
   lowercase current `main` commit SHA**.
2. In GitHub Actions, open **Publish Graph Studio Linux (owner approval)**,
   choose branch `main`, fill `source_sha` with that SHA and enter exactly
   `PUBLISH_GRAPH_STUDIO_LINUX` for `confirm_release`.
3. The read-only `authorize` job rejects a non-main dispatch, a malformed
   or stale source SHA, and an incorrect confirmation.
4. The `publish` job pauses at GitHub's protected environment
   **`graph-studio-linux-release`**. The repository owner must **separately
   approve the deployment in GitHub**. No publication occurs if approval is
   declined or not granted.
5. After approval, a fresh job checks out the exact authorized SHA, verifies
   it is still `main`, repeats Graph Studio regressions, builds the frontend,
   compiles/tests Rust, packages AppImage/Deb and prepares SHA-256 provenance.
   It checks the SHA again immediately before publishing.
6. Only then does the publishing step update the existing rolling
   `roadpilot-graph-studio-linux` prerelease. It uploads
   `RoadPilot-Graph-Studio-Linux.AppImage`,
   `RoadPilot-Graph-Studio-Linux.deb`, and
   `RoadPilot-Graph-Studio-Linux-SHA256SUMS.txt`, with an exact source
   fingerprint, run ID and approval environment. Finally it re-downloads
   the assets to verify hashes and source identity.

If `main` changes at either of the release checks, the job fails closed.
Submit a new release request for the new source SHA instead of repinning an
existing approved job. A successful PR build is **not** by itself evidence
that a release has been authorized or published.

## Required GitHub environment configuration

This repository requires an actual GitHub **environment protection rule**;
the workflow's `environment:` declaration alone does **not** guarantee
human approval. The repository administrator must maintain:

- Environment: `graph-studio-linux-release`.
- Required reviewers: the owner account (`kandyman991`).
- Deployment branches: **only `main`**.
- Administrator bypass: disabled (where supported).
- As a single-owner project, self-review is allowed so the owner can initiate
  a request and separately authorize it; this must still be an explicit
  GitHub deployment review action.

Check environment settings before the first real release and after changing
repository ownership or reviewer permissions. Never expose GitHub credentials
or R2 tokens in workflow logs or commit them to the repository.

## Acceptance / limitations

- `tests/test_graph_studio_release_governance.py` asserts the default
  build workflow is read-only, publishing is manual-only, approval is a
  distinct environment gate, source SHAs are pinned, and release assets carry
  SHA-256 provenance. Run this test on every relevant PR.
- Existing rolling-release consumers keep their release URL. They should
  validate the supplied SHA-256 manifest before installing a new package.
- The rolling GitHub release/tag is still mutable for compatibility; GitHub
  does not atomically replace an entire set of release assets. A failed upload
  or network interruption can leave a partially updated release. The
  publication job fails on remote verification failure; treat that outcome
  as blocked and do not distribute the incomplete release. A separate
  immutable versioned-release design would be needed for fully transactional
  promotion.
- These Linux application releases are **not** approval to publish an F8
  connectivity catalog, graph tiles or Android production packages. Their
  separate architecture and approval gates remain in force.
