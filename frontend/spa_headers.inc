include /etc/nginx/security_headers.inc;
# Mantine использует inline-стили; скрипты — только свои; договор показывается в iframe srcdoc
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-src 'self' blob: data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
add_header Cache-Control "no-cache" always;
