from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
from pathlib import Path
import os
import sys

deletePyflag = True
deleteCflag = True
deletePycflag = True
buildflg = True

# Get current folder path
mash_path = os.path.dirname(sys.argv[0])

files = list(Path(mash_path).glob('**/*.py'))
extensions = []
excludefiles = ['compile', 'lint', 'setup', 'gunicorn', 'env', 'app', 'auth', 'cli', 'constants', 'migrate', 'worker',
                'tasks', 'test_mock_method', '__init__', 'conf', 'wsgi']
excludefolder = ['tests', 'alembic/versions', 'notebooks_api/notebook/html_generator',"notebooks_api/scripts"]

# build .so files from .py files ###
if buildflg:
    for file in files:
        # Take out file name without .py ext
        filename = Path(file).resolve().stem
        if file.stat().st_size != 0 and filename not in excludefiles:
            relpath = os.path.relpath(os.path.dirname(file.absolute().as_posix()), mash_path)
            if relpath not in excludefolder:
                packagename = relpath.replace('/', '.') + '.' + filename if relpath != '.' else filename
                print(relpath + ":" + packagename)
                extensions.append([Extension(packagename, [str(file)])])
    for ext in extensions:
        setup(ext_modules=cythonize(ext, compiler_directives={'always_allow_keywords': True,
                                                              'c_string_type': 'str',
                                                              'c_string_encoding': 'utf8',
                                                              'language_level': 3}))

# delete *.py files ###
if deletePyflag:
    for file in files:
        filename = Path(file).resolve().stem
        relpath = os.path.relpath(os.path.dirname(file.absolute().as_posix()), mash_path)
        dirname = relpath.split('/')[0]
        if relpath not in excludefolder and filename not in excludefiles:
            file.unlink()

# delete *.c files #####
if deleteCflag:
    cfiles = list(Path(mash_path).glob('**/*.c'))
    for cfile in cfiles:
        filename = Path(cfile).resolve().stem
        relpath = os.path.relpath(os.path.dirname(file.absolute().as_posix()), mash_path)
        dirname = relpath.split('/')[0]
        if relpath not in excludefolder and filename not in excludefiles:
            cfile.unlink()

# delete *.pyc files #####
if deletePycflag:
    pycfiles = list(Path(mash_path).glob('**/*.pyc'))
    for pycfile in pycfiles:
        filename = Path(pycfile).resolve().stem
        relpath = os.path.relpath(os.path.dirname(file.absolute().as_posix()), mash_path)
        dirname = relpath.split('/')[0]
        if relpath not in excludefolder and filename not in excludefiles:
            pycfile.unlink()
