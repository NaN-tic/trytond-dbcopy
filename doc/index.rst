Database Copy Module
####################

The dbcopy module create a new database from production database. The database
_test is available to test in test enviroment.

Add new params in tryton.cfg server options:

Configuration
=============

To receive e-mail is necessary to add an email address to the user that
performs the copy: Menu Administration> Users> Users.

Warning
=======

It is strongly recommended *not* to clone the database when other people are
working on the ERP because this process stops any action they were performing.
