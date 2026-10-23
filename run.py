"""Launch the desktop app from the original extensionless GitHub uploads."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import sys


def load(name, filename):
    loader = SourceFileLoader(name, str(Path(__file__).with_name(filename)))
    module = module_from_spec(spec_from_loader(name, loader))
    sys.modules[name] = module
    loader.exec_module(module)
    return module


if __name__ == "__main__":
    load("api", "Api")
    load("solos_app", "App").main()
