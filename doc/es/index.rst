==================
Base de datos Test
==================

Permite la generación de una nueva base de datos a partir de la de producción
con finalidades de test o pruebas. Por ejemplo, si el usuario desea realizar un
cierre contable, pero antes desea hacerlo en un entorno de pruebas, puede usar
esta nueva base de datos para hacer el test.

Para la creación de la nueva base de datos hay que acceder a Administración.

El asistente mostrará algunas advertencias como que durante la generación de la
misma, se reiniciará el servidor Tryton y se perderá el acceso al mismo.

Una vez creada esta nueva base de datos se podrá abrir un nuevo cliente Tryton
y conectarse a la nueva base de datos de copia.

Este módulo usa el paquete de Python ERP DB Copia https://pypi.python.org/pypi/erpdbcopy
lo que permite realizar copias de seguridad también a nivel de sistema operativo.

Deberá añadir nuevas parámetros en el fichero tryton.cfg:

* erpdbcopy_user: usuario del servidor. Defecto: root
* erpdbcopy_server: Dominio or IP del servidor. Defecto: localhost
* erpdbcopy_port: Puerto del servidor. Defecto: 22
