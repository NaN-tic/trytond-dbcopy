#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = "res.user"

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        status += ' - DB: %s' % (Transaction().cursor.dbname)
        return status
