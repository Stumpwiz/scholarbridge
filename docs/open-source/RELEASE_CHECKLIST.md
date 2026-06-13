# Open Source Release Checklist

Use this checklist before any public release.

## Repository Content

- [ ] Seed files contain only synthetic data.
- [ ] No real personal names, emails, phones, or addresses in tracked files.
- [ ] No personal images in tracked files.
- [ ] No production exports (`*.dump`, `*.sql`, `*.xlsx`, `*.csv`, etc.) in tracked files.

## Security Hygiene

- [ ] No credentials in tracked files (`.env`, keys, tokens, private certs).
- [ ] `.gitignore` covers runtime uploads, dumps, and local environment files.
- [ ] Current-tree secrets scan completed and reviewed.

## PII Hygiene

- [ ] Current-tree PII scan completed and reviewed.
- [ ] Organization-specific examples are generalized where appropriate.

## Open Source Governance

- [ ] `LICENSE` present (Apache-2.0).
- [ ] `SECURITY.md` present and accurate.
- [ ] `CONTRIBUTING.md` present and accurate.
- [ ] `CODE_OF_CONDUCT.md` present and accurate.
- [ ] `docs/open-source/DATA_POLICY.md` present.

## Validation

- [ ] Test suite passes.
- [ ] README reflects public setup and contribution/security guidance.

## History Cleanup (separate phase)

- [ ] Sensitive historical blobs identified.
- [ ] History rewrite plan reviewed.
- [ ] Rewrite executed in controlled window.
- [ ] Team re-clone instructions prepared.
