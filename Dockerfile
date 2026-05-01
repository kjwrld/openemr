# OpenEMR with Clinical Co-Pilot Integration
# Extends official OpenEMR image with chat widget integration

FROM openemr/openemr:latest

# Copy modified demographics.php with 🤖 chat widget button
COPY interface/patient_file/summary/demographics.php /var/www/localhost/htdocs/openemr/interface/patient_file/summary/demographics.php

# Ensure correct permissions
RUN chown -R apache:root /var/www/localhost/htdocs/openemr/interface/patient_file/summary/demographics.php && \
    chmod 644 /var/www/localhost/htdocs/openemr/interface/patient_file/summary/demographics.php

# Expose standard OpenEMR ports
EXPOSE 80 443

# Inherit CMD/ENTRYPOINT from base image
