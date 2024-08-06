#!/bin/bash

# Nome del virtual environment
VENV_DIR=venv

# Verifica se Python 3.9 è installato
if ! command -v python3.9 &> /dev/null
then
    echo "Python 3.9 non è installato. Installalo e riprova."
    exit 1
fi

# Creazione del virtual environment
echo "Creazione del virtual environment in ${VENV_DIR}"
python3.9 -m venv $VENV_DIR

# Attivazione del virtual environment
source $VENV_DIR/bin/activate

# Installazione della libreria pox
echo "Installazione della libreria pox"
pip install pox
pip install networkx
pip install numpy

# Disattivazione del virtual environment
deactivate

echo "Virtual environment creato e pox installato con successo."
