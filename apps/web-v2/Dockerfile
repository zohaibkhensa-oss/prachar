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

# Build
RUN pnpm build

EXPOSE 3002
CMD ["pnpm", "start"]
