#This file is part dbcopy module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.config import CONFIG
import os
import logging

try:
    from erpdbcopy import version
except ImportError:
    message = 'Unable to find ERP DB Copy Package'
    logging.getLogger('dbcopy').error(message)
    raise Exception(message)

__all__ = ['CreateDbStart', 'CreateDbResult', 'CreateDb']


class CreateDbStart(ModelView):
    "Create DB Copy"
    __name__ = 'dbcopy.createdb.start'

    name = fields.Char('DB Name', readonly=True)

    @staticmethod
    def default_name():
        dbname = Transaction().cursor.dbname
        return "%s_copia" % dbname


class CreateDbResult(ModelView):
    "Create DB Copy"
    __name__ = 'dbcopy.createdb.result'


class CreateDb(Wizard):
    "Create DB Copy"
    __name__ = "dbcopy.createdb"

    start = StateView('dbcopy.createdb.start',
        'dbcopy.createdb_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create database copy', 'createdb', 'tryton-ok', default=True),
            ])
    createdb = StateTransition()
    result = StateView('dbcopy.createdb.result',
        'dbcopy.createdb_result_view_form', [
            Button('Close', 'end', 'tryton-close'),
            ])

    def transition_createdb(self):
        dbname = Transaction().cursor.dbname
        user = CONFIG['db_user'] or ''
        password = CONFIG['db_password'] or ''

        command = 'sudo bash -c "erpdbcopy -s %(server)s -u %(user)s -p %(password)s -d %(dbname)s -e trytond"' % {
            'server': dbname,
            'dbname': dbname,
            'user': user,
            'password': password,
        }
        os.system(command)
        return 'result'

    def default_result(self, fields):
        return {}
