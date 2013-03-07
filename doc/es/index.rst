===================
Copia base de datos
===================

Permite la generación de una nueva base de datos a partir de la de producción
con finalidades de test o pruebas. Por ejemplo, si el usuario desea realizar un
cierre contable, pero antes desea hacerlo en un entorno de pruebas, puede usar
esta nueva base de datos para hacer el test.

Para la creación de la nueva base de datos hay que acceder a |menu_sale_shop|\ .
El asistente mostrará algunas advertencias como que durante la generación de la
misma, se reiniciará el servidor Tryton y se perderá el acceso al mismo.
Una vez creada esta nueva base de datos se podrá abrir un nuevo cliente Tryton
y conectarse a la nueva base de datos de copia.

.. |menu_sale_shop| tryref:: dbcopy.menu_dbcopy_createdb/complete_name

Este módulo usa el paquete de Python `ERP DB Copia <http://doc.zikzakmedia.com/ErpDbCopy>`_
lo que permite realizar copias de seguridad también a nivel de sistema operativo.

.. warning:: Sólo podrá crear una copia de la base de datos cuando la instancia
             del servidor Tryton y la base de datos tengan el mismo nombre.
             Para la generación de esta copia, el servidor de Tryton se parará
             para poder generar esta nueva base de datos. El tiempo estimado
             durante el que el servidor permanecerá caído dependerá del tamaño
             de la base de datos original.
