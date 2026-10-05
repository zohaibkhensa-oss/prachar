FROM node:20-slim

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy workspace lockfile and package files
# Build context is repo root so we can access the workspace lockfile
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web-v2/package.json ./apps/web-v2/

# Install dependencies for web-v2 only — frozen lockfile for reproducible builds
RUN pnpm install --frozen-lockfile --filter web-v2...

# Copy source
COPY apps/web-v2 ./apps/web-v2

WORKDIR /app/apps/web-v2

# Build — NEXT_PUBLIC_API_BASE is baked in at build time.
# Override with --build-arg NEXT_PUBLIC_API_BASE=https://api.curv.app
ARG NEXT_PUBLIC_API_BASE=https://api.curv.app
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN pnpm build

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 3002
CMD ["pnpm", "start"]
