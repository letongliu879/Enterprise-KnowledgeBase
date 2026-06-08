# Contributing to Enterprise KnowledgeBase

Thank you for your interest in contributing.

## Development Setup

See [README.md](README.md#quick-start) for local development environment setup.

## Code Conventions

- **Python**: Follow PEP 8, use `snake_case` for functions/variables, `PascalCase` for classes.
- **Java**: Follow standard Spring Boot conventions, use `camelCase`.
- **TypeScript**: Follow the project's existing patterns.
- **Commit messages**: Write clear, concise commit messages in English.

## Pull Request Process

1. Ensure your code passes existing tests (`uv run pytest` for Python, `mvn test` for Java).
2. Update any affected documentation.
3. For cross-service changes, update `contracts/` first.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.
