# This file is part of dbcopy module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from psycopg2 import ProgrammingError, OperationalError
from sql import Table
from trytond.backend.postgresql.database import Database as PostgreSQL


__all__ = [
    'Database',
    ]


class Database(PostgreSQL):

    @classmethod
    def drop_test(cls, cursor, database_name, attempt=1):
        if attempt > 3:
            return False

        pg_database = Table('pg_database')
        query = pg_database.select(
            pg_database.datname,
            where=(pg_database.datname == '%s_test' % database_name)
            )
        cursor.execute(*query)
        if cursor.fetchall():
            try:
                Database.drop(cursor, '%s_test' % database_name)
            except OperationalError:
                return cls.drop_test(cursor, database_name, attempt + 1)

        return True

    @classmethod
    def close_connections(cls, cursor, username, database_name, attempt=1):
        if attempt > 3:
            return False

        pg_stat_activity = Table('pg_stat_activity')
        query_activities = pg_stat_activity.select(
            pg_stat_activity.pid,
            where=(
                (pg_stat_activity.usename == username) &
                (pg_stat_activity.datname == database_name)
                )
            )
        cursor.execute(*query_activities)
        for pid in [p[0] for p in cursor.fetchall()]:
            try:
                cursor.execute('SELECT pg_cancel_backend(%s)' % pid)
                cursor.execute('SELECT pg_terminate_backend(%s)' % pid)
            except OperationalError:
                return cls.close_connections(cursor, username, database_name,
                    attempt + 1)

        return True

    @classmethod
    def create_from_template(cls, cursor, username, database_name, attempt=1):
        if attempt > 3:
            return False

        try:
            cursor.execute(
                'CREATE DATABASE "' + database_name + '_test" '
                'TEMPLATE "' + database_name + '" ENCODING \'unicode\'')
        except OperationalError:
            return cls.create_from_template(cursor, username, database_name,
                attempt + 1)
        except ProgrammingError:
            return False

        cls._list_cache = None
        return True
