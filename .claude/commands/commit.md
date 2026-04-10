Run /verify first. If all checks pass, create a git commit.

1. Run `git status` and `git diff` to review what changed
2. Stage only relevant files (never .env, never node_modules, never __pycache__)
3. Write a commit message: one short subject line describing *what and why*, no bullet lists
4. Commit with:
```bash
git add <specific files>
git commit -m "your message"
```

Do not push unless explicitly asked.
