# Contributing to TLEX

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to TLEX. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## 🛠️ Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/your-username/tlex.git
    cd tlex
    ```
3.  **Create a branch** for your feature or bugfix:
    ```bash
    git checkout -b feature/amazing-feature
    ```
4.  **Set up the environment** following the [README](README.md) instructions.

## 💻 Development Workflow

### Backend (Python/FastAPI)
- Uses **Ruff** for linting and formatting.
- Ensure all tests pass (if any).
- Run linting before committing:
  ```bash
  ruff check .
  ruff format .
  ```

### Frontend (Next.js)
- Uses **ESLint** and **Prettier**.
- Run linting:
  ```bash
  cd frontend
  npm run lint
  ```
- run prettier:
  ```bash
  cd frontend
  npx prettier --write .
  ```

## 📮 Pull Request Process

1.  Prioritize clear, descriptive commit messages.
2.  Update the `README.md` with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.
3.  You may merge the Pull Request in once you have the sign-off of two other developers, or if you do not have permission to do that, you may request the second reviewer to merge it for you.

## 🐛 Reporting Bugs

Bugs are tracked as GitHub issues. When filing an issue, please include:
- A clear title and description.
- Steps to reproduce the bug.
- Expected vs. actual behavior.
- Logs or screenshots if applicable.

## 📜 License

By contributing, you agree that your contributions will be licensed under its MIT License.
