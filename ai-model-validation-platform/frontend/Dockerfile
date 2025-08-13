FROM node:20-alpine

WORKDIR /app

# Install dependencies in order with better error handling
COPY package*.json ./

# Clean install with verbose logging and error handling
RUN set -x && \
    npm cache clean --force && \
    npm install --verbose --no-audit --no-fund --legacy-peer-deps && \
    npm list @craco/craco || echo "Craco not found in list" && \
    ls -la node_modules/.bin/craco || echo "Craco binary not found" && \
    which craco || echo "Craco not in PATH"

# Copy source code
COPY . .

EXPOSE 3000

# Use npx to ensure craco is found, with fallback to react-scripts
CMD ["sh", "-c", "npx craco start || (echo 'Craco failed, trying react-scripts...' && npx react-scripts start)"]