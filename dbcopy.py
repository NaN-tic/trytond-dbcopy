# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.config import config

import logging
import threading
import time

try:
    from fabric.api import env, run
except ImportError:
    message = 'Install Fabric package: pip install Fabric'
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
        return "%s_test" % dbname


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

    @staticmethod
    def dbcopy(dbname):
        env.host_string = "%(user)s@%(server)s:%(port)s" % {
            'user': config.get('erpdbcopy', 'user'),
            'server': config.get('erpdbcopy', 'server'),
            'port': config.get('erpdbcopy', 'port'),
            }

        logging.getLogger('dbcopy').info("Start database copy: %s" % dbname)

        database = config.get('database', 'uri')
        time.sleep(6)
        run('python /usr/local/bin/erpdbcopy -u %(user)s -p %(password)s -d %(dbname)s' % {
            'user': database.split('/')[2].split(':')[0] + '_test',
            'password': database.split(':')[2].split('@')[0],
            'dbname': dbname,
            })
        logging.getLogger('dbcopy').info("Finish database copy: %s" % dbname)

    def transition_createdb(self):
        dbname = Transaction().cursor.dbname

        thread1 = threading.Thread(target=self.dbcopy, args=(dbname,))
        thread1.start()
        return 'result'

    def default_result(self, fields):
        return {}
