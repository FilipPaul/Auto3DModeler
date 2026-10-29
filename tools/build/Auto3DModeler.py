"""The built app's entry (PyInstaller, tools/build/auto3d.spec): Auto3DModeler.exe -> auto3d/launcher.py.

freeze_support first: the CAD kernel's processes (auto3d/modeler/worker.py, multiprocessing "spawn") start this same exe,
which then runs the kernel instead of a second app.
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from auto3d.launcher import main
    sys.exit(main())
