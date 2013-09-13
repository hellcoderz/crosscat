# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the application


import sys
#
import cx_Freeze


excludes = [
    'FixTk',
    'Tkconstants',
    'Tkinter',
    ]
includes = [
    'tabular_predDB.utils.data_utils',
    'tabular_predDB.utils.file_utils',
    'tabular_predDB.utils.timing_test_utils',
    'tabular_predDB.utils.convergence_test_utils',
    'tabular_predDB.LocalEngine',
    'tabular_predDB.HadoopEngine',
    'tabular_predDB.cython_code.State',
    'tabular_predDB.utils.xnet_utils',
    'tabular_predDB.utils.general_utils',
    'tabular_predDB.utils.sample_utils',
    'numpy',
    'sklearn.metrics',
    'sklearn.utils.lgamma',
    'scipy.special',
    'scipy.sparse.csgraph._validation',
    ]

buildOptions = dict(
        excludes = excludes,
        includes = includes,
        compressed = False,
)

executables = [
        cx_Freeze.Executable("hadoop_line_processor.py", base = None)
]

cx_Freeze.setup(
        name = "hadoop_line_processor",
        version = "0.1",
        description = "process arbitrary engine commands on hadoop",
        executables = executables,
        options = dict(build_exe = buildOptions))