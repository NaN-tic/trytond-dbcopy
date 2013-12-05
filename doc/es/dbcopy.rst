==================
Base de datos Test
==================

¿Qué hace ese módulo? ¿Que funcionalidades añade este módulo? ¿Cómo genero un extracto
bancario? ¿Y un cierre contable? Muchas de estas preguntas, las podemos realizar en la 
base de datos "_test".

La base de datos "_test" le permite la generación de una nueva base de datos a partir
de la de producción con finalidades de test o pruebas. El nombre de la base de datos "_test"
es: nombresubasededatos_test

Para la creación de la nueva base de datos hay que acceder a |menu_dbcopy_createdb|.

El asistente para generar la nueva base de datos mostrará algunas advertencias como que durante
la generación de la misma, se reiniciará el servidor Tryton y se perderá el acceso al mismo.
Es importante realizar una copia de la base de datos un usuario administrador de la empresa
y en una hora que no haya usuarios connectados (para que no se esperen a que se restablezca la
connexión).

Una vez creada esta nueva base de datos se podrá abrir un nuevo cliente Tryton
y conectarse a la nueva base de datos de copia. Se recomienda usar los perfiles de connexión
de Tryton para guardar los datos de connexión (base de datos producción y la base de datos _test).

.. |menu_dbcopy_createdb| tryref:: dbcopy.menu_dbcopy_createdb/complete_name
