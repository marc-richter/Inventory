# --- Build-Stufe ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci baut exakt die in der package-lock.json festgehaltenen Versionen -
# anders als npm install, das bei jedem Bau neuere Versionen ziehen kann.
RUN npm ci
COPY . .
RUN npm run build

# --- Laufzeit-Stufe: statische Dateien via nginx ausliefern, /api zum Backend proxien ---
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
