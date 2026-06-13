# =============================================================================
# Enterprise KnowledgeBase — Next.js Frontend Dockerfile
# =============================================================================

FROM node:22-slim AS base

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_ADMIN_API_URL
ARG NEXT_PUBLIC_WORKBENCH_API_URL
ENV NEXT_PUBLIC_ADMIN_API_URL=${NEXT_PUBLIC_ADMIN_API_URL}
ENV NEXT_PUBLIC_WORKBENCH_API_URL=${NEXT_PUBLIC_WORKBENCH_API_URL}

RUN npm run build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r ekb && useradd -r -m -g ekb ekb

COPY --from=builder --chown=ekb:ekb /app/.next/standalone ./
COPY --from=builder --chown=ekb:ekb /app/.next/static ./.next/static
COPY --from=builder --chown=ekb:ekb /app/public ./public

USER ekb

EXPOSE 3000

CMD ["node", "server.js"]
