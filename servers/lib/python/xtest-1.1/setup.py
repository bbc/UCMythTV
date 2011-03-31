from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(name="xtest",
      version="1.1",
      ext_modules=[
        Extension("xtest",
                  ["xtest.pyx"],
                  library_dirs=['/usr/X11R6/lib'],
                  libraries=["X11","Xtst"]),
        ],  
      cmdclass={'build_ext':build_ext})

