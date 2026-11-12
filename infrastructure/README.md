# Infrastructure & Deployment

This directory contains containerization, orchestration, and reverse-proxy configuration files for both **Java Main** and **Python Main** architectures backed by **MySQL 8.0**.

## Files
- `docker-compose.yml`: Full multi-container stack for **Java Main** (`Spring Boot :8080`, `FastAPI AI :8000`, `Next.js :3000`, `MySQL 8.0 :3306`, `Redis :6379`, and `Nginx :80`).
- `docker-compose.python-main.yml`: Override file for **Python Main** (`FastAPI Unified Backend + AI :8000`, `Next.js :3000`, `MySQL 8.0 :3306`, `Redis :6379`, and `Nginx :80`).
- `nginx/default.conf`: Nginx reverse proxy routing `/api/*` to Spring Boot and AI routes to FastAPI.
- `nginx/python-main.conf`: Nginx reverse proxy routing all `/api/*` traffic to FastAPI in Python Main mode.
