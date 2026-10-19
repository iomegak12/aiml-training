# Security Policy

## Scope

This repository is a training kit. It contains **synthetic** datasets and a Python dependency list, and has no deployed service. Relevant security issues include:

- A vulnerable or compromised dependency pinned or allowed by `requirements.txt`
- Anything committed that should not be public, such as credentials, API keys, tokens or personal data
- Data that appears to be real rather than synthetic (every company, person and figure in this kit is meant to be invented)
- Code or instructions in the repository that could harm a participant's machine

Defects deliberately planted in the Day 1–2 raw datasets (bad dates, duplicates, inconsistent labels, missing values) are part of the exercises and are **not** security issues.

## Supported versions

Only the latest release on the default branch receives fixes.

| Version | Supported |
|---|---|
| 1.x (latest) | Yes |
| Older | No |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's **[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)** (the *Security* tab → *Report a vulnerability*), or by email to **[SECURITY CONTACT EMAIL]**.

Please include:

- What you found and where (file, line, dependency and version)
- How to reproduce it, or why it matters
- Any suggested fix

## What to expect

- Acknowledgement within **5 business days**
- An assessment and planned fix (or an explanation if we don't consider it a vulnerability) within **14 days**
- Credit in the release notes, if you'd like it

If a secret was committed, we will rotate it first and then remove it from the history.
