FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY templates/index.html /usr/share/nginx/html/index.html
COPY templates/signup.html /usr/share/nginx/html/signup.html
COPY templates/signin.html /usr/share/nginx/html/signin.html
COPY templates/verify-pending.html /usr/share/nginx/html/verify-pending.html
COPY templates/forgot-password.html /usr/share/nginx/html/forgot-password.html
COPY templates/forgot-password-pending.html /usr/share/nginx/html/forgot-password-pending.html
COPY templates/reset-password.html /usr/share/nginx/html/reset-password.html
COPY templates/logout.html /usr/share/nginx/html/logout.html
COPY templates/session.js /usr/share/nginx/html/session.js

EXPOSE 80
