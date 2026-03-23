FROM oven/bun:1.3.5-alpine AS deps

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM deps AS build

WORKDIR /app

COPY . .
RUN bun run build

FROM oven/bun:1.3.5

WORKDIR /app

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
ENV ORIGIN=http://localhost:${PORT}

COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules/

EXPOSE ${PORT}

CMD ["bun", "build/index.js"]
