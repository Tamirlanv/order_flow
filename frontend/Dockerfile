FROM node:24-alpine AS build
ENV SCARF_ANALYTICS=false
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-http.conf /etc/nginx/orderflow/server.conf
COPY nginx-security.conf /etc/nginx/orderflow/security.conf
COPY nginx-proxy.conf /etc/nginx/orderflow/proxy.conf
COPY nginx-routes.conf /etc/nginx/orderflow/routes.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
