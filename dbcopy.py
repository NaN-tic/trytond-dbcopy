# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import os
from datetime import datetime
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
    password = fields.Char('Database Password')

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
                'db_cloned_successfully': ('Database %(source)s cloned '
                    'successfully into %(target)s.\nNow you can connect to the '
                    'new database.'),
                'dumping_db_error': 'Error dumping database %s.',
                'dropping_db_error': 'Error dropping database %s.',
                'creating_db_error': 'Error creating database %s.',
                'restoring_db_error': 'Error restoring database %s.',
                'user_email_error': 'User %s has not got any email address.',
                'connection_error': 'Error connection to new test database.\n'
                    'Please, create new test database or contact us.',
                'cannot_overwrite': 'You cannot overwrite current database.',
                'must_contain_test': ('To prevent removal of valid data, '
                    'target database must contain "test" in its name.'),
                })

    def transition_createdb(self):
        transaction = Transaction()
        user = Pool().get('res.user')(transaction.user)
        to_addr = user.email or config.get('email', 'from')
        if not to_addr:
            self.raise_user_error('user_email_error', user.name)

        if self.start.database == transaction.cursor.dbname:
            self.raise_user_error('cannot_overwrite')
        if not 'test' in self.start.database:
            self.raise_user_error('must_contain_test')
        user = transaction.user

        uri = parse_uri(config.get('database', 'uri'))
        if not uri.scheme == 'postgresql':
            self.raise_user_error('dbname_scheme')

        thread = threading.Thread(
                target=self.createdb_thread,
                args=(user, transaction.cursor.dbname, self.start.database,
                self.start.username, self.start.password), kwargs={})
        thread.start()
        return 'result'

    @classmethod
    def createdb_thread(cls, user, source_database, target_database,
            target_username, target_password):

        def prepare_message(user):
            user = Pool().get('res.user')(user)

            to_addr = user.email or config.get('email', 'from')
            if not to_addr:
                cls.raise_user_error('user_email_error', user.name)
            from_addr = config.get('email', 'from')
            subject = cls.raise_user_error('email_subject', (source_database,),
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
                message = cls.raise_user_error(message, {
                        'source': source_database,
                        'target': target_database,
                        }, raise_exception=False)
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

        def db_exists(database):
            Database = backend.get('Database')
            database = Database().connect()
            cursor = database.cursor()
            databases = database.list(cursor)
            cursor.close()
            return database in databases

        def dump_db(database, path, password):
            command = ['pg_dump', '-f', path]
            return execute_command(command, database, password)

        def drop_db(database, username, password):
            command = ['dropdb', '-w']
            return execute_command(command, database, username, password)

        def force_drop_db(database, username, password):
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
            output, error = execute_command(command, database, username,
                password)
            for proc_id in output.split('\n'):
                try:
                    pid = int(proc_id)
                except:
                    continue
                query = 'SELECT pg_cancel_backend(%s)' % pid
                command = ['psql', '-c', query]
                _, error = execute_command(command, database, username,
                    password)
                if error:
                    return _, error

                query = 'SELECT pg_terminate_backend(%s)' % pid
                command = ['psql', '-c', query]
                _, error = execute_command(command, database, username,
                    password)
                if error:
                    return _, error
            return drop_db(database, username, password)

        def create_db(database, username, password):
            command = ['createdb']
            if username:
                command += ['-O', username]
            command += ['-T', 'template0']
            return execute_command(command, database, username, password)

        def restore_db(path, database, username, password):
            command = ['psql', '-q', '-f', path]
            return execute_command(command, database, username, password)

        def deactivate_crons(database):
            cron = Table('ir_cron')
            query = cron.update([cron.active], [False])
            query = tuple(query)[0] % query.params
            command = ['psql', '-c', query]
            return execute_command(command, database)


        # Drop target database
        if db_exists(target_database):
            _, error = drop_db(target_database, target_username,
                target_password)
            if error:
                _, error = force_drop_db(target_database, target_username,
                    target_password)
                if error:
                    send_error_message(user, 'dropping_db_error', error)
                    return

        # Create target database
        _, error = create_db(target_database, target_username, target_password)
        if error:
            send_error_message(user, 'creating_db_error', error)
            return

        # Dump source database
        temporary = False
        path = config.get('dbcopy', 'path')
        if not path:
            temporary = True
            _, path = tempfile.mkstemp('-%s.sql' %
                datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))
        logger.info('Dumping database into %s' % path)

        _, error = dump_db(source_database, path, target_password)
        if error:
            send_error_message(user, 'dumping_db_error', error)
            if temporary:
                os.remove(path)
            return

        # Restore into target database
        _, error = restore_db(path, target_database, target_username,
            target_password)
        if error:
            send_error_message(user, 'restoring_db_error', error)
            if temporary:
                os.remove(path)
            return

        # Remove dump file
        if temporary:
            os.remove(path)

        # Deactivate crons on target database
        _, error = deactivate_crons(target_database)
        if error:
            send_error_message(user, 'connection_error', error)
            return

        send_successfully_message(user, 'db_cloned_successfully')

    def default_result(self, fields):
        return {}
