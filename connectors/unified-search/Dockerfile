# Build context attendu : le repertoire connectors/ (pas ce sous-dossier).
# docker build -f unified-search/Dockerfile -t unified-search .   # depuis connectors/
FROM node:20.17-alpine AS build
WORKDIR /app
COPY tsconfig.base.json /tsconfig.base.json
COPY unified-search/package.json ./
COPY unified-search/tsconfig.json ./
COPY unified-search/src ./src
RUN npm install
RUN npm run build

FROM node:20.17-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY unified-search/package.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 4002
CMD ["node", "dist/server.js"]
