#This file is part dbcopy module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .dbcopy import *
from .user import *


def register():
    Pool.register(
        CreateDbStart,
        CreateDbResult,
        User,
        module='dbcopy', type_='model')
    Pool.register(
        CreateDb,
        module='dbcopy', type_='wizard')
