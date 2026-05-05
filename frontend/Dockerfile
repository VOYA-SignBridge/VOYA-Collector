FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ARG VITE_MIRROR_PREVIEW=1
ARG VITE_SWAP_HANDEDNESS=1
ARG VITE_DEBUG_HANDS=1


ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_MIRROR_PREVIEW=${VITE_MIRROR_PREVIEW}
ENV VITE_SWAP_HANDEDNESS=${VITE_SWAP_HANDEDNESS}
ENV VITE_DEBUG_HANDS=${VITE_DEBUG_HANDS}

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
