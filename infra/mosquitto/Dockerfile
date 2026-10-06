FROM eclipse-mosquitto:2.0

COPY mosquitto.conf /opt/sentinel/mosquitto.conf
COPY acl /opt/sentinel/acl
COPY entrypoint.sh /usr/local/bin/sentinel-entrypoint.sh

USER root
RUN chmod 755 /usr/local/bin/sentinel-entrypoint.sh \
    && chown -R mosquitto:mosquitto /opt/sentinel /mosquitto/config
USER mosquitto

ENTRYPOINT ["/usr/local/bin/sentinel-entrypoint.sh"]
