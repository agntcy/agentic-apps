# Agent Connect Protocol (ACP) Tutorial Series

Welcome to the Agent Connect Protocol tutorial series! These tutorials will guide you through implementing the Agent Connect Protocol (ACP) using the Agent Gateway Protocol (AGP) as an implementation framework.

## What You'll Learn

By the end of this tutorial series, you'll understand:

1. The architecture and core concepts of Agent Gateway Protocol (AGP)
2. How to build client applications that communicate with remote agents
3. How to implement server-side agent logic
4. Advanced patterns for agent communication and collaboration
5. Best practices for deploying AGP applications

## Tutorial Roadmap

Here's what each tutorial covers:

### [1. Introduction to Agent Gateway Protocol (AGP)](01-intro-to-agp.md)

This tutorial introduces the core concepts of AGP, including:
- The client-gateway-server architecture
- Why distributed agent architecture matters
- Message flow between components
- Setting up your development environment

### [2. Building Your First AGP Client](02-first-agp-client.md)

Learn how to build a client application that communicates with remote agents:
- Setting up a Langgraph-based client
- Connecting to the gateway
- Sending and receiving messages
- Handling errors and edge cases

### [3. Implementing AGP Server Components](03-agp-server.md)

Dive into building server-side agents:
- Creating a FastAPI-based agent server
- Implementing core agent logic
- Processing requests from clients
- Customizing agent behavior

### [4. Advanced Agent Patterns](04-advanced-patterns.md) (Coming Soon)

Explore advanced patterns for agent interactions:
- Tool-using agents
- Multi-agent systems
- Streaming responses
- State management

### [5. Deploying AGP Applications](05-deployment.md) (Coming Soon)

Learn how to deploy AGP applications to production:
- Containerization with Docker
- Security considerations
- Scaling strategies
- Monitoring and observability

## Relationship to Agent Connect Protocol (ACP)

The Agent Connect Protocol (ACP) defines standards for agent communication, including:

1. **Authentication and Authorization**: How callers authenticate with agents
2. **Configuration**: How to configure remote agents
3. **Invocation**: How to invoke agents with input
4. **Output Retrieval**: How to get results from agents
5. **Capabilities and Schema Definitions**: How to discover agent capabilities
6. **Error Handling**: Standardized error reporting

The Agent Gateway Protocol (AGP) provides a concrete implementation of these standards, with specific APIs, message formats, and interaction patterns.

## Visual Reference

For a visual overview of the AGP architecture, see our [AGP Architecture Visualization](agp-architecture.md).

## Getting Help

If you encounter issues while working through these tutorials:

1. Check the [Troubleshooting](#troubleshooting) sections in each tutorial
2. Refer to the complete examples in the repository
3. Join our community Discord for support

## Next Steps

Ready to start learning? Begin with [Introduction to Agent Gateway Protocol (AGP)](01-intro-to-agp.md).

Happy building! 