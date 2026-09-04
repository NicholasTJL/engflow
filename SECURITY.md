# Security Policy

engflow executes user-defined commands and Python entrypoints as part of running a workflow.
Treat workflow files as executable code, not data — only run workflows from sources you trust.

## Reporting a Vulnerability

If you find a security issue (for example, a way for a malicious workflow file to escape its
working directory, leak secrets, or execute unintended code), please report it privately via
GitHub's [private vulnerability reporting](https://github.com/NicholasTJL/engflow/security/advisories/new)
rather than opening a public issue.

Include:

- A description of the issue and its impact.
- Steps to reproduce, ideally a minimal workflow file.
- The engflow version and operating system.

We aim to acknowledge reports within 5 business days.

## Supported Versions

Only the latest released minor version receives security fixes while the project is pre-1.0.
