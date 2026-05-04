## ADDED Requirements

### Requirement: Web container Dockerfile
The system SHALL provide a multi-stage Dockerfile at `web/Dockerfile` that builds the frontend application and serves it via nginx.

#### Scenario: Builder stage
- **WHEN** the Dockerfile builder stage executes
- **THEN** it SHALL use a Node.js base image, copy `package.json` and `package-lock.json`, run `npm ci` for reproducible dependency installation, copy the remaining source files, and run `npx vite build` to produce optimized static assets in a `dist/` directory

#### Scenario: Runtime stage
- **WHEN** the Dockerfile runtime stage executes
- **THEN** it SHALL use an nginx base image, copy the `dist/` directory from the builder stage to `/usr/share/nginx/html`, and copy a custom `nginx.conf` into the nginx configuration directory

#### Scenario: Non-root user
- **WHEN** the runtime container starts
- **THEN** the nginx process SHALL run as a non-root user

#### Scenario: Exposed port
- **WHEN** the Dockerfile is inspected
- **THEN** it SHALL declare `EXPOSE 3000`

#### Scenario: Health check
- **WHEN** the container runtime evaluates the health check
- **THEN** the Dockerfile SHALL define a `HEALTHCHECK` instruction that runs `curl -f http://localhost:3000/health || exit 1` at a reasonable interval

### Requirement: Nginx configuration
The system SHALL provide an `nginx.conf` file in the `web/` directory that serves the SPA, proxies API requests, and applies performance optimizations.

#### Scenario: Static file serving
- **WHEN** a request arrives for a static asset (e.g., `/assets/main.abc123.js`)
- **THEN** nginx SHALL serve the file from `/usr/share/nginx/html`

#### Scenario: SPA fallback routing
- **WHEN** a request arrives for a path that does not match a static file (e.g., `/repos/42/docs`)
- **THEN** nginx SHALL serve `/index.html` via a `try_files $uri $uri/ /index.html` directive to support client-side routing

#### Scenario: API reverse proxy
- **WHEN** a request arrives matching the path prefix `/api/*`
- **THEN** nginx SHALL proxy the request to the upstream `autodoc-api:8080`, stripping the `/api` prefix so that `/api/repositories` is forwarded as `/repositories`

#### Scenario: Gzip compression
- **WHEN** the nginx configuration is applied
- **THEN** gzip compression SHALL be enabled for text-based content types including `text/html`, `text/css`, `application/javascript`, and `application/json`

#### Scenario: Cache-control headers for hashed assets
- **WHEN** a request matches a static asset with a hash in its filename (e.g., files under `/assets/`)
- **THEN** nginx SHALL set `Cache-Control: public, max-age=31536000, immutable` to enable long-term browser caching

#### Scenario: Cache-control headers for HTML
- **WHEN** a request serves `index.html`
- **THEN** nginx SHALL set `Cache-Control: no-cache` to ensure the browser always checks for updated entry points

### Requirement: Docker Compose web service
The system SHALL add a `web` service to the Docker Compose configuration so the dashboard is accessible alongside the existing API and infrastructure services.

#### Scenario: Web service definition
- **WHEN** the Docker Compose file is inspected
- **THEN** it SHALL contain a `web` service that builds from `web/Dockerfile`, maps host port 3000 to container port 3000, and declares `depends_on` the `api` service

#### Scenario: Dashboard accessibility
- **WHEN** the full Docker Compose stack is running
- **THEN** the dashboard SHALL be accessible at `http://localhost:3000`

#### Scenario: API reachability from web container
- **WHEN** the web container starts within the Docker Compose network
- **THEN** it SHALL be able to reach the API service at the hostname `autodoc-api` on port 8080 (or the service name defined for the API) for reverse proxy requests

### Requirement: Makefile targets for web development
The system SHALL add Makefile targets in `deployment/Makefile` for web frontend development, production builds, and Docker image builds.

#### Scenario: Development server target
- **WHEN** the operator runs `make web-dev`
- **THEN** the Makefile SHALL start the Vite development server with hot module replacement

#### Scenario: Production build target
- **WHEN** the operator runs `make web-build`
- **THEN** the Makefile SHALL execute a production Vite build, producing optimized static assets in the `web/dist/` directory

#### Scenario: Docker build target
- **WHEN** the operator runs `make web-docker`
- **THEN** the Makefile SHALL build the Docker image from `web/Dockerfile`

### Requirement: Vite development proxy configuration
The system SHALL configure the Vite development server to proxy API requests to the local backend, enabling frontend development without the Docker Compose stack.

#### Scenario: API proxy in development
- **WHEN** the Vite development server is running and a request is made to `/api/*`
- **THEN** Vite SHALL proxy the request to `http://localhost:8080`, stripping the `/api` prefix, so that `/api/repositories` is forwarded as `http://localhost:8080/repositories`
