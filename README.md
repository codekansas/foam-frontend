# FOAM Frontend

Webserver for hosting my personal notes on a Raspberry Pi.

## Getting Started

Clone this repo:

```sh
git clone git@github.com:codekansas/foam-frontend.git
```

Create a new Conda environment (or install the required dependencies) from the requirements file:

```sh
conda install --yes --file requirements.txt
```

Set `NOTES_ROOT` environment variable to point at your [FOAM][foam-github] notes root directory:

```sh
export NOTES_ROOT=/path/to/notes/root

# Optionally, add this line to your Conda environment's `activate.d` file
# to avoid having to set the environment variable each time you reload the shell.
mkdir -p $CONDA_PREFIX/etc/conda/activate.d/
echo "export NOTES_ROOT=$NOTES_ROOT" >> $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
```

Serve the Flask app normally:

```sh
flask run
```

[foam-github]: https://github.com/foambubble/foam
