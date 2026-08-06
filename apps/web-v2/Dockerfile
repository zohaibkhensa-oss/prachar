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

# Build — pass NEXT_PUBLIC_ vars as build args so they're baked into the bundle
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
ARG NEXT_PUBLIC_APPLE_CLIENT_ID
ARG NEXT_PUBLIC_APPLE_REDIRECT_URI

ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID
ENV NEXT_PUBLIC_APPLE_CLIENT_ID=$NEXT_PUBLIC_APPLE_CLIENT_ID
ENV NEXT_PUBLIC_APPLE_REDIRECT_URI=$NEXT_PUBLIC_APPLE_REDIRECT_URI

RUN pnpm build

EXPOSE 3002
CMD ["pnpm", "start"]
