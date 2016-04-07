==================
Base de datos Test
==================

Permite la generación de una nueva base de datos a partir de la de producción
con finalidades de test o pruebas. Por ejemplo, si el usuario desea realizar un
cierre contable, pero antes desea hacerlo en un entorno de pruebas, puede usar
esta nueva base de datos para hacer el test.

Para la creación de la nueva base de datos hay que acceder a Administración/Copia
base de datos. Os pedirá la contraseña del Servidor de Tryton (está contraseña
no es la del usuario o usuario "admin", si no del servidor). En el caso que no use la
contraseña correcta, os mostrará el mensaje de "Acceso denegado" (Access Denied).

El asistente mostrará algunas advertencias como que durante la generación de la
misma, se reiniciará el servidor Tryton y se perderá el acceso al mismo.

Una vez creada esta nueva base de datos se podrá abrir un nuevo cliente Tryton
y conectarse a la nueva base de datos de copia.

Una vez realizada la copia, se envía un correo electrónico al usuario
informando del resultado de la clonación. En caso de fallo también se le envía
al proveedor de los servicios TIC.

Configuración
=============

Para recibir el correo electrónico es necesario añadir una dirección de correo
electrónico al usuario que realice la copia (en sus preferencias).

Precauciones
============

Se recomienda encarecidamente *no* realizar una copia de la base de datos
cuando otras personas están trabajando en el ERP debido a que este proceso
interrumpe cualquier acción que estuvieran realizando.
