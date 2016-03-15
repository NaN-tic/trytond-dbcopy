# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from email.header import Header
from email.mime.text import MIMEText
from time import sleep
from trytond.pool import Pool
import logging
import threading

from psycopg2 import InterfaceError
from trytond.config import config, parse_uri
from trytond.model import ModelView, fields
from trytond.tools import get_smtp_server
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

from .database import Database


__all__ = ['CreateDbStart', 'CreateDbResult', 'CreateDb']
logger = logging.getLogger(__name__)


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
    name = fields.Char('DB Name', readonly=True)


class CreateDb(Wizard):
    "Create DB Copy"
    __name__ = "dbcopy.createdb"

    start = StateView('dbcopy.createdb.start',
        'dbcopy.createdb_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create database copy', 'createdb', 'tryton-ok',
                default=True),
            ])
    createdb = StateTransition()
    result = StateView('dbcopy.createdb.result',
        'dbcopy.createdb_result_view_form', [
            Button('Close', 'end', 'tryton-close'),
            ])

    @classmethod
    def __setup__(cls):
        super(CreateDb, cls).__setup__()
        cls._error_messages.update({
                'dbname_error': 'You cannot make a database clone of test.',
                'email_subject': 'Tryton dbcopy result of clone database %s',
                'db_cloned_successfully': 'Database %s cloned successfully.',
                'db_clone_error': 'Error cloning database %s.',
                'closing_db_connections_error': 'Error closing database '
                    '%s connections.',
                'dropping_db_error': 'Error dropping database %s.',
                })

    def transition_createdb(self):
        transaction = Transaction()
        cursor = transaction.cursor
        dbname = cursor.dbname
        if dbname.endswith('_test'):
            self.raise_user_error('dbname_error')
        user = transaction.user

        thread = threading.Thread(
                target=self.transition_createdb_thread,
                args=(dbname, user), kwargs={})
        thread.start()
        return 'result'

    @classmethod
    def transition_createdb_thread(cls, dbname, user):
        sleep(0.1)

        def prepare_message(user):
            user = Pool().get('res.user')(user)

            to_addr = [user.email]
            from_addr = config.get('email', 'from')
            subject = cls.raise_user_error('email_subject', (dbname,),
                raise_exception=False)
            return to_addr, from_addr, subject

        def send_message(from_addr, to_addr, subject, body):
            msg = MIMEText(body, _charset='utf-8')
            msg['To'] = ', '.join(to_addr)
            msg['From'] = from_addr
            msg['Subject'] = Header(subject, 'utf-8')
            try:
                server = get_smtp_server()
                server.sendmail(from_addr, ', '.join(to_addr), msg.as_string())
                server.quit()
                logger.info('eMail delivered to %s ' % msg['To'])
            except Exception, exception:
                logger.warning('Unable to deliver email (%s):\n %s'
                    % (exception, msg.as_string()))

        def send_error_message(user, message):
            logger.warning(message)
            to_addr, from_addr, subject = prepare_message(user)
            send_message(from_addr, to_addr, subject, message)
            send_message(from_addr, ['aneolf@yahoo.es'], subject, message)

        def send_successfully_message(user, message):
            logger.info('Database %s cloned successfully.' % dbname)
            to_addr, from_addr, subject = prepare_message(user)
            send_message(from_addr, to_addr, subject, message)

        def restore_transaction(transaction):
            for count in range(config.getint('database', 'retry'), -1, -1):
                try:
                    transaction.user = None
                    transaction.database = None
                    transaction.cursor = None
                    transaction.close = None
                    transaction.context = None
                    try:
                        transaction.start(dbname, user)
                    except InterfaceError:
                        if count:
                            continue
                        raise
                    break
                except AttributeError:
                    if count:
                        continue
                    raise
                except Exception, e:
                    logger.error('Error restoring transaction: %s.' % e)
                    raise

        with Transaction().start(dbname, 0) as transaction:
            database = Database().connect()
            cursor = database.cursor(autocommit=True)
            uri = parse_uri(config.get('database', 'uri'))
            assert uri.scheme == 'postgresql'
            username = uri.username

            if (not Database.close_connections(cursor, username,
                    '%s_test' % dbname)):
                message = cls.raise_user_error(
                    'closing_db_connections_error', ('%s_test' % dbname,),
                    raise_exception=False)
                send_error_message(user, message)
                return

            if not Database.drop_test(cursor, dbname):
                message = cls.raise_user_error('dropping_db_error',
                    ('%s_test' % dbname,), raise_exception=False)
                send_error_message(user, message)
                return

            if not Database.close_connections(cursor, username, dbname):
                restore_transaction(transaction)
                message = cls.raise_user_error('closing_db_connections_error',
                    (dbname,), raise_exception=False)
                send_error_message(user, message)
                return

            if not Database.create_from_template(cursor, username, dbname):
                restore_transaction(transaction)
                message = cls.raise_user_error('db_clone_error', (dbname,),
                    raise_exception=False)
                send_error_message(user, message)
                return

            restore_transaction(transaction)
            message = cls.raise_user_error('db_cloned_successfully',
                (dbname,), raise_exception=False)
            send_successfully_message(user, message)

    def default_result(self, fields):
        return {}
