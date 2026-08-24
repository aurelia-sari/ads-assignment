FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy_headers.conf /etc/nginx/proxy_headers.conf
COPY index.html /usr/share/nginx/html/index.html
COPY css/ /usr/share/nginx/html/shared/css/
COPY js/ /usr/share/nginx/html/shared/js/
COPY assets/ /usr/share/nginx/html/shared/assets/

EXPOSE 80
