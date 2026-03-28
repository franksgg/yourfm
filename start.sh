#!/usr/bin/env bash
. .venv/bin/activate
cd indexer
./ices -c ../data/ices.conf.local &
cd ..
python main.py

