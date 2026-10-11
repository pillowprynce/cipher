# logs/

One log file per run: `logs/<run-id>.log`. Records every phase, tool call,
denial, spawn event, verifier verdict, and the final spawn tree.

Logs never contain API keys (the key is only ever sent as an HTTPS header
and is never printed or persisted).
