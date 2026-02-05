# Agent Directory Integration Guide

This guide demonstrates how to integrate **coffeeAgntcy lungo** with **[agntcy dir](https://github.com/agntcy/dir)** for automated agent discovery and management.

## Overview

The integration enables automatic translation and publication of all lungo agent A2A cards to a local agntcy directory service. 

## Quick Start

### 1. Start the Directory Service

First, launch the agntcy directory API server, directory MCP server and registry:

```bash
docker-compose up -d dir-api-server dir-mcp-server zot
```

This starts:
- `dir-api-server`: The directory API service for agent record management
- `dir-mcp-server`: The MCP server in front of the API service
- `zot`: OCI-compliant registry for storing agent artifacts

### 2. Install Development Dependencies

Install the required development dependencies for the integration scripts:

```bash
uv sync --extra dev
```

### 3. Publish Agent Records

Run the automated agent record publication script:

```bash
./scripts/publish_agent_records.sh
```

This script will:
- Scan the `agents/` directory for A2A card definitions
- Convert agent metadata to OASF format
- Upload records to the running directory service
- Generate content identifiers (CIDs) for published records

### 4. Verify and Interact with Records

After publishing, you can:

1. **View published records**: Check the generated `published_cids.json` file for CIDs of your published agents
2. **Interact with directory**: Use the `dirctl` CLI tool to query and manage directory records


```
{
  "Brazil Coffee Farm": "baeareiem5tc4gmtdhg74g5fmehlda4uvikfinlfpkmndj5jmv2zzojeume",
  "Vietnam Coffee Farm": "baeareiahesjf46pm7uvd7pupj66s6zppxot3arffaeshjhramjrinn3pi4",
  "Colombia Coffee Farm": "baeareib74t6ozgzo3j3mlkertldtxn45d4rj5pyfridujs3ycmgnvaphai",
  "Accountant agent": "baeareighwgck5fbup3d5czp2bkskqeu4veot6r3uyq53q6xsji4fw3n3oi",
  "Tatooine Farm agent": "baeareienn42cucclv7eus36vxblixskdvrc74zuw5t4iaptp4g357lzayu",
  "Logistics Helpdesk": "baeareibjql2cv3kmygsn2ofor3myoc3ar44m7lszo36ae5jp6aonlky2zq",
  "Shipping agent": "baeareifej6zgoe6o2mnlycgwwapdjit7dyaydnsayx5y3wbplbcmovr7w4"
}
```

```bash
# Example: Pull an agent record from cid
dirctl pull baeareiem5tc4gmtdhg74g5fmehlda4uvikfinlfpkmndj5jmv2zzojeume
```

For detailed `dirctl` usage, see the [CLI documentation](https://github.com/agntcy/dir/tree/main/cli).