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

# Build — pass API URL as build arg so NEXT_PUBLIC_ var is baked in
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN pnpm build

EXPOSE 3002
CMD ["pnpm", "start"]
