# Contributing to Open-Clip

We appreciate your interest in contributing to Open-Clip. By participating in this project, you agree to abide by our code of conduct.

## How to Contribute

### Reporting Bugs
If you find a bug, please check the issues list to see if it has already been reported. If not, open a new issue with the following information:
* A clear and descriptive title.
* Steps to reproduce the issue.
* Expected and actual results.
* Environment details (OS, Docker version).

### Suggesting Enhancements
We welcome ideas for new features. Please open an issue to discuss your proposal before starting any work. This helps us ensure that the new feature fits the project goals.

### Code Contributions
If you want to submit a fix or a feature:

1. **Fork** the repository.
2. **Create** a new branch for your feature or fix.
3. **Write** clear and concise code.
4. **Add tests** for your changes. We require all new code to be covered by tests.
5. **Run the existing test suite** to ensure no regressions were introduced.
   * Backend: Run `pytest` in the `backend` directory.
   * Frontend: Run `npm run test` in the `frontend` directory.
6. **Submit a Pull Request** with a detailed description of what you changed and why.

## Development Standards

* **Code Style**: Follow PEP 8 for Python and standard TypeScript/React conventions.
* **Documentation**: Update documentation if your changes require it.
* **Atomic Commits**: Keep your commits focused on a single change.

## License Note

This project is licensed under the GNU Affero General Public License v3.0 (AGPLv3). By contributing, you agree that your contributions will be licensed under the same terms.

