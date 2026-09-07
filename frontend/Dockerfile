# Step 8: containerizes the Step 6 frontend for deployment. Not used by
# the dev docker-compose.yml (that setup expects `npm run dev` on the
# host, per frontend/README.md) — this is for docker-compose.prod.yml.
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes VITE_* env vars into the bundle at build time — there is no
# runtime env for a static build, so the API's public URL has to be known
# here, not just at container-run time. docker-compose.prod.yml passes it
# as a build arg.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
