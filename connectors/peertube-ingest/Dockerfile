# Build context attendu : le repertoire connectors/ (pas ce sous-dossier).
# docker build -f peertube-ingest/Dockerfile -t peertube-ingest .   # depuis connectors/
FROM node:20.17-alpine AS build
WORKDIR /app
COPY tsconfig.base.json /tsconfig.base.json
COPY peertube-ingest/package.json ./
COPY peertube-ingest/tsconfig.json ./
COPY peertube-ingest/src ./src
RUN npm install
RUN npm run build

FROM node:20.17-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY peertube-ingest/package.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 4005
# Le service HTTP (webhook temps reel) est la commande par defaut ; le mode batch
# s'invoque separement dans le meme conteneur : `node dist/batch.js` (cf. README, cron).
CMD ["node", "dist/server.js"]
