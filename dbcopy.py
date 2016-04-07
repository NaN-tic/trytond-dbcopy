# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from email.header import Header
from email.mime.text import MIMEText
from os import environ, path
from subprocess import Popen, PIPE
from trytond import backend
from trytond import security
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
    name = fields.Char('DB Name', readonly=True)
    super_pwd = fields.Char('Super Password', required=True)

    @staticmethod
    def default_name():
        dbname = Transaction().database.name
        return '%s_test' % dbname


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
                'dbname_error': 'You can not clone a database from a test database. '
                    'Connect to live database and clone a new test database.',
                'dbname_scheme': 'You database is not PSQL. Can not copy your database',
                'email_subject': 'Tryton dbcopy result of clone database %s',
                'db_cloned_successfully': 'Database %s cloned successfully.\n'
                    'Now you can connect to the new database.',
                'dropping_db_error': 'Error dropping database %s.',
                'creating_db_error': 'Error creating database %s.',
                'restoring_db_error': 'Error restoring database %s.',
                'user_email_error': 'User %s has not got any email address.',
                'connection_error': 'Error connection to new test database.\n'
                    'Please, create new test database or contact us.',
                })

    def transition_createdb(self):
        transaction = Transaction()
        dbname = transaction.database.name
        if dbname.endswith('_test'):
            self.raise_user_error('dbname_error')
        user = transaction.user
        super_pwd = self.start.super_pwd

        security.check_super(super_pwd)

        uri = parse_uri(config.get('database', 'uri'))
        if not uri.scheme == 'postgresql':
            self.raise_user_error('dbname_scheme')

        thread = threading.Thread(
                target=self.transition_createdb_thread,
                args=(dbname, user), kwargs={})
        thread.start()
        return 'result'

    @classmethod
    def transition_createdb_thread(cls, dbname, user):

        def prepare_message(user):
            user = Pool().get('res.user')(user)

            to_addr = user.email or config.get('email', 'from')
            if not to_addr:
                cls.raise_user_error('user_email_error', user.name)
            from_addr = config.get('email', 'from')

            subject = cls.raise_user_error('email_subject', (dbname,),
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
            with Transaction().start(dbname, user):
                message = cls.raise_user_error(message, (dbname,),
                    raise_exception=False)
                message += '\n\n'+ error
                logger.warning(message)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def send_successfully_message(user, message):
            with Transaction().start(dbname, user):
                message = cls.raise_user_error(message, (dbname,),
                    raise_exception=False)
                logger.info('Database %s cloned successfully.' % dbname)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def execute_command(command):
            uri = parse_uri(config.get('database', 'uri'))
            env = environ.copy()

            if uri.username:
                command.append('--username=' + uri.username)
            if uri.hostname:
                command.append('--host=' + uri.hostname)
            if uri.port:
                command.append('--port=' + str(uri.port))
            if uri.password:
                env['PGPASSWORD'] = uri.password

            process = Popen(command, env=env, stdout=PIPE, stderr=PIPE)
            return process.communicate()

        def get_tmp_file_name(dbname):
            tmp = tempfile.gettempdir()
            tmp_file = path.join(tmp, dbname + '.sql')
            return tmp_file

        def db_exist(dbname):
            Database = backend.get('Database')
            try:
                Database(dbname + '_test').connect()
                return True
            except Exception:
                return False

        def dump_db(dbname):
            tmp_file = get_tmp_file_name(dbname)
            command = ['pg_dump', '-d', dbname, '-f', tmp_file]
            return execute_command(command)

        def drop_db_test(dbname):
            uri = parse_uri(config.get('database', 'uri'))
            env = environ.copy()

            if uri.password:
                env['PGPASSWORD'] = uri.password

            command = ['dropdb', '-w', '-U', uri.username, dbname + '_test']
            process = Popen(command, env=env, stdout=PIPE, stderr=PIPE)
            return process.communicate()

        def force_drop_db_test(dbname):
            pg_stat_activity = Table('pg_stat_activity')

            uri = parse_uri(config.get('database', 'uri'))

            query = pg_stat_activity.select(
                pg_stat_activity.pid,
                where=(
                    (pg_stat_activity.usename == "'%s'" % uri.username) &
                    (pg_stat_activity.datname == "'%s_test'" % dbname) &
                    (Not(Like(pg_stat_activity.query, "'%pg_stat_activity%'")))
                    )
                )
            query = tuple(query)[0] % query.params
            command = ['psql', '-d', dbname + '_test',  '-c', query]
            output, error = execute_command(command)
            for proc_id in output.split('\n'):
                try:
                    pid = int(proc_id)
                except:
                    continue
                query = 'SELECT pg_cancel_backend(%s)' % pid
                command = ['psql', '-d', dbname + '_test', '-c', query]
                _, error = execute_command(command)
                if error:
                    return _, error

                query = 'SELECT pg_terminate_backend(%s)' % pid
                command = ['psql', '-d', dbname + '_test', '-c', query]
                _, error = execute_command(command)
                if error:
                    return _, error

            return drop_db_test(dbname)

        def create_db_test(dbname):
            uri = parse_uri(config.get('database', 'uri'))
            command = ['createdb', dbname + '_test', '-O', uri.username, '-T', 'template0']
            return execute_command(command)

        def restore_db_test(dbname,):
            tmp_file = get_tmp_file_name(dbname)
            command = ['psql', '-q', '-f', tmp_file, '-d', dbname + '_test']
            return execute_command(command)

        def deactivate_crons(dbname):
            cron = Table('ir_cron')
            query = cron.update([cron.active], [False])
            query = tuple(query)[0] % query.params
            command = ['psql', '-d', dbname +'_test', '-c', query]
            return execute_command(command)

        def rm_dump(dbname):
            tmp_file = get_tmp_file_name(dbname)
            command = ['rm', tmp_file]
            return execute_command(command)

        # dump db
        _, error = dump_db(dbname)
        if error:
            send_error_message(user, 'dropping_db_error', error)
            return

        # drop db
        if db_exist(dbname):
            _, error = drop_db_test(dbname)
            if error:
                _, error = force_drop_db_test(dbname)
                if error:
                    send_error_message(user, 'dropping_db_error', error)
                    return

        # create db
        _, error = create_db_test(dbname)
        if error:
            send_error_message(user, 'creating_db_error', error)
            return

        # restore db
        restore_db_test(dbname)

        # desativate crons
        _, error = deactivate_crons(dbname)
        if error:
            send_error_message(user, 'connection_error', error)
            return

        rm_dump(dbname)

        send_successfully_message(user, 'db_cloned_successfully')

    def default_result(self, fields):
        return {}
