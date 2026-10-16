#!/bin/sh

# Inject runtime environment variables into index.html for 12-Factor App deployment

# 1. Base Path
# Mặc định là "/" nếu không truyền biến VITE_BASE_PATH
BASE_PATH="${VITE_BASE_PATH:-/}"

# Đảm bảo đường dẫn luôn kết thúc bằng "/"
case "$BASE_PATH" in
  */) ;;
  *) BASE_PATH="$BASE_PATH/" ;;
esac

echo "=> Injecting VITE_BASE_PATH: $BASE_PATH"
sed -i "s|__VITE_BASE_PATH__|$BASE_PATH|g" /usr/share/nginx/html/index.html

# 2. API URL
API_URL="${VITE_API_URL:-}"
echo "=> Injecting VITE_API_URL: $API_URL"
sed -i "s|__VITE_API_URL__|$API_URL|g" /usr/share/nginx/html/index.html

# Start Nginx
echo "=> Starting Nginx..."
exec "$@"
