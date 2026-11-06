# System Architecture

## Overview
`movie-rcm-system` is an end-to-end movie discovery and recommendation platform combining modern frontend UI, a robust enterprise backend, high-performance recommendation inference, and an offline AI training pipeline.

```
[ Frontend (Next.js) ]
         │
         ▼
[ Backend (Spring Boot) ] ────▶ [ PostgreSQL / Redis ]
         │
         ▼
[ Recommender Gateway (FastAPI) ]
         │
         ▼
[ AI Models & Vector Index (PyTorch / ONNX / FAISS) ]
```

## Subsystems
1. **Frontend (`/frontend`)**: Next.js App Router, Tailwind CSS, TypeScript.
2. **Backend (`/backend`)**:
   - `springboot`: User accounts, movie catalog, watchlist, transaction/interaction events.
   - `fastapi`: Low-latency real-time recommendation inference and vector search.
3. **AI Pipeline (`/ai`)**: Dataset preprocessing, model architectures (Collaborative Filtering, Two-Tower DSSM, Graph Neural Networks), training pipelines, and offline evaluation benchmarks.
4. **Database (`/database`)**: Migration scripts, schema definitions, and seed data.
5. **Infrastructure (`/infrastructure`)**: Docker configurations for development and deployment.
