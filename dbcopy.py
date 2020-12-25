# This file is part dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import os
import logging
import tempfile
import threading
from sql import Table
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
from trytond.config import config, parse_uri
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.sendmail import sendmail
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.i18n import gettext
from trytond.exceptions import UserError


logger = logging.getLogger(__name__)


class CreateDbStart(ModelView):
    'Create DB Copy'
    __name__ = 'dbcopy.createdb.start'

    database = fields.Char('Database Name', required=True)
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

    def transition_createdb(self):
        transaction = Transaction()
        user = Pool().get('res.user')(transaction.user)
        to_addr = user.email or config.get('email', 'from')
        if not to_addr:
            raise UserError(gettext('dbcopy.user_email_error', user=user.name))
        if self.start.database == transaction.database.name:
            raise UserError(gettext('dbcopy.cannot_overwrite'))
        if not 'test' in self.start.database:
            raise UserError(gettext('dbcopy.must_contain_test'))
        user = transaction.user

        uri = parse_uri(config.get('database', 'uri'))
        if not uri.scheme == 'postgresql':
            raise UserError(gettext('dbcopy.dbname_scheme'))

        thread = threading.Thread(
                target=self.createdb_thread,
                args=(user, transaction.database.name, self.start.database,
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
                raise UserError('dbcopy.user_email_error', user=user.name)
            from_addr = config.get('email', 'from')
            subject = gettext('dbcopy.email_subject',
                source_database=source_database)
            return to_addr, from_addr, subject

        def send_message(from_addr, to_addr, subject, body):
            msg = MIMEText(body, _charset='utf-8')
            msg['To'] = ', '.join(to_addr)
            msg['From'] = from_addr
            msg['Subject'] = Header(subject, 'utf-8')
            try:
                sendmail(msg['From'],msg['To'],msg)
                logger.info('eMail delivered to %s ' % msg['To'])
            except Exception as exception:
                logger.warning('Unable to deliver email (%s):\n %s'
                    % (exception, msg.as_string()))

        def send_error_message(user, message, error):
            with Transaction().start(source_database, user):
                message = gettext(message, source=source_database)
                message += '\n\n'+ error.decode("ascii", "replace")
                logger.warning(message)
                to_addr, from_addr, subject = prepare_message(user)
                send_message(from_addr, [to_addr], subject, message)

        def send_successfully_message(user, message):
            with Transaction().start(source_database, user):
                message = gettext(message,
                    source=source_database, target=target_database)
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

            logger.info('Command to execute: %s' % command)
            process = Popen(command, env=env, stdout=PIPE, stderr=PIPE)
            return process.communicate()

        def db_exists(database):
            cursor = Transaction().connection.cursor()
            pg_database = Table('pg_database')
            query = pg_database.select(pg_database.datname)
            cursor.execute(*query)
            databases = [x[0] for x in cursor.fetchall()]
            cursor.close()
            return database in databases

        def dump_db(database, path, username=None, password=None):
            command = ['pg_dump', '-f', path]
            logger.info('Command to dump: %s' % command)
            return execute_command(command, database, username, password)

        def drop_db(database, username, password):
            command = ['dropdb', '-w']
            logger.info('Command to drop: %s' % command)
            return execute_command(command, database, username, password)

        def force_drop_db(database, username, password):
            cursor = Transaction().connection.cursor()
            query = "SELECT pid FROM pg_stat_activity WHERE datname='%s'" % database
            cursor.execute(query)
            pids = [x[0] for x in cursor.fetchall()]
            for pid in pids:
                query = 'SELECT pg_cancel_backend(%s)' % pid
                cursor.execute(query)
                query = 'SELECT pg_terminate_backend(%s)' % pid
                cursor.execute(query)
            return drop_db(database, username, password)

        def create_db(database, username, password):
            command = ['createdb']
            if username:
                command += ['-O', username]
            command += ['-T', 'template0']
            logger.info('Command to create: %s' % command)
            return execute_command(command, database, username, password)

        def restore_db(path, database, username, password):
            command = ['psql', '-q', '-f', path]
            logger.info('Command to restore: %s' % command)
            return execute_command(command, database, username, password)

        def deactivate_crons(database):
            cron = Table('ir_cron')
            query = cron.update([cron.active], [False])
            query = tuple(query)[0] % query.params
            command = ['psql', '-c', query]
            logger.info('Command to deactivate crons: %s' % command)
            return execute_command(command, database)


        path = config.get('dbcopy', 'path')

        with Transaction().start(source_database, user):
            # Drop target database
            if db_exists(target_database):
                if path:
                    logger.info('Dumping %s database into %s' % (target_database,
                            path))
                    _, error = dump_db(target_database, os.path.join(path,
                            '%s-%s.sql' % (target_database,
                                datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))),
                        target_username, target_password)
                    if error:
                        send_error_message(user, 'dbcopy.dumping_db_error', error)
                        return
                _, error = drop_db(target_database, target_username,
                    target_password)
                if error:
                    logger.info('Could not drop database %s. Trying to force.' %
                        target_database)
                    _, error = force_drop_db(target_database, target_username,
                        target_password)
                    if error:
                        send_error_message(user, 'dbcopy.dropping_db_error', error)
                        return

            # Create target database
            _, error = create_db(target_database, target_username,
                target_password)
            if error:
                send_error_message(user, 'dbcopy.creating_db_error', error)
                return

            # Dump source database
            temporary = False
            if path:
                path = os.path.join(path, '%s-%s.sql' % (source_database,
                        datetime.now().strftime('%Y-%m-%d_%H:%M:%S')))
            else:
                temporary = True
                _, path = tempfile.mkstemp('-%s.sql' %
                    datetime.now().strftime('%Y-%m-%d_%H:%M:%S'))
            logger.info('Dumping database %s into %s' % (source_database, path))

            _, error = dump_db(source_database, path)
            if error:
                send_error_message(user, 'dbcopy.dumping_db_error', error)
                if temporary:
                    os.remove(path)
                return

            # Restore into target database
            _, error = restore_db(path, target_database, target_username,
                target_password)
            if error:
                send_error_message(user, 'dbcopy.restoring_db_error', error)
                if temporary:
                    os.remove(path)
                return

            # Remove dump file
            if temporary:
                os.remove(path)

            # Deactivate crons on target database
            _, error = deactivate_crons(target_database)
            if error:
                raise UserError('dbcopy.connection_error')
                return

        send_successfully_message(user, 'dbcopy.db_cloned_successfully')

    def default_result(self, fields):
        return {}
