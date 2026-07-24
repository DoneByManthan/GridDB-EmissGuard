from pathlib import Path
import jpype

BASE = Path(__file__).resolve().parent
LIBS = BASE / "libs"

if not jpype.isJVMStarted():
    jpype.startJVM(classpath=[
        str(LIBS / "gridstore.jar"),
        str(LIBS / "gridstore-arrow.jar"),
        str(LIBS / "arrow-memory-netty.jar"),
    ])

import griddb_python as griddb

__all__ = ["griddb"]