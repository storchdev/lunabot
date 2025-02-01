{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  # Specify the Python version
  buildInputs = [
    pkgs.python312
    # pkgs.python312Packages.venv
    # pkgs.python312Packages.pip
  ];

  # Automatically set up the .venv and install requirements
  shellHook = ''
    # Check if .venv exists, if not, create it
    if [ ! -d .venv ]; then
      python3 -m venv .venv
      echo "Created .venv"
    fi

    # Activate the virtual environment
    source .venv/bin/activate

    # Install dependencies if requirements.txt exists
    if [ -f requirements.txt ]; then
      pip install -r requirements.txt
    fi

    zsh
  '';
}
