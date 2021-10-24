#! /bin/sh

set -e
cd "$(dirname "$0")"
echo "Dumping Ryza 1..."
python3 -m atelier_tools.ryza_tag_finder game_files/ryza1/game_exe
python3 -m atelier_tools --game=ryza1 dump-json webui/public/ryza1.json
echo "Dumping Ryza 2..."
python3 -m atelier_tools.ryza_tag_finder game_files/ryza2/game_exe
python3 -m atelier_tools --game=ryza2 dump-json webui/public/ryza2.json
