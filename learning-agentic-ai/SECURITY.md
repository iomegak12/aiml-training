# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

**Please do not report security vulnerabilities in public GitHub issues.**

Email **jd.ramkumar@gmail.com** with:

- a description of the vulnerability and its impact
- steps to reproduce (requests, configuration with secrets removed)
- the affected version (`GET /health`)
- any suggested fix

You can expect an acknowledgement within **5 business days**. We will keep you informed while we investigate and fix the issue, and credit you in the release notes unless you prefer to stay anonymous. Please give us reasonable time to release a fix before any public disclosure.

## Security considerations for deployments

This project is a demonstration service. Before exposing it beyond a trusted network, consider the following.

### No authentication

The API has **no authentication or authorization**. Anyone who can reach it can talk to the agent, which can create, change, resolve and archive tickets and spends your OpenAI credits. Put it behind an authenticating reverse proxy or API gateway, or keep it on a private network.

### Secrets

- Keep `OPENAI_API_KEY` in `.env` or a secret store. `.env` is excluded from git and from the Docker build context.
- The API never logs or returns the key; the banner and `/ready` only show whether it is set.

### Logs contain conversation text

Request logs (`logs/api.log`) include the user's message and the agent's reply. Treat the log files as sensitive data: restrict access, and set a retention period that fits your policy. Rotation keeps at most about 60 MB (10 MB × 6 files).

### Rate limiting and proxies

Rate limiting uses the direct client IP and does not trust `X-Forwarded-For`. Behind a proxy, all clients share one limit; apply per-client limits at the proxy if needed. Limits are in-memory and per process.

### Prompt injection

The agent acts on natural-language input and on ticket text written by other users. A crafted message or ticket description could try to steer the agent into unintended ticket changes. Review the agent's actions in the logs, use plan mode (`mode: "plan"`) when actions need approval, and restrict who can reach the API.

### Container

The image runs as a non-root user and contains only the virtual environment and `main.py`. Rebuild it regularly to pick up security fixes in the base image and dependencies.
