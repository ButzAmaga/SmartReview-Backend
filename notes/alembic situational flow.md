### All 3 Situations — Command Line

---

#### Situation 1: First time setting up Alembic (empty DB)
```bash
# 1. Delete existing DB if any
del myapp.db

# 2. Generate migration from your models
alembic revision --autogenerate -m "initial tables"

# 3. Apply — this creates all your tables
alembic upgrade head
```

---

#### Situation 2: You have real data you want to keep
```bash
# 1. Hand over DB control to Alembic (marks current state as migrated)
alembic stamp head

# 2. From now on, every models.py change follows this flow:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

---

#### Situation 3: You used `create_all()` before Alembic (tables exist, no data)
```bash
# 1. Delete the DB (tables exist but no real data to lose)
del myapp.db

# 2. Comment out or remove create_all() from main.py first!
#    models.Base.metadata.create_all(bind=engine)  ← remove this

# 3. Generate fresh migration
alembic revision --autogenerate -m "initial tables"

# 4. Apply
alembic upgrade head
```

---

### Everyday workflow after any of the above
```bash
# Every time you change models.py:
alembic revision --autogenerate -m "what you changed"
alembic upgrade head

# Roll back if something went wrong
alembic downgrade -1

# Check current state
alembic current

# See full history
alembic history --verbose
```

You're currently in **Situation 1 or 3** — just `del myapp.db` and run `upgrade head` fresh!