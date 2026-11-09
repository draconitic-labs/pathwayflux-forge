# Security

Report vulnerabilities privately through [GitHub private vulnerability reporting](https://github.com/draconitic-labs/pathwayflux-forge/security/advisories/new), or at [support@draconitic.com](mailto:support@draconitic.com).

Fixes go to the `main` branch. There are no maintained older branches.

The API listens on `127.0.0.1`, accepts only `127.0.0.1` and `localhost` as the request host, and grants no cross-origin access. Project ids are limited to lowercase letters, digits and hyphens. Custom rate expressions are parsed into a syntax tree and evaluated without `eval`; only numbers, known names and arithmetic operators are accepted.
