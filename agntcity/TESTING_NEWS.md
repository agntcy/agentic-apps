---

## News Supervisor & Scraper System

A supervisor-worker agent system for scraping and summarizing news articles. The supervisor orchestrates URL assignment, rate limiting, and retries, while worker agents handle scraping and summarization.

### Quick Start

**Docker Compose:**
```bash
docker compose down
docker compose up nats news-supervisor news-scraper
```

**Local Development:**
```bash
# Terminal 1: NATS
docker compose up nats

# Terminal 2: Scraper worker
make news-scraper

# Terminal 3: Supervisor
make news-supervisor
```

**Services:** Supervisor `http://localhost:8001`, Scraper `http://localhost:9001`

### Files Changed

- **Supervisor**: Created `agents/supervisors/news/` with LangGraph workflow, A2A tools, and FastAPI server
- **Worker**: Created `agents/news/scraper/` with A2A server, agent executor, and placeholder scraping logic
- **Infrastructure**: Added Dockerfiles, docker-compose services, and Makefile targets

### Testing

```bash
# Health check
curl http://127.0.0.1:8001/health

# Test scraping
curl -X POST http://127.0.0.1:8001/agent/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Scrape these sites", "urls": ["https://example.com"]}'
```

### Common Issues

- **NATS connection errors**: Ensure NATS is running and endpoint is `nats://nats:4222` in Docker (not `localhost`)
- **KeyError `'urls_to_scrape'`**: Fixed - state keys now initialized with defaults
- **"No URLs processed"**: Expected - scraper returns placeholder until Person B implements actual scraping

### Architecture

Supervisor handles URL extraction, assignment with rate limiting (1s delay), retries (max 3), and result aggregation. Worker receives URLs via A2A/NATS, scrapes content (TODO), and summarizes with LLM.

### Next Steps

1. **Person B**: Implement web scraping in `agents/news/scraper/agent.py`
2. **Person C**: Add storage/logging MCP server
3. Add ranking/aggregation logic for articles
