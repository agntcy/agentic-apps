# Google ADK Integration (Draft)

SHADI exposes a Python extension module for secret access, SQLCipher memory,
and sandbox execution so ADK agents can run without handling OS keychains
directly.

## Recommended example app
The agentic-apps tourist scheduling system includes ADK agents and a SLIM
configuration already. The Tourist and Guide agents are good candidates for
first integration with SHADI.

## Suggested flow
1. Create a `PySessionContext` for the agent.
2. Configure `ShadiStore.set_verifier()` with a DID/VC verification callback.
3. Call `ShadiStore.verify_session()` with the DID/VC presentation.
4. Use `ShadiStore` to fetch secrets during tool execution.
5. Use `SqlCipherMemoryStore` for encrypted local memory when needed.
6. Run under the sandbox using `run_sandboxed` or the JSON policy runner.

## Key provisioning
Use `shadictl` to ingest OpenPGP keys and derive agent DIDs without invoking OS `gpg`:

```bash
cargo run -p shadictl -- \
	put-key --key human/gpg --in /path/to/human-secret.asc

cargo run -p shadictl -- \
	derive-agent-did --secret human/gpg --name agent-a --prefix agents
```
