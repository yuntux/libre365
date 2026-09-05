# Build context attendu : le repertoire connectors/ (pas ce sous-dossier).
# docker build -f presence-aggregator/Dockerfile -t presence-aggregator .   # depuis connectors/
FROM node:20-alpine AS build
WORKDIR /app
COPY tsconfig.base.json /tsconfig.base.json
COPY presence-aggregator/package.json ./
COPY presence-aggregator/tsconfig.json ./
COPY presence-aggregator/src ./src
RUN npm install
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY presence-aggregator/package.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 4003
CMD ["node", "dist/server.js"]
