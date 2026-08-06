FROM node:20-slim

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json ./
COPY pnpm-lock.yaml* ./

# Install dependencies (no frozen lockfile since we may not have one)
RUN pnpm install --no-frozen-lockfile

# Copy source
COPY . .

# Build — NEXT_PUBLIC_API_BASE is baked in at build time.
# Render passes envVars as Docker build args automatically.
# Default to the production API URL so local builds work too.
ARG NEXT_PUBLIC_API_BASE=https://prachar-api.onrender.com
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN pnpm build

EXPOSE 3002
CMD ["pnpm", "start"]
