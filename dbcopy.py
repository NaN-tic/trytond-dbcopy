# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import os
from email.header import Header
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
from trytond import backend
from trytond.config import config, parse_uri
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.sendmail import sendmail
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
import logging
import tempfile
import threading

from sql import Table
from sql.operators import Not, Like


__all__ = ['CreateDbStart', 'CreateDbResult', 'CreateDb']
logger = logging.getLogger(__name__)


class CreateDbStart(ModelView):
    'Create DB Copy'
    __name__ = 'dbcopy.createdb.start'
    database = fields.Char('Database Name')
    username = fields.Char('Database User')

    @staticmethod
    def default_database():
        dbname = Transaction().database.name
        return '%s_test' % dbname

    @staticmethod
    def default_username():
        return 'test'


class CreateDbResult(ModelView):
    'Create DB Copy'
    __name__ = 'dbcopy.createdb.result'
    name = fields.Char('DB Name', readonly=True)


class CreateDb(Wizard):
    'Create DB Copy'
    __name__ = 'dbcopy.createdb'

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
                'dbname_error': ('You can not clone a database from a test '
                    'database. Connect to live database and clone a new test '
                    'database.'),
                'dbname_scheme': ('You database is not PSQL. Can not copy your '
                    'database'),
                'email_subject': 'Tryton dbcopy result of clone database %s',
                'db_cloned_successfully': 'Database %s cloned successfully.\n'
                    'Now you can connect to the new database.',
                'dumping_db_error': 'Error dumping database %s.',
                'dropping_db_error': 'Error dropping database %s.',
                'creating_db_error': 'Error creating database %s.',
                'restoring_db_error': 'Error restoring database %s.',
                'user_email_error': 'User %s has not got any email address.',
                'connection_error': 'Error connection to new test database.\n'
                    'Please, create new test database or contact us.',
                })

    def transition_createdb(self):
        transaction = Transaction()
        user = Pool().get('res.user')(transaction.user)
        to_addr = user.email or config.get('email', 'from')
        if not to_addr:
            self.raise_user_error('user_email_error', user.name)

        source_database = transaction.cursor.dbname
        if source_database.endswith('_test'):
            self.raise_user_error('dbname_error')
        user = transaction.user

        uri = parse_uri(config.get('database', 'uri'))
        if not uri.scheme == 'postgresql':
            self.raise_user_error('dbname_scheme')

        thread = threading.Thread(
                target=self.createdb_thread,
                args=(user, source_database, self.start.database,
                self.start.username), kwargs={})
        thread.start()
        return 'result'

    @classmethod
    def createdb_thread(cls, user, source_database, target_database,
            target_username):

        def prepare_message(user):
            user = Pool().get('res.user')(user)

            to_addr = user.email or config.get('email', 'from')
            if not to_addr:
                cls.raise_user_error('user_email_error', user.name)
            from_addr = config.get('email', 'from')
            subject = cls.raise_user_error('email_subject', (source_database,),
                raise_exception=False)
            return to_addr, from_addr, subject

        def create_message(from_addr, to_addrs, subject, body):
            msg = MIMEText(body, _charset='utf-8')
            msg['To'] = ', '.join(to_addrs)
            msg['From'] = from_addr
            msg['Subject'] = Header(subject, 'utf-8')
            return msg

        def send_message(from_addr, to_addrs, subject, body):
            msg = create_message(from_addr, to_addrs, subject, body)
            sendmail(from_addr, to_addrs, msg)

        def send_error_message(user, message, error):
            with Transaction().start(source_database, user):
                message = cls.raise_user_error(message, (source_database,),
                    raise_exception=False).decode("ascii", "replace")
                message += '\n\n'+ error.decode("ascii", "replace")
                logger.warning(message)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def send_successfully_message(user, message):
            with Transaction().start(source_database, user):
                message = cls.raise_user_error(message, (source_database,),
                    raise_exception=False)
                logger.info('Database %s cloned successfully.' %
                    source_database)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def execute_command(command, database, username=None, password=None):
            uri = parse_uri(config.get('database', 'uri'))
            env = os.environ.copy()

            if username:
                command.append('--username=' + username)
            if uri.hostname:
                command.append('--host=' + uri.hostname)
            if uri.port:
                command.append('--port=' + str(uri.port))
            if password:
                env['PGPASSWORD'] = password
            command.append(database)

            process = Popen(command, env=env, stdout=PIPE, stderr=PIPE)
            return process.communicate()

        def db_exist(database):
            Database = backend.get('Database')
            try:
                Database(dbname + '_test').connect()
                return True
            except Exception:
            return database in databases

        def dump_db(database, path):
            command = ['pg_dump', '-f', path]
            return execute_command(command, database)

        def drop_db(database, username):
            command = ['dropdb', '-w']
            return execute_command(command, database, username)

        def force_drop_db(database, username):
            pg_stat_activity = Table('pg_stat_activity')

            uri = parse_uri(config.get('database', 'uri'))

            query = pg_stat_activity.select(
                pg_stat_activity.pid,
                where=(
                    (pg_stat_activity.usename == "'%s'" % uri.username) &
                    (pg_stat_activity.datname == "'%s'" % database) &
                    (Not(Like(pg_stat_activity.query, "'%pg_stat_activity%'")))
                    )
                )
            query = tuple(query)[0] % query.params
            command = ['psql', '-c', query]
            output, error = execute_command(command, database, username)
            for proc_id in output.split('\n'):
                try:
                    pid = int(proc_id)
                except:
                    continue
                query = 'SELECT pg_cancel_backend(%s)' % pid
                command = ['psql', '-c', query]
                _, error = execute_command(command, database, username)
                if error:
                    return _, error

                query = 'SELECT pg_terminate_backend(%s)' % pid
                command = ['psql', '-c', query]
                _, error = execute_command(command, database, username)
                if error:
                    return _, error
            return drop_db(database, username)

        def create_db(database, username):
            command = ['createdb']
            if username:
                command += ['-O', username]
            command += ['-T', 'template0']
            return execute_command(command, database, username)

        def restore_db(path, database, username):
            command = ['psql', '-q', '-f', path]
            return execute_command(command, database, username)

        def deactivate_crons(database):
            cron = Table('ir_cron')
            query = cron.update([cron.active], [False])
            query = tuple(query)[0] % query.params
            command = ['psql', '-c', query]
            return execute_command(command, database)


        _, path = tempfile.mkstemp('.sql')

        # Dump source database
        _, error = dump_db(source_database, path)
        if error:
            send_error_message(user, 'dumping_db_error', error)
            return

        # Drop target database
        if db_exist(target_database):
            _, error = drop_db(target_database, target_username)
            if error:
                _, error = force_drop_db(target_database, target_username)
                if error:
                    send_error_message(user, 'dropping_db_error', error)
                    return

        # Create target database
        _, error = create_db(target_database, target_username)
        if error:
            send_error_message(user, 'creating_db_error', error)
            return

        # Restore into target database
        _, error = restore_db(path, target_database, target_username)
        if error:
            send_error_message(user, 'restoring_db_error', error)
            return

        # Deactivate crons on target database
        _, error = deactivate_crons(target_database)
        if error:
            send_error_message(user, 'connection_error', error)
            return

        # Remove dump file
        os.remove(path)

        send_successfully_message(user, 'db_cloned_successfully')

    def default_result(self, fields):
        return {}
