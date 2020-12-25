# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import dbcopy
from . import user


def register():
    Pool.register(
        dbcopy.CreateDbStart,
        dbcopy.CreateDbResult,
        user.User,
        module='dbcopy', type_='model')
    Pool.register(
        dbcopy.CreateDb,
        module='dbcopy', type_='wizard')
