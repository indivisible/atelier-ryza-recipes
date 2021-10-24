#! /bin/sh

set -e
cd "$(dirname "$0")"
./update_dumps.sh
echo "Generating type bindings..."
python3 -m atelier_tools dump-ts-types >webui/src/DBTypes.ts
cd webui
echo "Deploying..."
npm run deploy
