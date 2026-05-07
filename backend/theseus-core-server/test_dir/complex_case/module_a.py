import module_b
import module_c as mc
from . import module_d
# Circular import test
import module_a
def func_a(): pass
