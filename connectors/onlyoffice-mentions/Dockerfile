# Expected build context: the connectors/ directory (not this subfolder).
# docker build -f onlyoffice-mentions/Dockerfile -t onlyoffice-mentions .   # from connectors/
FROM node:20.17-alpine AS build
WORKDIR /app
COPY tsconfig.base.json /tsconfig.base.json
COPY onlyoffice-mentions/package.json ./
COPY onlyoffice-mentions/tsconfig.json ./
COPY onlyoffice-mentions/src ./src
RUN npm install
RUN npm run build

FROM node:20.17-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY onlyoffice-mentions/package.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
EXPOSE 4004
CMD ["node", "dist/server.js"]
