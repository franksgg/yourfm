#!/bin/sh

INIT_FILE="init.sql"

# env
#exec tail -f /dev/null
set -e


if [ -n "$APP_USER" ]; then
sed -i -e "s/APP_USER/$APP_USER/g" $INIT_FILE
fi

if [ -n "$APP_PASSWORD" ]; then
   sed -i -e "s/APP_PASSWORD/$APP_PASSWORD/g" $INIT_FILE
fi

echo /opt/firebird/bin/isql -user SYSDBA -pass ${FIREBIRD_ROOT_PASSWORD:-masterkey} -i /home/shiva/bin/init.sql firebird:/var/lib/firebird/data/${FIREBIRD_DATABASE}
/opt/firebird/bin/isql -user SYSDBA -pass ${FIREBIRD_ROOT_PASSWORD:-masterkey} -i /home/shiva/bin/init.sql firebird:/var/lib/firebird/data/${FIREBIRD_DATABASE}
#
