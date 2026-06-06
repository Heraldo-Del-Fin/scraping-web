"""
main.py
-------
Punto de entrada único de la aplicación.
Ejecutar con: python main.py
"""

import sys
from pathlib import Path

# Asegurar que el directorio del proyecto esté en el path de imports
sys.path.insert(0, str(Path(__file__).parent))

from gui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()