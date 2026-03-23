FROM oven/bun:1.3.5-alpine AS builder

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY tsconfig.json ./tsconfig.json
COPY src ./src
RUN bun run build

FROM oven/bun:1.3.5-alpine

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup -S app && adduser -S -G app app

COPY --from=builder --chown=app:app /app/dist/index ./index

USER app

ENTRYPOINT ["/app/index"]
