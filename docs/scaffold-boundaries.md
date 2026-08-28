# Foundation scaffold boundaries

This repository separates future work into five root-level areas:

- `contracts/` owns implementation-neutral, versioned shared contracts and deterministic fixtures. It depends on no application package, AWS SDK, or infrastructure definition.
- `frontend/` owns the desktop client and client-side tooling. It may consume published or derived contract types only; it must not import Python backend source, CDK infrastructure, Lambda handlers, or DynamoDB/AWS implementation code.
- `backend/` owns serverless domain code, adapters, handlers, backend tests, tooling, and infrastructure definitions. It may consume contract semantics but must not redefine contracts.
- `docs/` owns repository guidance and architecture documentation.
- `scripts/` owns repeatable local verification and developer commands.

Dependency direction is one way: implementation boundaries may consume the stable contract boundary, while contracts remain independent of implementation. Frontend and backend do not import one another.

This scaffold intentionally creates no application behavior, Vite or Python bootstrap, CDK application, AWS resource, contract schema, market-data adapter, dashboard, AI capability, scoring capability, authentication, or trade-execution capability.
