# Expected build context: the connectors/ directory (not this subfolder).
# docker build -f peertube-ingest/Dockerfile -t peertube-ingest .   # from connectors/
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
# The HTTP service (real-time webhook) is the default command; batch mode
# is invoked separately in the same container: `node dist/batch.js` (see README, cron).
CMD ["node", "dist/server.js"]
