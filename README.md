# Arc Store Agentic Debugging Workflow Demo

![Agent dtctl workflow](image/agent-dtctl-workflow.png)

A demo e-commerce store with a React frontend, Spring Boot backend, a Python load generator, and an AI investigation agent workflow powered by dtctl and Dynatrace.

## Quickstart

Here are some short quickstart details to get going as you spin up the codespaces. More specific details are in the link at the bottom of the page.

1) To spin up the environment with GitHub Codespaces, go to **Code > Codespaces > New with options**.

   > **Recommended:** 4-core machine (16 GB RAM) — the Kind cluster runs the full Arc Store stack inside the codespace.

   You'll need:
   - A Dynatrace **Environment ID** — the subdomain from your environment URL, e.g. `abc12345` from `https://abc12345.live.dynatrace.com`
   - A Dynatrace **Environment Type** — typically `live` (or `sprint` / `dev`)
   - A Dynatrace **Operator Token** (`DT_API_TOKEN`) — used by the Dynatrace Operator to manage the lifecycle of all Dynatrace components in the cluster
   - A Dynatrace **Data Ingest Token** (`DT_DATA_INGEST_TOKEN`) with the following scopes:
     - `metrics.ingest`
     - `logs.ingest`
     - `openTelemetryTrace.ingest`

2) The codespace will automatically create a [Kind](https://kind.sigs.k8s.io/) Kubernetes cluster, deploy the Arc Store application, and install the Dynatrace Operator. Verify everything is running:

   ```sh
   kubectl get pods -n arc-store
   ```
   ```sh
   kubectl get pods -n dynatrace
   ```

Let's Get Started...

## [🛒 🤖 Start the AI bug investigation here!](https://dynatrace.github.io/dtctl-ai-bug-demo/)


More details about the project are below including how to build and run the Arc Store locally.

---

## Project layout

```
arc-store/
├── agent/            AI investigation orchestrator + prompt templates
├── backend/          Spring Boot 3.2 + H2
├── frontend/         React (Vite) + nginx
├── load-generator/   Python script
├── k8s/              Kubernetes manifests (namespace: arc-store)
└── build.sh          Build all Docker images
```

## Dependencies

The backend calls the tax-service at the URL configured by the `TAX_SERVICE_URL` environment variable.

- Local development fallback: `http://localhost:8081`
- Kubernetes deployment (configured in `k8s/configmap.yaml`): `http://tax-service.tax-service.svc.cluster.local:8081`

The tax-service is a separate repo deployed in its own Kubernetes namespace, but reachable from this app through the in-cluster DNS service URL above.

## Build Docker images

Run from the `arc-store/` directory:

```bash
./build.sh
```

This builds all three images for `linux/amd64` and `linux/arm64` using `docker buildx`.

## Deploy to Kubernetes

```bash
kubectl apply -f k8s/
```

Wait for pods to be ready:

```bash
kubectl get pods -n arc-store -w
```

## Access locally

```bash
# Store UI
nohup kubectl port-forward svc/arc-frontend 3000:80 -n arc-store > /tmp/arc-frontend-port-forward.log 2>&1 &

# Backend API (direct)
nohup kubectl port-forward svc/arc-backend 8080:8080 -n arc-store > /tmp/arc-backend-port-forward.log 2>&1 &
```

Open http://localhost:3000

## Local development (no Docker)

Start the tax-service first (see its own repo), then:

**Backend:**
```bash
cd backend
mvnw spring-boot:run
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

The frontend dev server will be available at http://localhost:5173/

**Load generator:**
```bash
cd load-generator
pip install -r requirements.txt
python generator.py
```

## Watch load generator logs

```bash
kubectl logs -f deployment/arc-load-generator -n arc-store
```

## API

| Method | Path          | Body                                      | Description       |
|--------|---------------|-------------------------------------------|-------------------|
| GET    | /api/products | —                                         | List all products |
| POST   | /api/orders   | `{ productId, quantity, shippingState }`  | Place an order    |

## Docs

To deploy the docs:

```bash
mkdocs gh-deploy
```

---

## [🛒🤖 Start the AI bug investigation here!](https://dynatrace.github.io/dtctl-ai-bug-demo/)
