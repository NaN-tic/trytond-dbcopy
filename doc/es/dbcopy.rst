==================
Base de datos Test
==================

¿Quiero hacer una operación y no me atrevo en producción? ¿Quiero hacer una formación
y necesito un entorno con datos de prueba? Muchas de estas preguntas, las podemos realizar
en la base de datos "_test".

La base de datos "_test" le permite la generación de una nueva base de datos a partir
de la de producción con finalidades de test o pruebas. Un ejemplo de nombre de la base de datos
"_test" puede ser: nombresubasededatos_test (el nombre de la base de datos de producción
y el sufijo "_test").

Para la creación de la nueva base de datos hay que acceder a |menu_dbcopy_createdb|.
Os pedirá la contraseña del Servidor de Tryton (está contraseña no es la del usuario o usuario "admin",
si no del servidor). En el caso que no use la contraseña correcta, os mostrará el mensaje
de "Acceso denegado" (Access Denied).

El asistente para generar la nueva base de datos mostrará algunas advertencias como que durante
la generación de la misma, se reiniciará el servidor Tryton y se perderá el acceso al mismo.
Es importante realizar una copia de la base de datos un usuario administrador de la empresa
y en una hora que no haya usuarios conectados (para que no se esperen a que se restablezca la
conexión).

Una vez creada esta nueva base de datos se podrá abrir un nuevo cliente Tryton
y conectarse a la nueva base de datos de copia. Se recomienda usar los perfiles de conexión
de Tryton para guardar los datos de conexión (base de datos producción y la base de datos _test).

Recuerden que en la parte superior del cliente (título de la ventana) se muestra que base de datos
estáis conectados. Si necesitáis conectar de nuevo a la base de datos de producción, revisad que
entorno estáis conectados y en caso que estéis conectados a "_test", se debe desconectar y conectar
a la base de datos de producción.

.. |menu_dbcopy_createdb| tryref:: dbcopy.menu_dbcopy_createdb/complete_name
