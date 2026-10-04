# Hospital Workflow Agent - Frontend

React + TypeScript + Vite dashboard for hospital operations (beds, staff, scheduling,
emergency response and the AI assistant). Talks to the FastAPI backend through `/api`
(proxied to `http://localhost:8000` in development).

## Development

```bash
npm install
npm run dev      # http://localhost:5173
```

## Build

```bash
npm run build    # outputs to dist/
npm run lint
```

## Docker

```bash
docker build -t hwa-frontend .
```

The nginx image proxies `/api/` to `http://backend:8000/`.

Decision support only - synthetic data, not for clinical use.
