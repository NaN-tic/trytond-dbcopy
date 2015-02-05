# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from subprocess import Popen, PIPE
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

    def dbcopy(self, dbname):

        def erp_command(db_user, db_password, dbname):
            return ('python /usr/local/bin/erpdbcopy -u %(user)s '
                '-p %(password)s -d %(dbname)s' % {
                    'user': db_user,
                    'password': db_password,
                    'dbname': dbname,
                    })

        database = config.get('database', 'uri')
        db_user = database.split('/')[2].split(':')[0] + '_test'
        db_password = database.split(':')[2].split('@')[0]
        db_server = database.split(':')[2].split('@')[1]

        logging.getLogger('dbcopy').info("Start database copy: %s" % dbname)
        if db_server != 'localhost':
            user = config.get('erpdbcopy', 'user', 'root')
            port = config.get('erpdbcopy', 'port', 22)
            env.host_string = "%(user)s@%(server)s:%(port)s" % {
                'user': user,
                'server': db_server,
                'port': port,
                }
            time.sleep(6)
            run(erp_command(db_user, db_password, dbname))
        else:
            command = erp_command(db_user, db_password, dbname)
            proccess = Popen(command, shell=True, stderr=PIPE)
            _, error = proccess.communicate()
            if error:
                logging.getLogger('dbcopy').error("Error making copy of %s: %s"
                    % (dbname, error))

        logging.getLogger('dbcopy').info("Finish database copy: %s" % dbname)

    def transition_createdb(self):
        dbname = Transaction().cursor.dbname

        thread1 = threading.Thread(target=self.dbcopy, args=(dbname,))
        thread1.start()
        return 'result'

    def default_result(self, fields):
        return {}
