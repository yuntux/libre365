# Build context attendu : le repertoire connectors/ (pas ce sous-dossier), pour que
# tsconfig.base.json partage soit accessible : `docker build -f notification-hub/Dockerfile .`
FROM node:20.17-alpine AS build
WORKDIR /app
COPY tsconfig.base.json /tsconfig.base.json
COPY notification-hub/package.json ./
COPY notification-hub/tsconfig.json ./
COPY notification-hub/src ./src
RUN npm install
RUN npm run build

FROM node:20.17-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY notification-hub/package.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 4001
CMD ["node", "dist/server.js"]
