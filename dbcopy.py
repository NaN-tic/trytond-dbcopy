# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from email.header import Header
from email.mime.text import MIMEText
from os import environ, path
from subprocess import Popen, PIPE
from trytond.config import config, parse_uri
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.tools import get_smtp_server
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

    @staticmethod
    def default_name():
        dbname = Transaction().cursor.dbname
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
                'dbname_error': 'You cannot make a database clone of test.',
                'email_subject': 'Tryton dbcopy result of clone database %s',
                'db_cloned_successfully': 'Database %s cloned successfully.\n'
                    'Now you can connect to the new database.',
                'dropping_db_error': 'Error dropping database %s.',
                'creating_db_error': 'Error creating database %s.',
                'restoring_db_error': 'Error restoring database %s.',
                'user_email_error': 'User %s has not got any email address.',
                'deactivating_cron_error': 'Error deactivating crons.\n'
                    'Please, deactivate them manually.',
                })

    def transition_createdb(self):
        transaction = Transaction()
        dbname = transaction.cursor.dbname
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

        def prepare_message(user):
            user = Pool().get('res.user')(user)

            to_addr = user.email
            if not to_addr:
                cls.raise_user_error('user_email_error', user.name)
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
            with Transaction().start(dbname, user):
                message = cls.raise_user_error(message, ('%s_test' % dbname,),
                    raise_exception=False)
                logger.warning(message)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)
                send_message(from_addr, ['suport@zikzakmedia.com'], subject,
                    message)

        def send_successfully_message(user, message):
            with Transaction().start(dbname, user):
                message = cls.raise_user_error(message, (dbname,),
                    raise_exception=False)
                logger.info('Database %s cloned successfully.' % dbname)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def execute_command(password, command):
            env = environ.copy()
            env['PGPASSWORD'] = password
            process = Popen(command, env=env, stdout=PIPE, stderr=PIPE)
            return process.communicate()

        def get_tmp_file_name(dbname):
            tmp = tempfile.gettempdir()
            tmp_file = path.join(tmp, dbname + '.sql')
            return tmp_file

        def dump_db(dbname, username, password):
            tmp_file = get_tmp_file_name(dbname)
            command = ['pg_dump', '-d', dbname, '-U', username, '-f', tmp_file]
            return execute_command(password, command)

        def drop_db_test(dbname, username, password):
            command = ['dropdb', '-w', '-U', username, dbname + '_test']
            return execute_command(password, command)

        def force_drop_db_test(dbname, username, password):
            pg_stat_activity = Table('pg_stat_activity')
            query = pg_stat_activity.select(
                pg_stat_activity.pid,
                where=(
                    (pg_stat_activity.usename == "'%s'" % username) &
                    (pg_stat_activity.datname == "'%s_test'" % dbname) &
                    (Not(Like(pg_stat_activity.query, "'%pg_stat_activity%'")))
                    )
                )
            query = tuple(query)[0] % query.params
            command = ['psql', '-d', '%s_test' % dbname, '-U', username, '-c',
                query]
            output, error = execute_command(password, command)
            for proc_id in output.split('\n'):
                try:
                    pid = int(proc_id)
                except:
                    continue

                query = 'SELECT pg_cancel_backend(%s)' % pid
                command = ['psql', '-d', '%s_test' % dbname, '-U', username,
                    '-c', query]
                _, error = execute_command(password, command)
                if error:
                    return _, error

                query = 'SELECT pg_terminate_backend(%s)' % pid
                command = ['psql', '-d', '%s_test' % dbname, '-U', username,
                    '-c', query]
                _, error = execute_command(password, command)
                if error:
                    return _, error

            return drop_db_test(dbname, username, password)

        def create_db_test(dbname, username, password):
            command = ['createdb', dbname + '_test', '-O', username]
            return execute_command(password, command)

        def restore_db_test(dbname, username, password):
            tmp_file = get_tmp_file_name(dbname)
            command = ['psql', '-q', '-f', tmp_file, '-U', username,
                '-d', dbname + '_test']
            return execute_command(password, command)

        def deactivate_crons(dbname, username, password):
            cron = Table('ir_cron')
            query = cron.update([cron.active], [False])
            query = tuple(query)[0] % query.params
            command = ['psql', '-d', dbname, '-U', username, '-c', query]
            return execute_command(password, command)

        def rm_dump(dbname):
            tmp_file = get_tmp_file_name(dbname)
            command = ['rm', tmp_file]
            return execute_command(password, command)

        uri = parse_uri(config.get('database', 'uri'))
        assert uri.scheme == 'postgresql'
        username = uri.username
        password = uri.password

        _, error = dump_db(dbname, username, password)
        if error:
            send_error_message(user, 'dropping_db_error')
            return

        _, error = drop_db_test(dbname, username, password)
        if error and 'does not exist' not in error:
            _, error = force_drop_db_test(dbname, username, password)
            if error:
                send_error_message(user, 'dropping_db_error')
                return

        _, error = create_db_test(dbname, username, password)
        if error:
            send_error_message(user, 'creating_db_error')
            return

        _, error = restore_db_test(dbname, username, password)
        if error:
            send_error_message(user, 'restoring_db_error')
            return

        _, error = deactivate_crons('%s_test' % dbname, username, password)
        if error:
            send_error_message(user, 'deactivating_cron_error')
            return

        rm_dump(dbname)

        send_successfully_message(user, 'db_cloned_successfully')

    def default_result(self, fields):
        return {}
