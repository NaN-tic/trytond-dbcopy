Database Copy Module
####################

The dbcopy module create a new database from production database. The database
_test is available to test in test enviroment.

Add new params in tryton.cfg server options:

* erpdbcopy_user: user server. Default: root
* erpdbcopy_server: Domain or IP server. Default: localhost
* erpdbcopy_port: Port server. Default: 22
