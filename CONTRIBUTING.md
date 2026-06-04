# Contributing to Amp

Thanks for your interest in contributing to Amp!

## How to Contribute

### Bug Reports
Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your environment (OS, Node version, Python version, AI host)

### Feature Requests
Open an issue describing:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Pull Requests

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run the test suite: `npm test`
5. Commit with a descriptive message
6. Push and open a PR

### Code Standards

- **Python (MCP servers):** Follow PEP 8. All servers must pass `python3 -c "import ast; ast.parse(open('file.py').read())"`
- **JavaScript (hooks, scripts):** Use CommonJS (`require`). Node 18+ compatible.
- **Markdown (skills, docs):** Follow the skill format in `.claude/skills/README.md`
- **Shell scripts:** Use `#!/usr/bin/env bash` with `set -euo pipefail`

### Skill Contributions

To contribute a new skill:
1. Create a folder in `.claude/skills/your-skill-name/`
2. Add `SKILL.md` with the standard format (see existing skills for examples)
3. Test it by invoking `/your-skill-name` in your AI agent
4. Submit a PR

### MCP Server Contributions

MCP servers live in `core/mcp/`. Each server:
- Reads `VAULT_PATH` from environment
- Uses the `mcp` Python framework
- Has tools decorated with proper descriptions
- Handles missing files/config gracefully

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
