FROM mcr.microsoft.com/dotnet/runtime:6.0
ENV INSTALL_PATH="/var/www/linguard" \
    DATA_PATH="/var/www/linguard/data" \
    EXPORTED_PATH="/data"
COPY dist/linguard-docker.tar.gz linguard.tar.gz
RUN mkdir linguard && tar -xf linguard.tar.gz -C linguard
WORKDIR linguard
RUN chmod +x ./install.sh && ./install.sh
WORKDIR $EXPORTED_PATH
RUN rm -rf /linguard*

EXPOSE 8080

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD /bin/bash /entrypoint.sh
