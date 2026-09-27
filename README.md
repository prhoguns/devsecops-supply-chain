# DevSecOps Supply Chain

[![pipeline](https://github.com/prhoguns/devsecops-supply-chain/actions/workflows/pipeline.yml/badge.svg)](https://github.com/prhoguns/devsecops-supply-chain/actions/workflows/pipeline.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/prhoguns/devsecops-supply-chain/badge)](https://scorecard.dev/viewer/?uri=github.com/prhoguns/devsecops-supply-chain)

_Status: Built and verified September 26–27, 2026. Every result below came from a real run._

The build half of a two-repo setup. Every change to a small Python service goes through five
security gates. Only a change that passes all of them on `main` is built into an image, signed
with the workflow's own identity, given an SBOM and build provenance, and promoted by digest to
[kubernetes-gitops-platform](https://github.com/prhoguns/kubernetes-gitops-platform). The cluster
there refuses any image that this pipeline did not sign.

```
 push / PR ──► test ──────────┐
           ──► secrets ───────┤  Gitleaks over the branch's full history
           ──► sast ──────────┤  Semgrep (p/default, Dockerfile, GitHub Actions rules)
           ──► deps-and-config┘  Trivy (dependencies, secrets, misconfig) + Checkov (Dockerfile)
                     │
                     ▼
               image: build → Trivy image scan → smoke test (non-root, no shell, read-only)
                     │  main only
                     ▼
               release: push to GHCR → cosign sign (keyless, Sigstore)
                        → SPDX SBOM as a signed attestation → SLSA provenance
                        → verify all of it the way the cluster will
                     │
                     ▼
               promote: commit the new digest to kubernetes-gitops-platform (deploy key)
```

A full run on `main` takes about 2–3 minutes.

## The gates, proven by pull requests

Each of these PRs introduces one problem. Each was blocked, nothing was built or deployed, and
each is closed without merging so the failed checks stay visible:

| PR | Change | Blocked by |
|---|---|---|
| [#1](https://github.com/prhoguns/devsecops-supply-chain/pull/1) | Adds PyYAML 5.3.1 (CVE-2020-14343, CRITICAL) | Trivy dependency scan |
| [#2](https://github.com/prhoguns/devsecops-supply-chain/pull/2) | Hard-codes an API key (fake) | Gitleaks, and Semgrep's secrets rules |
| [#3](https://github.com/prhoguns/devsecops-supply-chain/pull/3) | Passes a query parameter to `eval()` | Semgrep `eval-detected` |
| [#4](https://github.com/prhoguns/devsecops-supply-chain/pull/4) | Runs the container as root | Trivy DS-0002, Checkov CKV_DOCKER_8, Semgrep |

## What gets published

For every commit on `main`, `ghcr.io/prhoguns/demo-api` gets an image with:

- a **keyless cosign signature**. There is no signing key to leak: Sigstore issues a short-lived
  certificate bound to this workflow's GitHub identity and records it in the Rekor transparency log.
- a signed **SPDX SBOM attestation** (46 packages in the current image).
- **SLSA v1 build provenance** from GitHub, naming the repository, workflow file and branch.

Anyone can check them. The identity must match exactly; a signature made by any other workflow
fails:

```bash
IMAGE=ghcr.io/prhoguns/demo-api@sha256:<digest from the GitOps repo>
ID=https://github.com/prhoguns/devsecops-supply-chain/.github/workflows/pipeline.yml@refs/heads/main

cosign verify "$IMAGE" --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
cosign verify-attestation "$IMAGE" --type spdxjson --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify "oci://$IMAGE" -R prhoguns/devsecops-supply-chain
```

The `policy-fixtures` workflow publishes two images that must *not* be admitted by the cluster:
one unsigned, and one validly signed but by the wrong workflow. The platform's tests use them to
prove the admission policy checks who signed, not only that a signature exists.

## The image

- Chainguard Python base, pinned by digest: **35 MB, 0 known CVEs** (Trivy), no shell, no package
  manager, runs as uid 65532.
- Multi-stage build. The first scan found 2 HIGH CVEs, both in libraries vendored inside `pip`.
  Nothing uses pip at runtime, so it is removed from the final image instead of suppressing the
  findings.
- The entrypoint is only `python`; the default command runs the API. The platform runs the load
  generator from the same signed image with `args: ["-m", "app.loadgen"]`, so there is no
  unsigned "test tool" image anywhere in the cluster.

## The service

`app/main.py` is a FastAPI service with health endpoints and Prometheus metrics labelled by route
template (so metric cardinality stays bounded). `ERROR_RATE` makes `/api/work` fail on purpose,
so the platform's alerting can be demonstrated by changing one value in Git. `app/loadgen.py`
generates steady traffic and accepts only http(s) URLs. 14 unit tests.

```bash
pip install -r requirements-dev.txt && pytest -q     # tests
docker build -t demo-api . && docker run -p 8080:8080 demo-api
```

## Problems I hit

- **Semgrep's `p/python` ruleset passed an `eval()` on user input.** Found while building PR #3.
  The pipeline now uses `p/default`, which also flagged two real issues in the clean code:
  `urlopen()` on a configurable URL (urllib accepts `file://`, now restricted to http/https with
  tests), and Dependabot proposing releases the day they ship (now a 7-day cooldown, since most
  malicious package releases are pulled within days).
- **One secret broke every branch.** After PR #2, every build started failing Gitleaks: a
  full-depth checkout fetches all branches and Gitleaks scanned all of them. It now scans the full
  history of the commit under test (`--log-opts=HEAD`) and nothing else.
- **The load generator would have crashed on every deployment.** Stopping the API while it ran
  killed it: `urllib` raises `ConnectionResetError` directly instead of wrapping it in `URLError`,
  and a rolling update resets connections the same way. Any network error now counts as a failed
  request, with a regression test that fails on the old code.
- **Checkov's GitHub Actions checks evaluated nothing** on this workflow file, so they would
  have passed anything. Workflow security is covered by Semgrep's `p/github-actions` rules instead.

## Supply-chain hygiene in the pipeline itself

- `main` is protected: a pull request cannot merge until all five gates pass, and force pushes and
  branch deletion are blocked.
- Every third-party action is pinned to a full commit SHA, not a tag.
- Default token permissions are read-only; `packages`, `id-token` and `attestations` write access
  is granted only to the release job that needs it.
- Checkouts do not persist credentials, except in the promote job, which needs its key to push.
  That key is a deploy key scoped to the one GitOps repository, not a personal token.
- Dependabot keeps pip packages, the base image digest and the actions up to date, a week after
  each release.
