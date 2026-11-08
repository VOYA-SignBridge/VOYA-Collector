# Ảnh gốc ghim theo DIGEST, không chỉ theo tag. Tag `3.11-slim` di chuyển vài lần mỗi
# tháng; mỗi lần nó di chuyển thì mọi lớp phía sau (torch/CUDA, 4,3 GB nén) bị dựng lại
# với digest mới, và máy chạy web phải tải lại cả khối thay vì vài chục MB mã.
# Dependabot (.github/dependabot.yml) mở PR khi có digest mới: cập nhật có chủ ý.
FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS builder

WORKDIR /app

ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build

FROM nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add entrypoint script
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
