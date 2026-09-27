# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub:
**Security → Report a vulnerability** on this repository
([private vulnerability reporting](https://github.com/prhoguns/devsecops-supply-chain/security/advisories/new)).
Do not open a public issue for a suspected vulnerability.

Include what you found, how to reproduce it, and the commit or image digest affected. I aim to
acknowledge reports within 3 business days and to share a fix or mitigation plan within 14 days.

## Scope

- The `demo-api` service in `app/`.
- The supply-chain pipeline in `.github/workflows/`, including the signing, SBOM, provenance and
  promotion steps.
- Published images in `ghcr.io/prhoguns/demo-api`. Only images signed by
  `.github/workflows/pipeline.yml@refs/heads/main` are genuine; the README shows how to verify one.

`ghcr.io/prhoguns/policy-fixtures` contains deliberately unsigned and wrongly signed images used to
test admission policies. They are not a vulnerability.

## Supported versions

Only the latest image built from `main` is supported. Older digests are not patched; the pipeline
rebuilds on every change and Dependabot keeps dependencies current.
