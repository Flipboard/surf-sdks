# Contributing to Surf API SDKs

Thanks for your interest in contributing! This document explains how to get involved.

## Reporting Bugs

Found a bug? [Open an issue](https://github.com/Flipboard/surf-sdks/issues/new) with:

- **SDK and version** (e.g., Python 1.0.0)
- **What you expected** vs. **what happened**
- **Minimal code to reproduce** the issue
- **Error message** or stack trace (if any)

## Requesting Features

Have an idea? [Open an issue](https://github.com/Flipboard/surf-sdks/issues/new) with the `enhancement` label. Describe the use case and how it would help your project.

## Pull Requests

We welcome PRs! Here's the process:

### Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/surf-sdks.git`
3. Create a branch: `git checkout -b fix/describe-your-change`
4. Make your changes
5. Test your changes (see below)
6. Commit with a clear message
7. Push and open a PR against `main`

### Guidelines

- **One PR per change** -- keep PRs focused and reviewable
- **Match existing style** -- follow the conventions in the SDK you're modifying
- **Add tests** for new features or bug fixes
- **Don't break existing tests** -- run the test suite before submitting
- **Update docs** if your change affects the public API (README, code comments)

### Testing

Each SDK has its own test suite. Run them with a test API token:

```bash
export SURF_API_TEST_TOKEN=surf_sk_test_...

# Python
cd python && pytest tests/ -v

# TypeScript
cd typescript && npm run test:integration

# Go
cd go && go test -tags integration -v

# Java
cd java && ./gradlew integrationTest
```

Or run all SDKs at once:

```bash
./test-harness/run_all.sh
```

### PR Review

- A maintainer will review your PR, usually within a few business days
- We may request changes -- this is normal and collaborative
- Once approved, a maintainer will merge it

## Code of Conduct

Be respectful and constructive. We're all here to build great tools. Harassment, discrimination, or abusive behavior will not be tolerated.

## Questions?

- **Discord**: [Join the Surf Developers community](https://discord.gg/R4E9frvzcn)
- **Email**: support@surf.social

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
