FROM node:18-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package*.json ./

# Clear npm cache and install with exact versions
RUN npm cache clean --force && \
    npm ci --only=production --no-audit --no-fund && \
    npm install --save-dev @craco/craco@^7.1.0 && \
    npm list @craco/craco

# Copy source code
COPY . .

EXPOSE 3000

# Start with explicit PATH and verification
CMD ["sh", "-c", "ls -la node_modules/.bin/craco && npm start"]