FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY templates/index.html /usr/share/nginx/html/index.html
COPY templates/signup.html /usr/share/nginx/html/signup.html

EXPOSE 80
