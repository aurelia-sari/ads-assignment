FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY templates/index.html /usr/share/nginx/html/index.html
COPY templates/signup.html /usr/share/nginx/html/signup.html
COPY templates/signin.html /usr/share/nginx/html/signin.html
COPY templates/verify-pending.html /usr/share/nginx/html/verify-pending.html
COPY templates/session.js /usr/share/nginx/html/session.js

EXPOSE 80
