# Movie Recommendation System (`movie-rcm-system`)

An end-to-end cinematic movie discovery and recommendation platform architected as a modular monorepo.

---

## 📁 Project Structure

```text
movie-rcm-system/
│
├── frontend/                     # Next.js Web Application
│   ├── app/                      # App router pages & layouts
│   ├── components/               # Shared reusable UI components
│   ├── features/                 # Feature-specific modules (movies, search, profile, etc.)
│   ├── lib/                      # Utilities & API helpers
│   ├── types/                    # TypeScript interfaces
│   ├── package.json              # Frontend dependencies & scripts
│   ├── next.config.ts            # Next.js configuration
│   ├── tailwind.config.ts        # Tailwind CSS configuration
│   └── tsconfig.json             # TypeScript configuration
│
├── backend/                      # Backend microservices
│   ├── springboot/               # Core business logic, auth & catalog management (Java/Spring Boot)
│   └── fastapi/                  # Real-time recommendation inference gateway (Python/FastAPI)
│
├── ai/                           # AI & Machine Learning pipelines
│   ├── models/                   # Model architectures & exported artifacts (PyTorch/ONNX)
│   ├── training/                 # Training routines & hyperparameter tuning
│   ├── datasets/                 # Preprocessing & feature engineering pipelines
│   └── evaluation/               # Offline evaluation metrics & benchmarks
│
├── database/                     # Database management
│   ├── migrations/               # Schema migration scripts (SQL / Liquibase / Flyway)
│   ├── seeds/                    # Development & test seed data
│   └── schema/                   # DDL schemas and ER diagrams
│
├── infrastructure/               # DevOps & Containerization
│   └── docker-compose.yml        # Local development multi-container orchestration
│
├── docs/                         # System architecture & documentation
│   └── architecture.md           # High-level architecture and component flow
│
├── .github/                      # CI/CD & GitHub automation
│   └── workflows/
│       └── ci.yml                # Automated test & build pipeline
│
├── .gitignore                    # Monorepo gitignore rules
└── README.md                     # Root project documentation
```

---

## 🚀 Quick Start

### 1. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 2. Infrastructure (PostgreSQL & Redis)
```bash
cd infrastructure
docker compose up -d
```

### 3. Backend Services
- **Spring Boot**: See [backend/springboot/README.md](backend/springboot/README.md)
- **FastAPI**: See [backend/fastapi/README.md](backend/fastapi/README.md)

### 4. AI Pipelines
- See [ai/README.md](ai/README.md)
