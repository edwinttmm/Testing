FROM node:20-alpine

# Install curl for healthcheck and bash for better script support
RUN apk add --no-cache curl bash

WORKDIR /app

# Set environment variables for faster startup and production readiness
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NODE_ENV=development
ENV SKIP_PREFLIGHT_CHECK=true
ENV TSC_COMPILE_ON_ERROR=true
ENV FAST_REFRESH=true
ENV GENERATE_SOURCEMAP=false
ENV REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_WS_URL=ws://localhost:8000
ENV REACT_APP_ENVIRONMENT=development
ENV CI=false
ENV DOCKER=true

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies with better error handling
RUN npm ci --legacy-peer-deps --no-audit --no-fund --silent

# Copy source code
COPY . .

# Health check to ensure the app is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

EXPOSE 3000

# Copy and use start script
COPY start.sh ./
RUN chmod +x start.sh

# Start with custom script
CMD ["./start.sh"]