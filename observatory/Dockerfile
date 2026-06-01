FROM node:20-alpine AS builder
WORKDIR /app

RUN apk add --no-cache python3 make g++

COPY package*.json ./
RUN npm ci

COPY client ./client
COPY server ./server
RUN npm run build

# ---

FROM node:20-alpine AS runtime
WORKDIR /app

RUN apk add --no-cache python3 make g++

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

EXPOSE 3001
ENV NODE_ENV=production

CMD ["node", "dist/server/index.js"]
