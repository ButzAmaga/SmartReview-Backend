my-ai-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point: Initializes FastAPI & Lifespan
│   ├── database.py          # SQLAlchemy engine & SessionLocal setup
│   ├── models.py            # Database Tables (SQLAlchemy)
│   ├── schemas.py           # Data Validation (Pydantic)
│   ├── crud.py              # Database Create/Read/Update/Delete logic
│   ├── dependencies.py      # Auth & DB session helpers
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── engine.py        # Model loading & inference logic
│   │   └── processor.py     # Data pre/post-processing
│   └── routers/
│       ├── __init__.py
│       ├── users.py         # User & Auth endpoints
│       └── predictions.py   # Model inference endpoints
├── models/                  # Storage for weight files (.pth, .pkl, .h5)
│   └── model_v1.pth
├── tests/                   # Pytest folder
├── .env                     # Database URLs & Secret Keys
├── .gitignore
├── Dockerfile               # For production deployment
└── requirements.txt         # FastAPI, Uvicorn, SQLAlchemy, Torch/Sklearn
