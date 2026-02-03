#!/bin/bash
# Configura pg_hba.conf per permettere connessioni md5 da tutti gli host
echo "host all all all md5" >> /var/lib/postgresql/data/pg_hba.conf
