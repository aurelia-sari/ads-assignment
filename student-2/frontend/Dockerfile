FROM nginx:alpine

ENV NGINX_RESOLVER=127.0.0.11 \
    SHARED_FRONTEND_URL=http://shared-frontend:80 \
    STUDENT2_API_URL=http://student-2-api:5102
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY templates/index.html /usr/share/nginx/html/index.html
COPY css/ /usr/share/nginx/html/css/
COPY tabs/ /usr/share/nginx/html/tabs/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80
