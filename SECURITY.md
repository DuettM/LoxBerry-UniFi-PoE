# Security Policy

## Supported versions
Only the latest published release is actively supported with security fixes unless stated otherwise.

## Reporting a vulnerability
Do not publish vulnerabilities, credentials, tokens, private keys, personal data or exploit details in a public issue. Report security problems privately to `duett86@web.de` with affected version, impact, reproducible steps and redacted logs.

## Responsible testing
Test only systems, accounts and devices you own or are explicitly authorized to test. Do not bypass access controls, exfiltrate data, perform denial-of-service testing or publish working exploit details before a fix is available.

## Credential incidents
If a password, token, session cookie or private signing key is exposed, treat it as compromised and rotate/revoke it immediately; deleting it from Git history alone is not sufficient.

## Release security
Release ZIP files are protected by the project's SHA-256 and Ed25519 verification path. The private signing key must remain outside the repository and be available only to the authorized release process. A signing-key exposure requires immediate key rotation and a new trusted public key release path.
