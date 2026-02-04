# Simplified Moltbook Architecture - Visual Flow

## System Diagram (Updated)

```
┌──────────────────────────────────────────────────────────────┐
│                           USER                               │
│                    (Makes HTTP Request)                      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ POST /agent/prompt
                         │ {"community_urls": ["..."]}
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  SUPERVISOR                                 │
│                  (Port 8003)                                │
│  ┌────────────────────────────────────────────────────┐     │
│  │  LangGraph State Machine (UNCHANGED)               │     │
│  │  - supervisor: Validate URLs                       │     │
│  │  - assign_communities: Distribute to workers       │     │
│  │  - collect_results: Aggregate                      │     │
│  │  - retry_failed: Error handling                    │     │
│  └────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ A2A via NATS
                         │ "Scrape: https://..."
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                     NATS MESSAGE BROKER                      │
│                     (Port 4222)                              │
│  Topic: agent/news/scraper                                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ WORKER 1     │  │ WORKER 2     │  │ WORKER N     │
│ (Port 9002)  │  │              │  │              │
│              │  │              │  │              │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │
│ │  Scrape  │ │  │ │  Scrape  │ │  │ │  Scrape  │ │
│ │  Top 10  │ │  │ │  Top 10  │ │  │ │  Top 10  │ │
│ │  Posts   │ │  │ │  Posts   │ │  │ │  Posts   │ │
│ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │
│      │       │  │      │       │  │      │       │
│      ▼       │  │      ▼       │  │      ▼       │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │
│ │ Analyze  │ │  │ │ Analyze  │ │  │ │ Analyze  │ │
│ │ with LLM │ │  │ │ with LLM │ │  │ │ with LLM │ │
│ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │
│      │       │  │      │       │  │      │       │
│      ▼       │  │      ▼       │  │      ▼       │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │
│ │ Generate │ │  │ │ Generate │ │  │ │ Generate │ │
│ │ 1-2 Para │ │  │ │ 1-2 Para │ │  │ │ 1-2 Para │ │
│ │ Summary  │ │  │ │ Summary  │ │  │ │ Summary  │ │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       │ A2A Response    │                 │
       └────────────────┬┴─────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  MOLTBOOK SUPERVISOR                         │
│  - Receives all worker summaries                             │
│  - Aggregates into final report                              │
│  - Returns to user                                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ HTTP Response
                         │ {response: "...", session_id: "..."}
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                           USER                               │
│              (Receives community summaries)                  │
└──────────────────────────────────────────────────────────────┘
```

## Workflow Timeline

```
Time   Actor               Action
──────────────────────────────────────────────────────────────
00:00  User                POST /agent/prompt
00:01  Supervisor          Parse & validate URLs
00:02  Supervisor          A2A → Worker 1: "Scrape: https://..."
00:03  Worker 1            Receive A2A message
00:04  Worker 1            scrape_moltbook_tool() [mock data]
00:05  Worker 1            analyze_posts_tool() [LLM call]
00:10  Worker 1            Generate 1-2 paragraph summary
00:11  Worker 1            A2A → Supervisor: return summary
00:12  Supervisor          Receive worker summary
00:13  Supervisor          Format final report
00:14  Supervisor          HTTP → User: return response
00:15  User                Display results
```

## Data Flow

```
INPUT                    PROCESSING                   OUTPUT
────────────────────────────────────────────────────────────────

Community URL            Worker scrapes               10 Posts
https://moltbook.com  →  top posts               →   [{id, title,
/m/technology                                          upvotes, ...}]
                                                              │
                                                              ▼
                         Worker analyzes               Summary Text
                         with LLM                →    "The community is
                         (1 API call)                  discussing..."
                                                              │
                                                              ▼
                         Worker formats                Final Report
                         final summary            →   # Community Summary
                                                       **Time:** 24 hours
                                                       **Posts:** 10
                                                       [1-2 paragraphs]
```

```
Supervisor
    ↓ A2A (1 call per community)
Worker (does everything)
    ↓
Results
```

## Component Interaction

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  Component   │  Supervisor  │   Worker     │     NATS     │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ Supervisor   │      -       │  A2A Send    │  Publish     │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ Worker       │  A2A Reply   │      -       │  Subscribe   │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ NATS         │  Subscribe   │  Sub/Pub     │      -       │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ LLM          │      -       │  API Call    │      -       │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ User         │  HTTP        │      -       │      -       │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

## Worker Internal Flow

```
┌─────────────────────────────────────────────────────────┐
│              COMMUNITY WORKER AGENT                     │
│                                                         │
│  1. Receive A2A Message                                 │
│     ↓                                                   │
│  2. Extract URL from message                            │
│     ↓                                                   │
│  3. Call scrape_moltbook_tool(url)                      │
│     │                                                   │
│     └──→ Returns 10 posts (mock data)                   │
│          {posts: [...]}                                 │
│     ↓                                                   │
│  4. Call analyze_posts_tool(posts)                      │
│     │                                                   │
│     ├──→ Build LLM prompt                               │
│     │    "Analyze these 10 posts..."                    │
│     │                                                   │
│     ├──→ Call LLM API                                   │
│     │    llm.complete(prompt)                           │
│     │                                                   │
│     └──→ Returns analysis text                          │
│          "The community is discussing..."               │
│     ↓                                                   │
│  5. Format final summary                                │
│     │                                                   │
│     └──→ Combine analysis + metadata                    │
│          # Community Summary                            │
│          [Analysis paragraph]                           │
│          Top Post: [title]                              │
│     ↓                                                   │
│  6. Return via A2A to Supervisor                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Scaling (10 Workers)

```
                    Supervisor
                        │
                        │ NATS Load Balancing
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
Worker 1            Worker 5            Worker 10
    │                   │                   │
Community 1         Community 5         Community 10
    │                   │                   │
LLM Call            LLM Call            LLM Call
    │                   │                   │
Summary 1           Summary 5           Summary 10
    │                   │                   │
    └───────────────────┴───────────────────┘
                        │
                  Final Report
```

## Key Simplification Benefits

1. ✅ **Fewer hops**: 2 A2A calls instead of 6+ (per community)
2. ✅ **Faster**: Single LLM call instead of multiple
3. ✅ **Simpler logic**: Linear flow in worker
4. ✅ **Less infrastructure**: 2 containers instead of 3
5. ✅ **Same output quality**: 1-2 paragraph summaries
6. ✅ **Same scalability**: Can run 10+ workers
7. ✅ **Supervisor unchanged**: LangGraph orchestration kept