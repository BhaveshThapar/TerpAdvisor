Run all checks before committing. Execute in order and report results for each:

1. **Backend tests**
```bash
cd backend && python -m pytest tests/ -q --tb=short
```

2. **Frontend typecheck**
```bash
cd frontend && npx tsc --noEmit
```

3. **Frontend lint**
```bash
cd frontend && npm run lint
```

If anything fails, list what failed and stop. Do not mark work as done until all three pass.
