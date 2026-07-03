#!/usr/bin/env bash
~/venv/bin/python3 prototype-dmtools.py

: '

python3 -m venv ~/venv
source ~/venv/bin/activate
pip install --upgrade pip
pip install Pillow
pip install screeninfo
deactivate

'


