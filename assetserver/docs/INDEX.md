# Documentation Index

## 🎓 Start Here
- **[Project Report](project-report.md)** — The complete student technical report. Read this first.

## 🔬 Technical Deep-Dives
- [Image Generation Pipeline](pipeline/image-generation-pipeline.md) — DiT mechanics, pipeline stages
- [Asset Family Engines](architecture/asset-family-engines.md) — Per-family generation architecture
- [Workflow Design Justification](pipeline/workflow-design-justification.md) — Model selection and node graph rationale
- [Prompt Architecture](architecture/architecture.md#3-prompt-architecture-templates--python) — 4-layer prompt assembly system

## 🏗️ System Reference
- [Architecture Overview](architecture/architecture.md) — System design, middleware, components
- [Database Schema](architecture/database-schema.md) — ERD, tables, FK strategies
- [Configuration Reference](architecture/configuration-reference.md) — Every config key
- [Storage & Caching](architecture/storage-and-caching.md) — LRU cache, atomic writes

## 🔌 ComfyUI Integration
- [ComfyUI Protocol](architecture/comfyui-protocol.md) — WebSocket + HTTP lifecycle
- [Load Balancer](architecture/load-balancer.md) — Multi-node routing
- [ComfyUI Setup Guide](architecture/comfyui-setup-guide.md) — Hardware, install, models

## 🧰 Operations
- [Static Catalog](architecture/static-catalog.md) — Static asset resolution
- [Font Utilities](architecture/font-utils.md) — Cross-platform font loading
- [Testing Plan](architecture/testing-plan.md) — Test architecture and fixtures

## 🎮 API Users
- **[Server API Reference](guides/server-api.md)** — Concise endpoint reference
- [API Examples](guides/api-examples.md) — Curl examples for all endpoints
- [Leader Prompt Guide](guides/leader-prompt-guide.md) — Writing leader descriptions
- [Tile Prompt Guide](guides/tile-prompt-guide.md) — Structure, object, terrain prompts
- [Unit Prompt Guide](guides/unit-prompt-guide.md) — Unit sprite prompts
- [Validation Prompts](guides/validation-prompts.md) — Pre-built test prompts

## 📋 Project Management
- [Next Steps](project/next_steps.md) — Roadmap and future work
- [Deployment Guide](../DEPLOYMENT.md) — Production deployment
- [Security](../SECURITY.md) — Auth, CORS, rate limiting
