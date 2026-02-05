# Makefile for running logistics and farm services with uv
# Each target sets PYTHONPATH to project root before invoking uv

# Variables
PYTHONPATH := $(CURDIR)
UV = PYTHONPATH=$(PYTHONPATH) uv run

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  weather-mcp         - Run weather MCP server"
	@echo "  payment-mcp         - Run payment MCP server"
	@echo "  news-supervisor      - Run news supervisor"
	@echo "  news-scraper         - Run news scraper worker"

.PHONY: weather-mcp
weather-mcp:
	$(UV) agents/mcp_servers/weather_service.py

.PHONY: payment-mcp
payment-mcp:
	$(UV) agents/mcp_servers/payment_service.py

.PHONY: news-supervisor
news-supervisor:
	$(UV) agents/supervisors/news/main.py

.PHONY: news-scraper
news-scraper:
	$(UV) agents/news/scraper/server.py
